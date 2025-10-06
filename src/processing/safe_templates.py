"""
Безопасные шаблоны для генерации контента без LLM
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SafeTemplates:
    """Генерация безопасного контента из проверенных фактов"""
    
    def __init__(self):
        self.templates = {
            'ru': {
                'note_buy': "В нашем интернет-магазине ProRazko можно <strong>купить {title}</strong> — быстрая доставка по Украине и гарантия качества.",
                'description': "{title}. {brand_info}{color_info}{pack_info}",
                'advantages': [
                    "Подходит для разных зон тела",
                    "Удобно в использовании", 
                    "Проверенный бренд",
                    "Качественные материалы",
                    "Быстрый эффект"
                ],
                'faq_questions': [
                    "Какой вес упаковки?",
                    "Какой цвет продукта?",
                    "Для каких зон подходит?",
                    "Как использовать продукт?",
                    "Какой бренд?"
                ]
            },
            'ua': {
                'note_buy': "У нашому інтернет-магазині ProRazko можна <strong>купити {title}</strong> — швидка доставка по Україні та гарантія якості.",
                'description': "{title}. {brand_info}{color_info}{pack_info}",
                'advantages': [
                    "Підходить для різних зон тіла",
                    "Зручно у використанні",
                    "Перевірений бренд", 
                    "Якісні матеріали",
                    "Швидкий ефект"
                ],
                'faq_questions': [
                    "Яка вага упаковки?",
                    "Який колір продукту?",
                    "Для яких зон підходить?",
                    "Як використовувати продукт?",
                    "Який бренд?"
                ]
            }
        }
    
    def render_note_buy(self, h1: str, locale: str = 'ua', specs: List[Dict[str, str]] = None) -> str:
        """Генерирует note-buy с улучшенным шаблоном"""
        from src.processing.enhanced_note_buy_generator import EnhancedNoteBuyGenerator
        
        generator = EnhancedNoteBuyGenerator()
        result = generator.generate_enhanced_note_buy(h1, locale)
        
        if result and result.get('content'):
            return result['content']
        else:
            # Fallback к старому методу
            from src.morph.case_engine import decline_title_for_buy

            # Проверяем заголовок на смешение локалей
            safe_title = self._get_safe_title(h1, locale, specs or [])

            # Склоняем название для винительного падежа
            declined_title = decline_title_for_buy(safe_title, locale)

            template = self.templates[locale]['note_buy']
            return template.format(title=declined_title)
    
    def _get_safe_title(self, h1: str, locale: str, specs: List[Dict[str, str]]) -> str:
        """Получает безопасное название товара для указанной локали"""
        from src.validation.locale_validator import LocaleValidator
        
        locale_validator = LocaleValidator()
        
        # Проверяем заголовок на смешение локалей
        if locale_validator.validate_locale_content(h1, locale):
            return h1
        
        # Если заголовок содержит смешение локалей, строим безопасное название из specs
        logger.warning(f"⚠️ Заголовок содержит смешение локалей для {locale}: {h1[:50]}...")
        return self._build_safe_name_from_specs(specs, locale, h1)
    
    def _build_safe_name_from_specs(self, specs: List[Dict[str, str]], locale: str, h1: str = "") -> str:
        """Строит безопасное название из характеристик с извлечением из заголовка"""
        if not specs and not h1:
            return "товар" if locale == 'ru' else "товар"
        
        # Словарь для быстрого поиска характеристик
        specs_dict = {}
        if specs:
            for spec in specs:
                key = spec.get('name', '') or spec.get('label', '')
                value = spec.get('value', '')
                if key.strip() and value.strip():
                    specs_dict[key.strip().lower()] = value.strip()
        
        # Строим название по приоритету
        parts = []
        
        # 1. Форма выпуска
        form = self._get_safe_form(specs_dict, locale)
        if not form or form in ["воск", "віск"]:
            # Если форма не найдена в specs, пытаемся определить по h1
            if h1:
                form = self._detect_form_from_title(h1, locale)
            else:
                form = "воск" if locale == 'ru' else "віск"
        
        if form:
            parts.append(form)
        
        # 2. Бренд - сначала из specs, потом из заголовка
        brand = self._get_safe_brand(specs_dict, locale)
        if not brand and h1:
            brand = self._extract_brand_from_title(h1, locale)
        if brand:
            parts.append(brand)
        
        # 3. Серия/тип - сначала из specs, потом из заголовка
        series = self._get_safe_series(specs_dict, locale)
        if not series and h1:
            series = self._extract_series_from_title(h1, locale)
        if series:
            parts.append(series)
        
        # 4. Объем/вес - сначала из specs, потом из заголовка
        volume = self._get_safe_volume(specs_dict, locale)
        if not volume and h1:
            volume = self._extract_volume_from_title(h1, locale)
        if volume:
            parts.append(volume)
        
        # Если ничего не нашли, собираем минимальное название
        if not parts:
            if h1:
                form = self._detect_form_from_title(h1, locale)
                return form
            return "воск" if locale == 'ru' else "віск"
        
        # Гарантируем минимальное название с объемом если есть
        result = " ".join(parts)
        if len(parts) == 1 and h1:  # Только форма найдена
            # Пытаемся добавить объем из заголовка
            volume = self._extract_volume_from_title(h1, locale)
            if volume:
                result = f"{result} {volume}"
        
        return result
    
    def _detect_form_from_title(self, h1: str, locale: str) -> str:
        """Определяет форму выпуска по названию товара"""
        h1_lower = h1.lower()
        
        # Определяем форму по ключевым словам в названии
        if 'картридж' in h1_lower or 'картрид' in h1_lower:
            return "воск в картридже" if locale == 'ru' else "віск в картриджі"
        elif 'банк' in h1_lower or 'баночк' in h1_lower or 'банці' in h1_lower:
            return "воск в банке" if locale == 'ru' else "віск в банці"
        elif 'гранул' in h1_lower:
            return "воск в гранулах" if locale == 'ru' else "віск в гранулах"
        elif 'пленк' in h1_lower or 'плівц' in h1_lower:
            return "воск в пленке" if locale == 'ru' else "віск в плівці"
        else:
            return "воск" if locale == 'ru' else "віск"
    
    def _get_safe_form(self, specs_dict: Dict[str, str], locale: str) -> str:
        """Получает безопасную форму выпуска"""
        form_keys = ['форма', 'форма выпуска', 'тип', 'вид', 'форма випуску', 'форма выпуска воска', 'форма випуску воску']
        
        for key in form_keys:
            for spec_key in specs_dict:
                if key in spec_key:
                    value = specs_dict[spec_key].lower()
                    
                    # Нормализуем форму выпуска
                    if 'картридж' in value or 'картрид' in value:
                        return "воск в картридже" if locale == 'ru' else "віск в картриджі"
                    elif 'банк' in value or 'баночк' in value:
                        return "воск в банке" if locale == 'ru' else "віск в банці"
                    elif 'гранул' in value:
                        return "воск в гранулах" if locale == 'ru' else "віск в гранулах"
                    elif 'пленк' in value:
                        return "воск в пленке" if locale == 'ru' else "віск в плівці"
        
        # Если не нашли форму в specs, пытаемся определить по названию товара
        # Это fallback для случаев, когда форма не указана в характеристиках
        return "воск" if locale == 'ru' else "віск"
    
    def _get_safe_brand(self, specs_dict: Dict[str, str], locale: str) -> str:
        """Получает безопасный бренд"""
        brand_keys = ['бренд', 'brand', 'производитель', 'марка']
        
        for key in brand_keys:
            for spec_key in specs_dict:
                if key in spec_key:
                    brand = specs_dict[spec_key].strip()
                    # Бренды обычно нейтральны по языку
                    return brand
        
        return ""
    
    def _get_safe_series(self, specs_dict: Dict[str, str], locale: str) -> str:
        """Получает безопасную серию/тип"""
        series_keys = ['серия', 'серия', 'линия', 'линія', 'коллекция', 'колекція', 'class', 'класс']
        
        for key in series_keys:
            for spec_key in specs_dict:
                if key in spec_key:
                    series = specs_dict[spec_key].strip()
                    # Серии обычно нейтральны по языку
                    return series
        
        return ""
    
    def _get_safe_volume(self, specs_dict: Dict[str, str], locale: str) -> str:
        """Получает безопасный объем/вес"""
        volume_keys = ['объем', 'об\'єм', 'вес', 'вага', 'масса', 'маса', 'weight', 'volume']
        
        for key in volume_keys:
            for spec_key in specs_dict:
                if key in spec_key:
                    volume = specs_dict[spec_key].strip()
                    # Объемы обычно нейтральны по языку (цифры + единицы)
                    return volume
        
        return ""
    
    def _extract_brand_from_title(self, h1: str, locale: str) -> str:
        """Извлекает бренд из заголовка"""
        h1_lower = h1.lower()
        
        # Известные бренды
        brands = ['simple use', 'italwax', 'prorazko', 'cleopatra', 'veet', 'sally hansen']
        
        for brand in brands:
            if brand in h1_lower:
                return brand.title()
        
        return ""
    
    def _extract_series_from_title(self, h1: str, locale: str) -> str:
        """Извлекает серию из заголовка"""
        h1_lower = h1.lower()
        
        # Проверяем конкретные паттерны
        if locale == 'ru':
            if 'золотая перлина' in h1_lower or 'золота перлина' in h1_lower:
                return 'Золотая перлина'
            elif 'королевская перлина' in h1_lower or 'королевская' in h1_lower:
                return 'Королевская перлина'
            elif 'орхидея' in h1_lower or 'orchidea' in h1_lower:
                return 'Орхидея'
            elif 'top line' in h1_lower:
                return 'Top Line'
        else:  # ua
            if 'золотая перлина' in h1_lower or 'золота перлина' in h1_lower:
                return 'Золота перлина'
            elif 'королівська перлина' in h1_lower or 'королівська' in h1_lower:
                return 'Королівська перлина'
            elif 'орхідея' in h1_lower or 'orchidea' in h1_lower:
                return 'Орхідея'
            elif 'top line' in h1_lower:
                return 'Top Line'
        
        return ""
    
    def _extract_volume_from_title(self, h1: str, locale: str) -> str:
        """Извлекает объем из заголовка"""
        import re
        
        # Ищем паттерны объема: 400 мл, 750 г, 1000 мл и т.д.
        volume_patterns = [
            r'(\d+)\s*мл',
            r'(\d+)\s*г',
            r'(\d+)\s*грам',
            r'(\d+)\s*кг',
            r'(\d+)\s*ml',
            r'(\d+)\s*g'
        ]
        
        for pattern in volume_patterns:
            match = re.search(pattern, h1.lower())
            if match:
                number = match.group(1)
                if 'мл' in pattern or 'ml' in pattern:
                    return f"{number} мл"
                elif 'г' in pattern or 'грам' in pattern or 'g' in pattern:
                    return f"{number} г"
                elif 'кг' in pattern:
                    return f"{number} кг"
        
        return ""
    
    def render_safe_description(self, facts: Dict[str, Any], locale: str = 'ua') -> str:
        """Генерирует безопасное описание из фактов"""
        template = self.templates[locale]['description']
        
        # Собираем информацию по частям
        parts = []
        
        # Бренд
        brand = facts.get('brand', '')
        brand_info = f"Бренд {brand}. " if brand else ""
        
        # Цвет
        color = facts.get('color', '')
        color_info = f"Цвет: {color}. " if color else ""
        
        # Упаковка
        pack = facts.get('pack', '')
        pack_info = f"Вес: {pack}. " if pack else ""
        
        return template.format(
            title=facts.get('title', ''),
            brand_info=brand_info,
            color_info=color_info,
            pack_info=pack_info
        ).strip()
    
    def render_safe_advantages(self, facts: Dict[str, Any], locale: str = 'ua', count: int = 3) -> List[str]:
        """Генерирует безопасные преимущества"""
        advantages = self.templates[locale]['advantages'].copy()
        
        # Добавляем специфичные преимущества на основе фактов
        if facts.get('brand'):
            brand_adv = f"Продукция бренда {facts['brand']}" if locale == 'ru' else f"Продукція бренду {facts['brand']}"
            advantages.insert(0, brand_adv)
        
        if facts.get('pack'):
            pack_adv = f"Удобная упаковка {facts['pack']}" if locale == 'ru' else f"Зручна упаковка {facts['pack']}"
            advantages.insert(1, pack_adv)
        
        return advantages[:count]
    
    def render_safe_faq(self, facts: Dict[str, Any], locale: str = 'ua', count: int = 4) -> List[Dict[str, str]]:
        """Генерирует безопасные FAQ"""
        questions = self.templates[locale]['faq_questions'].copy()
        faq = []
        
        for i, question in enumerate(questions[:count]):
            answer = self._generate_safe_answer(question, facts, locale)
            faq.append({
                'q': question,
                'a': answer
            })
        
        return faq
    
    def _generate_safe_answer(self, question: str, facts: Dict[str, Any], locale: str) -> str:
        """Генерирует безопасный ответ на вопрос"""
        question_lower = question.lower()
        
        if 'вес' in question_lower or 'вага' in question_lower:
            pack = facts.get('pack', '')
            return pack if pack else ("Не указано" if locale == 'ru' else "Не вказано")
        
        elif 'цвет' in question_lower or 'колір' in question_lower:
            color = facts.get('color', '')
            return color if color else ("Не указано" if locale == 'ru' else "Не вказано")
        
        elif 'зоны' in question_lower or 'зон' in question_lower:
            return ("Подходит для разных зон тела" if locale == 'ru' 
                   else "Підходить для різних зон тіла")
        
        elif 'использовать' in question_lower or 'використовувати' in question_lower:
            return ("Следуйте инструкциям на упаковке" if locale == 'ru'
                   else "Дотримуйтесь інструкцій на упаковці")
        
        elif 'бренд' in question_lower:
            brand = facts.get('brand', '')
            return brand if brand else ("Не указано" if locale == 'ru' else "Не вказано")
        
        else:
            return ("Информация уточняется" if locale == 'ru' 
                   else "Інформація уточнюється")
    
    def render_safe_blocks(self, h1: str, facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Генерирует все безопасные блоки"""
        from src.processing.fragment_renderer import ProductFragmentRenderer
        
        renderer = ProductFragmentRenderer()
        
        # Генерируем блоки
        specs = self._render_safe_specs(facts, locale)
        note_buy = self.render_note_buy(h1, locale, specs)
        description = self.render_safe_description(facts, locale)
        advantages = self.render_safe_advantages(facts, locale)
        faq = self.render_safe_faq(facts, locale)
        
        # Рендерим в HTML фрагменты
        return {
            'note_buy': note_buy,
            'title': h1,
            'description': renderer.render_description(description, locale),
            'advantages': renderer.render_advantages(advantages, locale),
            'faq': renderer.render_faq(faq, locale),
            'specs': renderer.render_specs(specs, locale)
        }
    
    def render_safe_blocks_from_llm(self, h1: str, llm_content: Dict[str, Any], locale: str, html: str = "") -> Dict[str, Any]:
        """Генерирует блоки из LLM контента с fallback для пропущенных полей"""
        from src.processing.fragment_renderer import ProductFragmentRenderer
        
        renderer = ProductFragmentRenderer()
        
        # Конвертируем LLM контент в формат для рендеринга
        description = llm_content.get('description', '')
        advantages = llm_content.get('advantages', [])
        faq = llm_content.get('faq', [])
        specs = llm_content.get('specs', [])
        
        # Генерируем note-buy с проверкой локали
        note_buy = self.render_note_buy(h1, locale, specs)
        
        # Нормализуем UA-контент
        if locale == 'ua':
            from src.validation.locale_validator import LocaleValidator
            locale_validator = LocaleValidator()
            description = locale_validator.normalize_ua_content(description)
        
        # Рендерим в HTML фрагменты (без fallback характеристик)
        return {
            'note_buy': note_buy,
            'title': h1,
            'description': renderer.render_description(description, locale),
            'advantages': renderer.render_advantages(advantages, locale),
            'faq': renderer.render_faq(faq, locale),
            'faq_data': faq,  # Добавляем сырые данные FAQ для JSON-LD
            'specs': renderer.render_specs(specs, locale),
            'photo_alt': self._get_photo_alt(h1, html)
        }
    
    def _add_fallback_specs(self, specs: List[Dict[str, str]], h1: str, locale: str) -> List[Dict[str, str]]:
        """Добавляет fallback характеристики для полей, которые LLM пропустил"""
        if not specs:
            specs = []
        
        # Проверяем какие поля уже есть
        existing_names = {spec.get('name', '').lower() for spec in specs}
        
        # Добавляем недостающие поля
        fallback_specs = []
        
        # Бренд
        if 'бренд' not in existing_names and 'brand' not in existing_names:
            fallback_specs.append({'name': 'Бренд', 'value': 'ItalWAX'})
        
        # Форма выпуска
        if 'форма' not in existing_names and 'форма выпуска' not in existing_names:
            if 'гранулах' in h1.lower():
                fallback_specs.append({'name': 'Форма выпуска', 'value': 'Гранулы'})
            elif 'картридж' in h1.lower():
                fallback_specs.append({'name': 'Форма выпуска', 'value': 'Картридж'})
        
        # Температура
        if 'температура' not in existing_names and 'temp' not in existing_names:
            fallback_specs.append({'name': 'Температура плавления', 'value': '40-42°C'})
        
        # Объединяем с существующими
        return specs + fallback_specs
    
    def _get_photo_alt(self, h1: str, html: str = "") -> str:
        """Извлекает hero-фото из галереи или og:image"""
        if not html:
            return "placeholder.jpg"
        
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1) Ищем активный слайд галереи
        img = soup.select_one('.tmGallery-item.swiper-slide-active img[gallery-image]')
        if img and img.get('src'):
            return self._absolutize_url(img['src'], html)
        
        # 2) Ищем первый слайд галереи
        if not img:
            img = soup.select_one('.tmGallery-item img[gallery-image]')
            if img and img.get('src'):
                return self._absolutize_url(img['src'], html)
        
        # 3) Ищем og:image
        og_image = soup.select_one('meta[property="og:image"]')
        if og_image and og_image.get('content'):
            return self._absolutize_url(og_image['content'], html)
        
        # 4) Ищем любые изображения товара
        product_images = soup.select('img[src*="product"], img[src*="item"], img[alt*="product"]')
        for img in product_images:
            if img.get('src') and not 'placeholder' in img.get('src', '').lower():
                return self._absolutize_url(img['src'], html)
        
        # 5) Ищем первое изображение в контенте
        content_img = soup.select_one('div.content img, .product-content img, main img')
        if content_img and content_img.get('src'):
            return self._absolutize_url(content_img['src'], html)
        
        return "placeholder.jpg"
    
    def _absolutize_url(self, url: str, html: str) -> str:
        """Преобразует относительный URL в абсолютный"""
        if url.startswith('http'):
            return url
        
        # Извлекаем базовый URL из HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        base_tag = soup.find('base')
        if base_tag and base_tag.get('href'):
            base_url = base_tag['href']
        else:
            # Пытаемся извлечь из meta или других источников
            base_url = "https://prorazko.com"
        
        if not base_url.endswith('/'):
            base_url += '/'
        
        if url.startswith('/'):
            return base_url.rstrip('/') + url
        else:
            return base_url + url
    
    def _render_safe_specs(self, facts: Dict[str, Any], locale: str) -> List[Dict[str, str]]:
        """Генерирует безопасные характеристики"""
        specs = []
        
        # Добавляем только безопасные характеристики
        safe_keys = ['brand', 'type', 'color', 'pack', 'category', 'application']
        
        for key in safe_keys:
            value = facts.get(key)
            if value:
                if locale == 'ru':
                    label_map = {
                        'brand': 'Бренд',
                        'type': 'Тип', 
                        'color': 'Цвет',
                        'pack': 'Вес',
                        'category': 'Категория',
                        'application': 'Применение'
                    }
                else:
                    label_map = {
                        'brand': 'Бренд',
                        'type': 'Тип',
                        'color': 'Колір', 
                        'pack': 'Вага',
                        'category': 'Категорія',
                        'application': 'Застосування'
                    }
                
                specs.append({
                    'label': label_map.get(key, key),
                    'value': value
                })
        
        return specs
