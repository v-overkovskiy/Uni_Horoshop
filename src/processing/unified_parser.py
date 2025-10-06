import asyncio
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple
import logging
from .characteristics_translator import CharacteristicsTranslator
from ..validation.language_validator import LanguageValidator

logger = logging.getLogger(__name__)

class UnifiedParser:
    """
    Универсальный динамический парсер для параллельного анализа RU и UA версий.
    Работает без словарей и статических правил, адаптируется к любой структуре HTML.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.translator = CharacteristicsTranslator()
        self.language_validator = LanguageValidator()
        
        # Кеш парсинга для оптимизации
        self._parse_cache = {}  # URL → parsed_data
        self._characteristics_cache = {}  # URL → characteristics
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def fetch_html(self, ua_url: str) -> Tuple[str, str]:
        """
        Параллельно загружает UA и RU версии страницы (асинхронно, без задержек).
        
        Args:
            ua_url: URL украинской версии страницы
            
        Returns:
            Tuple[ua_html, ru_html]: HTML контент обеих версий
        """
        ru_url = ua_url.replace('https://prorazko.com/', 'https://prorazko.com/ru/')

        async def get_html(url: str) -> str:
            try:
                loop = asyncio.get_running_loop()
                resp = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))
                return resp.text if resp.ok else ''
            except Exception as e:
                logger.warning(f"Ошибка загрузки {url}: {e}")
                return ''

        ua_html, ru_html = await asyncio.gather(
            get_html(ua_url),
            get_html(ru_url)
        )
        return ua_html, ru_html

    def parse_bundle(self, ua_html: str, ru_html: str) -> List[str]:
        """
        Динамически парсит 'состав набора' только если однозначно присутствует в обеих версиях.
        
        Args:
            ua_html: HTML украинской версии
            ru_html: HTML русской версии
            
        Returns:
            List[str]: Список компонентов набора или пустой список
        """
        soup_ua = BeautifulSoup(ua_html, 'html.parser')
        soup_ru = BeautifulSoup(ru_html, 'html.parser')

        # Динамические маркеры для поиска состава набора
        ua_markers = ['склад набор', 'комплектація', 'склад комплект', 'склад набору', 'комплектація набору', 'склад']
        ru_markers = ['состав набор', 'комплектация', 'состав комплект', 'состав набора', 'комплектация набора', 'состав']
        
        ua_bundle = self._extract_bundle_list(soup_ua, ua_markers)
        ru_bundle = self._extract_bundle_list(soup_ru, ru_markers)

        # Жёсткая проверка: списки должны быть, совпадать по содержанию/длине и иметь ≥2 элемента
        if not ua_bundle or not ru_bundle:
            logger.debug("Состав набора не найден в одной из версий")
            return []
            
        if len(ua_bundle) < 2 or len(ru_bundle) < 2:
            logger.debug("Состав набора содержит менее 2 элементов")
            return []

        # Сопоставление: проверяем совпадение наборов (динамически, без хардкода)
        # Нормализуем тексты для сравнения (убираем различия в языке)
        def normalize_text(text):
            # Убираем языковые различия для сравнения
            text_lower = text.lower()
            # Простые замены
            text_lower = text_lower.replace('піна', 'пена')
            text_lower = text_lower.replace('депіляції', 'депиляции')
            text_lower = text_lower.replace('нанесення', 'нанесения')
            text_lower = text_lower.replace('видалення', 'удаления')
            text_lower = text_lower.replace('використання', 'использования')
            text_lower = text_lower.replace('інструкція', 'инструкция')
            text_lower = text_lower.replace('з використання', 'по использованию')
            text_lower = text_lower.replace('з', 'по')
            return text_lower.strip()
        
        ua_normalized = {normalize_text(item) for item in ua_bundle}
        ru_normalized = {normalize_text(item) for item in ru_bundle}
        
        # Более гибкое сравнение - проверяем пересечение множеств
        intersection = ua_normalized.intersection(ru_normalized)
        if len(intersection) < len(ua_normalized) * 0.75:  # Если совпадает менее 75%
            logger.debug(f"Состав набора не совпадает между версиями: UA={ua_normalized}, RU={ru_normalized}")
            return []

        logger.info(f"Найден состав набора: {len(ua_bundle)} элементов")
        return ua_bundle  # Возвращаем UA-версию (локализованную)

    def _extract_bundle_list(self, soup: BeautifulSoup, markers: List[str]) -> List[str]:
        """
        Динамически ищет маркер + следующий ul/li, адаптируясь к структуре.
        
        Args:
            soup: BeautifulSoup объект для парсинга
            markers: Список маркеров для поиска
            
        Returns:
            List[str]: Список элементов или пустой список
        """
        for tag in soup.find_all(['h2', 'h3', 'strong', 'p', 'div', 'span']):
            text = tag.get_text(strip=True).lower()
            logger.debug(f"Проверяем тег: '{text}'")
            if any(marker in text for marker in markers):
                logger.debug(f"Найден маркер в тексте: '{text}'")
                # Ищем ближайший ul или ol (список)
                list_tag = tag.find_next(['ul', 'ol'])
                if list_tag:
                    items = [li.get_text(strip=True) for li in list_tag.find_all('li') if li.get_text(strip=True)]
                    if items:
                        logger.debug(f"Найден список состава: {len(items)} элементов")
                        return items
        return []

    async def parse_characteristics(self, ua_html: str, ru_html: str) -> Tuple[list, list]:
        """
        Универсальный парсер с кешированием характеристик.
        
        Args:
            ua_html: HTML украинской версии
            ru_html: HTML русской версии
            
        Returns:
            Tuple[Dict[str, str], Dict[str, str]]: (ru_specs, ua_specs)
        """
        # Создаем ключ кеша на основе содержимого HTML
        import hashlib
        cache_key = hashlib.md5(f"{ua_html[:1000]}{ru_html[:1000]}".encode()).hexdigest()
        
        # Проверяем кеш
        if cache_key in self._characteristics_cache:
            self._cache_hits += 1
            logger.info(f"✅ Кеш характеристик: {cache_key[:8]}...")
            return self._characteristics_cache[cache_key]
        
        self._cache_misses += 1
        
        soup_ua = BeautifulSoup(ua_html, 'html.parser')
        soup_ru = BeautifulSoup(ru_html, 'html.parser')

        # Извлекаем характеристики из обеих версий независимо
        specs_ua_raw = self._extract_characteristics_from_html(soup_ua)
        specs_ru_raw = self._extract_characteristics_from_html(soup_ru)

        logger.info(f"Извлечено из UA: {len(specs_ua_raw)} характеристик")
        logger.info(f"Извлечено из RU: {len(specs_ru_raw)} характеристик")

        # ✅ ВКЛЮЧАЕМ УНИВЕРСАЛЬНЫЙ ПЕРЕВОД
        specs_ua_list = [{'label': key, 'value': value} for key, value in specs_ua_raw.items()]
        specs_ru_list = [{'label': key, 'value': value} for key, value in specs_ru_raw.items()]
        
        specs_ua_translated = await self.translator.translate_characteristics_batch(specs_ua_list, 'ua')
        specs_ru_translated = await self.translator.translate_characteristics_batch(specs_ru_list, 'ru')
        
        logger.info(f"✅ RU характеристики: {len(specs_ru_translated)} (переведенные через LLM)")
        logger.info(f"✅ UA характеристики: {len(specs_ua_translated)} (переведенные через LLM)")
        
        # Кешируем результат
        result = (specs_ru_translated, specs_ua_translated)
        self._characteristics_cache[cache_key] = result
        
        logger.info(f"📊 Кеш характеристик: {self._cache_hits} хитов, {self._cache_misses} миссов")
        
        # Возвращаем два списка словарей (переведенные характеристики)
        return result

    def _find_ua_value(self, ru_key: str, ru_specs: Dict[str, str], ua_specs: Dict[str, str]) -> str:
        """
        Находит соответствующее значение в UA версии для русского ключа.
        
        Args:
            ru_key: Русский ключ
            ru_specs: Словарь RU характеристик
            ua_specs: Словарь UA характеристик
            
        Returns:
            str: Соответствующее значение из UA или RU
        """
        # Метод 1: Прямое совпадение ключей
        if ru_key in ua_specs:
            return ua_specs[ru_key]
        
        # Метод 2: Поиск по переведенному ключу
        translated_key = self.translator.translate(ru_key)
        if translated_key in ua_specs:
            return ua_specs[translated_key]
        
        # Метод 3: Fallback по порядку (если ключи не совпадают)
        ru_keys = list(ru_specs.keys())
        ua_values = list(ua_specs.values())
        if ru_key in ru_keys:
            idx = ru_keys.index(ru_key)
            if idx < len(ua_values):
                return ua_values[idx]
        
        # Метод 4: Возвращаем RU значение как fallback
        return ru_specs.get(ru_key, "")

    def _extract_characteristics_from_html(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Извлекает все пары ключ-значение из HTML контейнера характеристик.
        """
        # Ищем самый релевантный блок для характеристик
        features_block = self._find_features_block(soup)
        if not features_block:
            logger.warning("Блок характеристик не найден")
            return {}

        # Извлекаем пары ключ-значение
        pairs = self._extract_key_value_pairs(features_block)
        logger.debug(f"Найдено пар ключ-значение: {len(pairs)}")
        return pairs

    def _find_features_block(self, soup: BeautifulSoup):
        """
        Ищет самый релевантный блок для характеристик.
        Приоритет: div.product_group с таблицей характеристик (как показано на скриншоте)
        """
        # Метод 1: Ищем div.product_group с таблицей характеристик
        product_group = soup.select_one('div.product_group')
        if product_group:
            logger.debug("Найден div.product_group")
            # Ищем таблицу характеристик внутри product_group
            table = product_group.find('table')
            if table:
                logger.debug("Найдена таблица характеристик внутри product_group")
                return table
            # Ищем ul с характеристиками внутри product_group (но не навигационные)
            ul = product_group.find('ul')
            if ul:
                # Проверяем, что это не навигационные элементы
                li_items = ul.find_all('li')
                if li_items:
                    first_li_text = li_items[0].get_text(strip=True).lower()
                    # Если первый li содержит навигационные элементы - это не характеристики
                    nav_keywords = ['грн', 'отзыв', 'сравнению', 'шт', 'наличии', 'артикул']
                    if not any(keyword in first_li_text for keyword in nav_keywords):
                        logger.debug("Найден ul с характеристиками внутри product_group")
                        return ul
        
        # Метод 2: Ищем таблицу характеристик напрямую
        table_selectors = [
            '.product-features__table',  # Основной селектор по результатам тестирования
            '.product-features table',
            'table.specs',
            '.characteristics table',
            '.product-specs table'
        ]
        
        for selector in table_selectors:
            table = soup.select_one(selector)
            if table:
                logger.info(f"✅ Найдена таблица характеристик с селектором: {selector}")
                return table
            else:
                logger.debug(f"❌ Селектор {selector} не найден")
        
        # Метод 3: Ищем ul с характеристиками (но не навигационные)
        ul_selectors = [
            'ul.specs',
            '.characteristics ul',
            '.product-specs ul'
        ]
        
        for selector in ul_selectors:
            ul = soup.select_one(selector)
            if ul:
                li_items = ul.find_all('li')
                if li_items:
                    first_li_text = li_items[0].get_text(strip=True).lower()
                    # Проверяем, что это не навигационные элементы
                    nav_keywords = ['грн', 'отзыв', 'сравнению', 'шт', 'наличии', 'артикул']
                    if not any(keyword in first_li_text for keyword in nav_keywords):
                        logger.debug(f"Найден ul с характеристиками с селектором: {selector}")
                        return ul
        
        logger.warning("Блок характеристик не найден")
        return None

    def _extract_key_value_pairs(self, container) -> Dict[str, str]:
        """
        Извлекает пары ключ-значение из контейнера.
        Поддерживает различные структуры HTML с фильтрацией мусорных данных.
        """
        pairs = {}
        if not container:
            return pairs

        # Список "мусорных" ключей, которые нужно игнорировать
        garbage_keywords = [
            'главная', 'товары', 'депиляция', 'шугаринг', 'средства', 'epilax',
            'крем', 'после', 'депиляции', 'экстракт', 'киви', 'тестер',
            'наличии', 'артикул', 'отзыв', 'грн', 'шт', 'сравнению', 'желания',
            'войдите', 'сайт', 'добавить', 'товар', 'список', 'накопительной',
            'скидки', 'купить', 'сравнение', 'желания', 'войдите', 'сайт',
            'добавить', 'товар', 'список', 'накопительной', 'скидки', 'купить'
        ]

        def is_garbage_key(key: str) -> bool:
            """Проверяет, является ли ключ мусорным"""
            key_lower = key.lower()
            # Если ключ слишком длинный (больше 100 символов) - это мусор
            if len(key) > 100:
                return True
            # Если ключ содержит много мусорных слов
            garbage_count = sum(1 for word in garbage_keywords if word in key_lower)
            if garbage_count >= 3:
                return True
            # Если ключ содержит навигационные элементы
            nav_elements = ['главная', 'товары', 'депиляция', 'шугаринг', 'средства']
            if any(nav in key_lower for nav in nav_elements):
                return True
            return False

        def is_garbage_value(val: str) -> bool:
            """Проверяет, является ли значение мусорным"""
            val_lower = val.lower()
            # Если значение слишком длинное (больше 200 символов) - это мусор
            if len(val) > 200:
                return True
            # Если значение содержит много мусорных слов
            garbage_count = sum(1 for word in garbage_keywords if word in val_lower)
            if garbage_count >= 3:
                return True
            return False

        # Метод 1: Таблица характеристик (tr с th и td)
        for tr in container.select('tr'):
            cells = tr.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).replace(':', '')
                val = cells[1].get_text(strip=True)
                
                # >> ФОРМАТИРОВАНИЕ: добавляем пробелы после запятых <<
                formatted_val = ', '.join([v.strip() for v in val.split(',')])
                
                # Фильтруем мусорные данные
                if (key and formatted_val and key not in pairs and 
                    not is_garbage_key(key) and not is_garbage_value(formatted_val)):
                    pairs[key] = formatted_val

        # Метод 2: li с span элементами
        for li in container.select('li'):
            spans = li.find_all('span')
            if len(spans) >= 1:
                key = spans[0].get_text(strip=True).replace(':', '')
                # Значение = весь текст li минус текст первого span
                full_text = li.get_text(strip=True)
                key_text = spans[0].get_text(strip=True)
                val = full_text.replace(key_text, '').strip().lstrip(':').strip()
                
                # >> ФОРМАТИРОВАНИЕ: добавляем пробелы после запятых <<
                formatted_val = ', '.join([v.strip() for v in val.split(',')])
                
                # Фильтруем мусорные данные
                if key and formatted_val and not is_garbage_key(key) and not is_garbage_value(formatted_val):
                    pairs[key] = formatted_val

        # Метод 3: div с двумя ячейками
        for row in container.select('div'):
            cells = row.find_all(['span', 'div'])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).replace(':', '')
                val = cells[1].get_text(strip=True)
                
                # >> ФОРМАТИРОВАНИЕ: добавляем пробелы после запятых <<
                formatted_val = ', '.join([v.strip() for v in val.split(',')])
                
                # Фильтруем мусорные данные
                if (key and formatted_val and key not in pairs and 
                    not is_garbage_key(key) and not is_garbage_value(formatted_val)):
                    pairs[key] = formatted_val

        # Метод 3: div с классами product-block__item
        for item in container.select('div.product-block__item, div[class*="block"]'):
            title_elem = item.find(class_=lambda x: x and ('title' in x.lower() or 'label' in x.lower()))
            value_elem = item.find(class_=lambda x: x and ('value' in x.lower() or 'content' in x.lower()))
            
            if title_elem and value_elem:
                key = title_elem.get_text(strip=True).replace(':', '')
                # ИСПРАВЛЕНИЕ ДЛЯ ПРОБЕЛОВ: используем separator для сохранения пробелов
                val = value_elem.get_text(separator=', ', strip=True)
                
                # >> ДОПОЛНИТЕЛЬНОЕ ФОРМАТИРОВАНИЕ: добавляем пробелы после запятых <<
                formatted_val = ', '.join([v.strip() for v in val.split(',')])
                
                # Фильтруем мусорные данные
                if (key and formatted_val and key not in pairs and 
                    not is_garbage_key(key) and not is_garbage_value(formatted_val)):
                    pairs[key] = formatted_val

        # Метод 4: Fallback - любой текст с двоеточием (с фильтрацией)
        for elem in container.find_all(['div', 'span', 'p']):
            text = elem.get_text(strip=True)
            if ':' in text and len(text.split(':')) == 2:
                key, val = text.split(':', 1)
                key = key.strip()
                val = val.strip()
                
                # >> ФОРМАТИРОВАНИЕ: добавляем пробелы после запятых <<
                formatted_val = ', '.join([v.strip() for v in val.split(',')])
                
                # Фильтруем мусорные данные
                if (key and formatted_val and key not in pairs and 
                    not is_garbage_key(key) and not is_garbage_value(formatted_val)):
                    pairs[key] = formatted_val

            logger.info(f"✅ Извлечено {len(pairs)} пар ключ-значение после фильтрации")
            if pairs:
                logger.info(f"Примеры характеристик: {list(pairs.items())[:3]}")
            return pairs

    def _parse_characteristics_fallback(self, ua_html: str, ru_html: str) -> Dict[str, str]:
        """Fallback метод для совместимости со старым подходом"""
        soup_ua = BeautifulSoup(ua_html, 'html.parser')
        soup_ru = BeautifulSoup(ru_html, 'html.parser')

        # Динамические селекторы для характеристик (адаптируется к классам/тегам)
        selectors = [
            'ul.specs li',
            '.characteristics li', 
            'table.specs tr',
            '.specs li',
            '.product-specs li',
            '.specifications li',
            'ul li',
            'table tr'
        ]
        
        ua_items = []
        ru_items = []
        
        for selector in selectors:
            ua_found = soup_ua.select(selector)
            ru_found = soup_ru.select(selector)
            
            if ua_found and ru_found and len(ua_found) >= 2:
                ua_items = ua_found
                ru_items = ru_found
                logger.debug(f"Fallback: найдены характеристики с селектором: {selector}")
                break

        specs = {}
        min_len = min(len(ru_items), len(ua_items))
        
        for i in range(min_len):
            # Из RU: ключ (первый span/th или текст до ':')
            ru_text = ru_items[i].get_text(strip=True)
            ru_key = ru_text.split(':')[0].strip() if ':' in ru_text else ru_text

            # Из UA: значение (второй span/td или текст после ':')
            ua_text = ua_items[i].get_text(strip=True)
            ua_val = ua_text.split(':')[-1].strip() if ':' in ua_text else ua_text

            if ru_key and ua_val:
                specs[ru_key] = ua_val  # Ключ из RU, значение из UA

        logger.debug(f"Fallback: извлечено характеристик: {len(specs)}")
        return specs

    async def parse(self, ua_url: str) -> Dict:
        """
        Парсинг с кешированием для оптимизации повторных запросов.
        
        Args:
            ua_url: URL украинской версии страницы
            
        Returns:
            Dict: Полная информация о продукте
        """
        cache_key = ua_url
        
        # Проверяем кеш
        if cache_key in self._parse_cache:
            self._cache_hits += 1
            logger.info(f"✅ Кеш хит: {ua_url}")
            return self._parse_cache[cache_key]
        
        self._cache_misses += 1
        
        # Парсим
        ua_html, ru_html = await self.fetch_html(ua_url)
        parsed_data = self.parse_product_info(ua_html, ru_html)
        
        # Кешируем
        self._parse_cache[cache_key] = parsed_data
        
        logger.info(f"📊 Кеш статистика: {self._cache_hits} хитов, {self._cache_misses} миссов")
        
        return parsed_data

    def parse_product_info(self, ua_html: str, ru_html: str) -> Dict:
        """
        Полный парсинг продукта: название, описание, характеристики, состав набора.
        
        Args:
            ua_html: HTML украинской версии
            ru_html: HTML русской версии
            
        Returns:
            Dict: Полная информация о продукте
        """
        soup_ua = BeautifulSoup(ua_html, 'html.parser')
        soup_ru = BeautifulSoup(ru_html, 'html.parser')
        
        # Парсинг названия
        title_ua = self._extract_title(soup_ua)
        title_ru = self._extract_title(soup_ru)
        
        # Парсинг описания
        description_ua = self._extract_description(soup_ua)
        description_ru = self._extract_description(soup_ru)
        
        # Парсинг характеристик и состава
        specs = self.parse_characteristics(ua_html, ru_html)
        bundle = self.parse_bundle(ua_html, ru_html)
        
        return {
            'title_ua': title_ua,
            'title_ru': title_ru,
            'description_ua': description_ua,
            'description_ru': description_ru,
            'specs': specs,
            'bundle': bundle
        }
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлекает название продукта."""
        selectors = ['h1', '.product-title', '.title', '.product-name']
        for selector in selectors:
            title_tag = soup.select_one(selector)
            if title_tag:
                return title_tag.get_text(strip=True)
        return ''
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Извлекает описание продукта."""
        selectors = ['.description', '.product-description', '.content', 'p']
        for selector in selectors:
            desc_tag = soup.select_one(selector)
            if desc_tag:
                return desc_tag.get_text(strip=True)
        return ''
    
    async def _translate_title_if_needed(self, title: str, target_locale: str) -> str:
        """
        Переводит название если языки не совпадают
        
        Args:
            title: Исходное название
            target_locale: Целевая локаль ('ru' или 'ua')
            
        Returns:
            str: Переведенное или исходное название
        """
        if not title:
            return title
            
        # Определяем язык исходного названия
        detected_lang = self.language_validator.detect_language(title)
        logger.info(f"🔍 Язык исходного названия: {detected_lang}")
        
        # Переводим если языки не совпадают
        if target_locale == 'ru' and detected_lang == 'ua':
            logger.info(f"🔄 ПЕРЕВОД НАЗВАНИЯ: UA → RU")
            logger.info(f"   Исходное: {title}")
            
            try:
                translated_title = await self.translator.translate_text(title, target_lang='ru')
                logger.info(f"   Переведено: {translated_title}")
                
                # ⚠️ КРИТИЧНО: Проверяем и исправляем капитализацию
                if translated_title and len(translated_title) > 0:
                    if translated_title[0].islower():
                        logger.warning(f"⚠️ Название начинается с маленькой буквы: {translated_title}")
                        translated_title = translated_title[0].upper() + translated_title[1:]
                        logger.info(f"✅ Исправлено: {translated_title}")
                
                # Валидация перевода
                translated_lang = self.language_validator.detect_language(translated_title)
                if translated_lang != 'ru':
                    logger.error(f"❌ Перевод не прошел валидацию: язык {translated_lang}")
                    # Возвращаем исходное название если перевод не удался
                    return title
                
                return translated_title
                
            except Exception as e:
                logger.error(f"❌ Ошибка перевода названия: {e}")
                return title
                
        elif target_locale == 'ua' and detected_lang == 'ru':
            logger.info(f"🔄 ПЕРЕВОД НАЗВАНИЯ: RU → UA")
            logger.info(f"   Исходное: {title}")
            
            try:
                translated_title = await self.translator.translate_text(title, target_lang='ua')
                logger.info(f"   Переведено: {translated_title}")
                
                # ⚠️ КРИТИЧНО: Проверяем и исправляем капитализацию
                if translated_title and len(translated_title) > 0:
                    if translated_title[0].islower():
                        logger.warning(f"⚠️ Название начинается с маленькой буквы: {translated_title}")
                        translated_title = translated_title[0].upper() + translated_title[1:]
                        logger.info(f"✅ Исправлено: {translated_title}")
                
                # Валидация перевода
                translated_lang = self.language_validator.detect_language(translated_title)
                if translated_lang != 'ua':
                    logger.error(f"❌ Перевод не прошел валидацию: язык {translated_lang}")
                    # Возвращаем исходное название если перевод не удался
                    return title
                
                return translated_title
                
            except Exception as e:
                logger.error(f"❌ Ошибка перевода названия: {e}")
                return title
        else:
            logger.info(f"✅ Название уже на правильном языке ({detected_lang})")
            return title
    
    async def get_translated_title(self, ua_html: str, ru_html: str, locale: str) -> str:
        """
        Получает переведенное название для указанной локали
        
        Args:
            ua_html: HTML украинской версии
            ru_html: HTML русской версии  
            locale: Целевая локаль ('ru' или 'ua')
            
        Returns:
            str: Название на правильном языке
        """
        if locale == 'ru':
            # Для русской локали используем русскую версию или переводим украинскую
            soup_ru = BeautifulSoup(ru_html, 'html.parser')
            title_ru = self._extract_title(soup_ru)
            
            if title_ru:
                return await self._translate_title_if_needed(title_ru, 'ru')
            else:
                # Если русской версии нет, переводим украинскую
                soup_ua = BeautifulSoup(ua_html, 'html.parser')
                title_ua = self._extract_title(soup_ua)
                return await self._translate_title_if_needed(title_ua, 'ru')
                
        else:  # locale == 'ua'
            # Для украинской локали используем украинскую версию или переводим русскую
            soup_ua = BeautifulSoup(ua_html, 'html.parser')
            title_ua = self._extract_title(soup_ua)
            
            if title_ua:
                return await self._translate_title_if_needed(title_ua, 'ua')
            else:
                # Если украинской версии нет, переводим русскую
                soup_ru = BeautifulSoup(ru_html, 'html.parser')
                title_ru = self._extract_title(soup_ru)
                return await self._translate_title_if_needed(title_ru, 'ua')
