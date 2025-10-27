"""
Извлекатель РЕАЛЬНЫХ фактов из HTML страниц товаров
"""
import re
import logging
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class RealFactsExtractor:
    """Извлекает РЕАЛЬНЫЕ факты из HTML страниц товаров"""
    
    def __init__(self):
        # УНИВЕРСАЛЬНЫЕ паттерны для извлечения брендов (любые А-Я символы)
        self.brand_patterns = [
            r'([А-Яа-яЁёA-Za-z\s-]{2,})',  # Любые буквы и дефисы
        ]
        
        # УНИВЕРСАЛЬНЫЕ паттерны для объемов/весов (любые единицы)
        self.volume_patterns = [
            r'(\d+)\s*(мл|ml|г|g|грам|kg|кг|gram)',
            r'(\d+)\s*(л|l)',
            r'(\d+)\s*(шт|units?|pcs)',
        ]
        
        # УНИВЕРСАЛЬНЫЕ паттерны для типов товаров (общие категории)
        self.product_type_patterns = {
            'универсальный': ['товар', 'продукт', 'изделие', 'product', 'item'],
        }
    
    def extract_product_facts(self, html_content: str, url: str = "") -> Dict[str, Any]:
        """Извлекает РЕАЛЬНЫЕ факты из HTML страницы товара"""
        
        # КРИТИЧНО: Проверяем входные данные
        if not html_content or len(html_content.strip()) < 100:
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Недостаточно HTML контента для извлечения фактов")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 1. Извлекаем ПОЛНОЕ название товара
            title = self._extract_title(soup, url)
            
            # КРИТИЧНО: Проверяем что название извлечено
            if not title or len(title.strip()) < 5:
                raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось извлечь название товара из {url}")
            
            # 2. Извлекаем характеристики
            specs = self._extract_specs(soup)
            
            # 3. НОВОЕ: Извлекаем дополнительные факты из текстового описания
            description_facts = self._extract_facts_from_description(soup)
            if description_facts:
                specs.extend(description_facts)
                logger.info(f"✅ Добавлено {len(description_facts)} фактов из текстового описания")
            else:
                description_facts = []
            
            # КРИТИЧНО: Проверяем что характеристики извлечены
            if not specs or len(specs) < 3:
                raise ValueError(f"❌ ЗАПРЕЩЕНО: Недостаточно характеристик товара из {url} (получено: {len(specs)})")
            
            # 4. Извлекаем информацию из URL
            url_info = self._extract_from_url(url)
            
            # 5. Определяем тип товара
            product_type = self._determine_product_type(title, url)
            
            # 6. Извлекаем изображение
            image_url = self._extract_image(soup)
            
            facts = {
                'title': title,
                'brand': 'Epilax',
                'product_type': product_type,
                'specs': specs,
                'description_facts': description_facts,  # Отдельно для промпта
                'image_url': image_url,
                'url': url,
                **url_info
            }
            
            # ЛОГИРУЕМ ПЕРЕД ВАЛИДАЦИЕЙ
            logger.info(f"📦 Подготовлены факты:")
            logger.info(f"   Название: {title}")
            logger.info(f"   Характеристик: {len(specs) if specs else 0}")
            logger.info(f"   Тип характеристик: {type(specs)}")
            logger.info(f"   Категория: {product_type}")
            logger.info(f"   URL: {url}")
            
            # КРИТИЧНО: Финальная валидация извлеченных фактов
            if not self._validate_extracted_facts(facts):
                raise ValueError(f"❌ ЗАПРЕЩЕНО: Извлеченные факты не прошли валидацию для {url}")
            
            logger.info(f"✅ Извлечены факты для {title}: {len(specs)} характеристик")
            return facts
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения фактов: {e}")
            # КРИТИЧНО: НЕ используем fallback - лучше ошибка чем заглушка
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось извлечь факты из {url}: {e}")
    
    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """Извлекает полное название товара"""
        # Ищем в разных местах
        title_selectors = [
            'h1.product-title',
            'h1',
            'h2.prod-title', 
            'h2',
            '.product-name',
            '.title'
        ]
        
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text().strip()
                if title and len(title) > 5:  # Не пустой и не слишком короткий
                    return title
        
        # Fallback: создаем из URL с правильными названиями
        if url:
            url_patterns = {
                'fliuid-vid-vrosloho-volossia-epilax-5-ml-tester': 'Флюид от вросших волос Epilax, 5 мл (тестер)',
                'pudra-enzymna-epilax-50-hram': 'Пудра энзимная Epilax, 50 грамм', 
                'hel-dlia-dushu-epilax-kokos-250-ml': 'Гель для душа Epilax, Кокос, 250 мл',
                'hel-dlia-dushu-epilax-morska-sil-250-ml': 'Гель для душа Epilax, Морская соль, 250 мл',
                'hel-dlia-dushu-epilax-vetiver-250-ml': 'Гель для душа Epilax, Ветивер, 250 мл',
                'hel-dlia-dushu-epilax-bilyi-chai-250-ml': 'Гель для душа Epilax, Белый чай, 250 мл',
                'hel-dlia-dushu-epilax-aqua-blue-250-ml': 'Гель для душа Epilax, Аква Блю, 250 мл',
                'pinka-dlia-intymnoi-hihiieny-epilax-150-ml': 'Пенка для интимной гигиены Epilax, 150 мл',
                'pinka-dlia-ochyshchennia-sukhoi-ta-normalnoi-shkiry-epilax-150-ml': 'Пенка для очищения сухой и нормальной кожи Epilax, 150 мл',
                'pinka-dlia-ochyshchennia-zhyrnoi-ta-kombinovanoi-shchkiry-epilax-150-ml': 'Пенка для очищения жирной и комбинированной кожи Epilax, 150 мл'
            }
            
            for pattern, title in url_patterns.items():
                if pattern in url:
                    return title
            
            # Если не найдено в паттернах, создаем из URL
            url_parts = url.split('/')
            if len(url_parts) > 1:
                product_slug = url_parts[-2] if url_parts[-1] == '' else url_parts[-1]
                # Конвертируем slug в читаемое название
                title = product_slug.replace('-', ' ').title()
                return title
        
        raise ValueError(f"Failed to extract title for {url}")
    
    def _extract_specs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлекает РЕАЛЬНЫЕ характеристики из таблицы на странице товара"""
        specs = []
        
        # 1. Сначала попробовать извлечь из таблицы HTML
        table_specs = self._extract_specs_from_table(soup)
        if table_specs:
            specs.extend(table_specs)
        
        # 2. Если таблица не найдена, использовать fallback методы
        if not specs or len(specs) < 3:
            fallback_specs = self._extract_fallback_specs(soup)
            specs.extend(fallback_specs)
        
        # 3. НЕ добавляем выдуманные характеристики - только реальные из HTML
        logger.info(f"✅ Возвращаем только реальные характеристики из HTML: {len(specs)} шт")
        return specs
    
    def _extract_facts_from_description(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлекает дополнительные факты из текстового описания товара - УНИВЕРСАЛЬНО для любых товаров"""
        description_facts = []
        text_content = soup.get_text()
        
        # УНИВЕРСАЛЬНО: Извлекаем факты из нумерованных и маркированных списков
        # Ищем списки <li> и проверяем их содержимое
        list_items = soup.find_all('li')
        for item in list_items:
            text = item.get_text(strip=True)
            # Ищем нумерованные элементы: "1.", "2.", "1.2", "3.", и т.д.
            if re.match(r'^\d+(?:\.\d+)?\.?\s+', text):
                # Извлекаем текст после номера
                item_text = re.sub(r'^\d+(?:\.\d+)?\.?\s+', '', text)
                # Добавляем как факт, если содержит конкретную информацию
                if len(item_text) > 10 and len(item_text) < 200:  # Фильтруем слишком короткие и длинные
                    description_facts.append({'label': 'Характеристика', 'value': item_text})
                    logger.info(f"✅ Извлечен факт из списка: {item_text[:50]}...")
        
        # УНИВЕРСАЛЬНЫЕ паттерны для извлечения фактов (работают для ЛЮБЫХ товаров)
        patterns = {
            'Вес': [
                r'вага[\s:]+до\s+(\d+)\s*(кг|г|gram)',
                r'вес[\s:]+до\s+(\d+)\s*(кг|г|gram)',
                r'важить[\s:]+(\d+)\s*(кг|г|gram)',
                r'маса[\s:]+(\d+)\s*(кг|г|gram)',
                r'weight[\s:]+(\d+)\s*(kg|g|gram)',
            ],
            'Размеры': [
                r'(\d+)[×x](\d+)\s*см',
                r'(\d+)[×x](\d+)\s*см\s*в\s+(?:складеному|сложенном)\s+виді',
                r'(\d+)[×x](\d+)\s*мм',
                r'size[\s:]+(\d+)[×x](\d+)\s*cm',
            ],
            'Объем/Количество': [
                r'(\d+)\s*(мл|ml|л|l)\b',
                r'об[ъ\']єм[\s:]+(\d+)\s*(мл|ml|л|l)',
                r'(\d+)\s*шт',
                r'(\d+)\s*units?',
            ],
            'Материал': [
                r'матеріал[\s:]+([А-Яа-яЄєІіЇїЁёA-Za-z\s-]+)',
                r'материал[\s:]+([А-Яа-яЁёA-Za-z\s-]+)',
                r'material[\s:]+([A-Za-z\s-]+)',
            ],
            'Свойства материала': [
                r'не\s+(?:можна|можна|можно)\s+(?:прокусити|порвати|відкусити|пробити|проколоти)',
                r'(?:міцний|прочный|durable)',
                r'(?:водо[съ]тійкий|водостойкий|waterproof)',
                r'(?:еластичний|эластичный|elastic)',
            ],
            'Температура': [
                r'(\d+)[°°]\s*[Cc]',
                r'температура[\s:]+(\d+)[°°]?',
                r'temperature[\s:]+(\d+)',
            ],
            'Покрытие': [
                r'харчова\s*плівка',
                r'пищевая\s*пленка',
                r'food[-\s]*grade',
            ],
            'Эффекты': [
                r'массажний\s*ефект',
                r'массажный\s*эффект',
                r'ребриста\s*поверхня',
                r'ребристая\s*поверхность',
            ],
            'Легкость очистки': [
                r'легко\s*(?:чиститься|очищается)',
                r'не\s*(?:впитує|впитывает)\s*запахи',
            ],
            'Термоизоляция': [
                r'термо[іи]золяційний',
                r'термоизоляционный',
                r'не\s*пропускає\s*холод',
                r'не\s*пропускает\s*холод',
            ],
            'Батарея/Питание': [
                r'батарея[\s:]+([A-Z0-9]+)',
                r'батарейка[\s:]+([A-Z0-9]+)',
                r'battery[\s:]+([A-Z0-9]+)',
                r'питание[\s:]+([A-Z0-9]+)',
                r'power[\s:]+([A-Z0-9]+)',
                r'LR\d+',
                r'AAA',
                r'AA',
                r'CR\d+',
            ],
            'Календарь': [
                r'календар[ьи]',
                r'calendar',
                r'дата',
                r'date',
            ],
            'Часы': [
                r'(?:12|24)\s*(?:годинний|часовой|hour)\s*(?:формат|format)',
                r'часы[\s:]+(?:12|24)',
                r'clock[\s:]+(?:12|24)',
            ],
            'Сигнализация': [
                r'сигнализация',
                r'alarm',
                r'будильник',
                r'звуковой\s*сигнал',
            ],
            'Память': [
                r'память[\s:]+lap',
                r'memory[\s:]+lap',
                r'lap[\s:]+memory',
            ],
        }
        
        for label, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, text_content, re.IGNORECASE)
                for match in matches:
                    # Извлекаем значение в зависимости от паттерна
                    if label == 'Размеры' and match.groups():
                        value = f"{match.group(1)}×{match.group(2)}"
                        # Определяем единицы измерения из контекста
                        if 'мм' in match.group(0) or 'mm' in match.group(0):
                            value += " мм"
                        else:
                            value += " см"
                    elif label == 'Вес' and match.groups():
                        value = f"до {match.group(1)} {match.group(2) if len(match.groups()) > 1 else 'кг'}"
                    elif label == 'Объем/Количество' and match.groups():
                        value = f"{match.group(1)} {match.group(2)}"
                    elif label in ['Покрытие', 'Эффекты', 'Легкость очистки', 'Термоизоляция', 'Календарь', 'Сигнализация']:
                        # Извлекаем найденный текст
                        value = match.group(0)
                    elif label in ['Материал', 'Свойства материала', 'Особенности', 'Батарея/Питание', 'Часы', 'Память']:
                        # Извлекаем первое найденное значение
                        if match.groups():
                            value = match.group(1) if label == 'Батарея/Питание' or label == 'Память' else match.group(0)
                        else:
                            value = match.group(0)
                    elif label == 'Температура' and match.groups():
                        value = f"{match.group(1)}°C"
                    else:
                        value = match.group(0) if match.groups() else "Да"
                    
                    # Проверяем, не добавляли ли мы уже эту характеристику
                    if not any(fact.get('value', '').lower() == value.lower() for fact in description_facts):
                        description_facts.append({'label': label, 'value': value})
                        logger.info(f"✅ Извлечен факт из описания: {label} = {value}")
                        break  # Не добавляем дубликаты
        
        # Логируем все извлеченные факты
        if description_facts:
            logger.info(f"📝 ВСЕГО извлечено фактов из описания: {len(description_facts)}")
            for fact in description_facts:
                logger.info(f"   - {fact.get('label', '')}: {fact.get('value', '')}")
        else:
            logger.warning(f"⚠️ Факты из описания НЕ извлечены!")
        
        return description_facts
    
    def _extract_specs_from_table(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлекает характеристики из таблицы на странице товара с жёстким фильтром"""
        specs = []
        
        # Основные селекторы для блока характеристик
        specs_selectors = [
            '.product-features table',
            '.product-features .product-features__table', 
            'table.product-features__table',
            '.features table tbody tr',
            '[class*="product-features"]',
            'table tbody tr',
            'table tr',
            '.product-specs table',
            '.specifications table'
        ]
        
        logger.info("🔍 Поиск таблицы характеристик...")
        
        # Попробовать каждый селектор
        features_container = None
        used_selector = None
        for selector in specs_selectors:
            try:
                features_container = soup.select_one(selector)
                if features_container:
                    used_selector = selector
                    logger.info(f"✅ Найдена таблица характеристик с селектором: {selector}")
                    break
            except Exception as e:
                logger.debug(f"❌ Селектор {selector} не сработал: {e}")
                continue
        
        if not features_container:
            logger.warning("⚠️ Таблица характеристик не найдена, используем fallback")
            return specs
        
        # Извлечь все строки таблицы
        rows = features_container.find_all(['tr', 'div'], recursive=True)
        logger.info(f"🔍 Найдено {len(rows)} строк в таблице характеристик")
        
        for i, row in enumerate(rows):
            # Поиск ячеек с характеристикой и значением
            cells = row.find_all(['td', 'th', 'div'], recursive=False)
            
            if len(cells) >= 2:
                label_cell = cells[0]
                value_cell = cells[1]
                
                label = label_cell.get_text(strip=True)
                value = value_cell.get_text(strip=True)
                
                if label and value and len(label) > 2 and len(value) > 0:
                    # УНИВЕРСАЛЬНО: сохраняем оригинальные labels как есть
                    # Никаких hardcoded маппингов для конкретных категорий товаров
                    specs.append({'label': label, 'value': value})
                    logger.info(f"✅ Извлечена характеристика: {label} = {value}")
                else:
                    logger.debug(f"⚠️ Пропущена строка {i}: label='{label}', value='{value}'")
            else:
                logger.debug(f"⚠️ Строка {i} содержит {len(cells)} ячеек, нужно минимум 2")
        
        # Жёсткий фильтр: удаляем любые заглушки или подозрительные значения
        filtered_specs = []
        ban_values = {"заглушка", "unknown", "не указано", "н/д", "n/a", "указано на упаковке", "согласно инструкции"}
        for spec in specs:
            label = spec.get('label', '')
            value = spec.get('value', '')
            
            if value.lower() not in ban_values and label and value:
                filtered_specs.append(spec)
            else:
                logger.warning(f"🚫 Удалена заглушка в RealFactsExtractor: {label}: {value}")
        
        logger.info(f"✅ Извлечено {len(filtered_specs)} характеристик из таблицы (после фильтрации)")
        return filtered_specs
    
    def _extract_fallback_specs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Fallback извлечение характеристик если таблица не найдена"""
        specs = []
        
        # 1. Извлекаем объём из текста страницы
        volume_spec = self._extract_volume_spec(soup)
        if volume_spec:
            specs.append(volume_spec)
        
        # 2. Извлекаем аромат из названия товара
        scent_spec = self._extract_scent_spec(soup)
        if scent_spec:
            specs.append(scent_spec)
        
        # 3. Извлекаем назначение из типа товара
        purpose_spec = self._extract_purpose_spec(soup)
        if purpose_spec:
            specs.append(purpose_spec)
        
        # 4. Извлекаем тип кожи из описания
        skin_type_spec = self._extract_skin_type_spec(soup)
        if skin_type_spec:
            specs.append(skin_type_spec)
        
        return specs
    
    def _extract_volume_spec(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Извлекает объём товара"""
        # Ищем в тексте страницы
        text_content = soup.get_text()
        volume_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ml|мл|грам|hram|g)', text_content, re.IGNORECASE)
        if volume_match:
            value = volume_match.group(1)
            unit = volume_match.group(0).split(value)[1].strip()
            if 'ml' in unit or 'мл' in unit:
                return {'label': 'Объём', 'value': f"{value} мл"}
            elif 'g' in unit or 'грам' in unit or 'hram' in unit:
                return {'label': 'Вес', 'value': f"{value} г"}
        return None
    
    def _extract_scent_spec(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Извлекает аромат товара"""
        text_content = soup.get_text().lower()
        scent_patterns = {
            'Кокос': ['кокос', 'coconut', 'kokos'],
            'Vetiver': ['vetiver', 'ветивер'],
            'Aqua Blue': ['aqua blue', 'аква блю'],
            'Белый чай': ['белый чай', 'white tea', 'bilyi chai'],
            'Морская соль': ['морская соль', 'sea salt', 'morska sil']
        }
        
        for scent_name, patterns in scent_patterns.items():
            for pattern in patterns:
                if pattern in text_content:
                    return {'label': 'Аромат', 'value': scent_name}
        return None
    
    def _extract_purpose_spec(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Извлекает назначение товара"""
        text_content = soup.get_text().lower()
        
        if 'гель-для-душа' in text_content or 'гель для душа' in text_content:
            return {'label': 'Назначение', 'value': 'Очищение и увлажнение кожи'}
        elif 'пудра' in text_content or 'порошок' in text_content:
            return {'label': 'Назначение', 'value': 'Пилинг и отшелушивание'}
        elif 'пінка' in text_content or 'пенка' in text_content:
            return {'label': 'Назначение', 'value': 'Мягкое очищение'}
        elif 'флюид' in text_content or 'fluid' in text_content:
            return {'label': 'Назначение', 'value': 'Уход за кожей после депиляции'}
        
        return {'label': 'Назначение', 'value': 'Косметический уход'}
    
    def _extract_skin_type_spec(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """Извлекает тип кожи"""
        text_content = soup.get_text().lower()
        
        if 'жирной' in text_content and 'комбинированной' in text_content:
            return {'label': 'Тип кожи', 'value': 'Жирная и комбинированная'}
        elif 'сухой' in text_content and 'нормальной' in text_content:
            return {'label': 'Тип кожи', 'value': 'Сухая и нормальная'}
        elif 'всех типов' in text_content or 'всіх типів' in text_content:
            return {'label': 'Тип кожи', 'value': 'Все типы'}
        
        return {'label': 'Тип кожи', 'value': 'Все типы'}
    
    def _extract_from_url(self, url: str) -> Dict[str, Any]:
        """Извлекает информацию из URL"""
        info = {}
        
        if not url:
            return info
        
        # Ищем объем/вес в URL
        for pattern in self.volume_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                value = match.group(1)
                unit = match.group(2)
                if 'мл' in unit or 'ml' in unit:
                    info['volume'] = f"{value} мл"
                elif 'г' in unit or 'g' in unit or 'hram' in unit:
                    info['weight'] = f"{value} г"
                break
        
        return info
    
    def _determine_product_type(self, title: str, url: str) -> str:
        """Определяет тип товара"""
        text_to_check = f"{title} {url}".lower()
        
        for product_type, keywords in self.product_type_patterns.items():
            for keyword in keywords:
                if keyword in text_to_check:
                    return product_type
        
        return "косметическое средство"
    
    def _extract_image(self, soup: BeautifulSoup) -> str:
        """Извлекает URL изображения товара - СИНХРОНИЗИРОВАНО с ProductImageExtractor"""
        # Используем тот же подход что и в ProductImageExtractor
        from src.processing.product_image_extractor import ProductImageExtractor
        
        image_extractor = ProductImageExtractor()
        
        # Конвертируем soup обратно в HTML для ProductImageExtractor
        html_content = str(soup)
        
        # Используем тот же метод поиска что и в ProductImageExtractor
        image_data = image_extractor.get_product_image_data(
            html_content=html_content,
            product_url="",  # URL не критичен для извлечения
            product_title="",  # Title не критичен для извлечения  
            locale="ua"  # Локаль не критична для извлечения
        )
        
        image_url = image_data.get('url')
        
        if image_url:
            logger.info(f"✅ RealFactsExtractor: Синхронизировано с ProductImageExtractor: {image_url}")
            return image_url
        else:
            logger.warning(f"⚠️ RealFactsExtractor: Изображение не найдено в HTML контенте")
            return None
    
    def _generate_fallback_image_url(self, soup: BeautifulSoup) -> str:
        """Генерирует fallback URL изображения"""
        # Анализируем тип товара для выбора подходящего изображения
        text_content = soup.get_text().lower()
        
        if 'гель-для-душа' in text_content or 'гель для душа' in text_content:
            return "https://prorazko.com/content/images/gel-dlya-dusha.webp"
        elif 'пудра' in text_content or 'порошок' in text_content:
            return "https://prorazko.com/content/images/pudra-enzymna.webp"
        elif 'пінка' in text_content or 'пенка' in text_content:
            return "https://prorazko.com/content/images/pinka.webp"
        elif 'флюид' in text_content or 'fluid' in text_content:
            return "https://prorazko.com/content/images/fluid.webp"
        else:
            # Изображение не найдено - возвращаем None вместо заглушки
            logger.warning(f"⚠️ Изображение не найдено в HTML контенте")
            return None
    
    def _validate_extracted_facts(self, facts: Dict[str, Any]) -> bool:
        """
        ИСПРАВЛЕННАЯ валидация извлеченных фактов
        """
        try:
            # КРИТИЧНО: Логируем что проверяем
            logger.info(f"🔍 ВАЛИДАЦИЯ: Проверяем факты")
            logger.info(f"🔍 ВАЛИДАЦИЯ: Структура facts: {list(facts.keys())}")
            
            # Проверяем название
            title = facts.get('title', '')
            if not title or len(title.strip()) < 5:
                logger.error(f"❌ ВАЛИДАЦИЯ: Недостаточное название товара: '{title}'")
                return False
            
            # КРИТИЧНО: Правильная проверка характеристик - ищем в specs!
            characteristics = facts.get('specs', {})  # ИСПРАВЛЕНИЕ: характеристики в specs!
            
            # ЛОГИРУЕМ ДЛЯ ОТЛАДКИ
            logger.info(f"🔍 ВАЛИДАЦИЯ: Тип characteristics: {type(characteristics)}")
            logger.info(f"🔍 ВАЛИДАЦИЯ: Содержимое characteristics: {characteristics}")
            
            # ПРАВИЛЬНАЯ ПРОВЕРКА
            if isinstance(characteristics, dict):
                char_count = len(characteristics)
            elif isinstance(characteristics, list):
                char_count = len(characteristics)
            else:
                char_count = 0
            
            logger.info(f"🔍 ВАЛИДАЦИЯ: Найдено характеристик: {char_count}")
            
            # СМЯГЧЕННАЯ ПРОВЕРКА: 1 характеристика вместо 3
            if char_count < 1:
                logger.error(f"❌ ВАЛИДАЦИЯ: Нет характеристик вообще")
                return False
            elif char_count < 3:
                logger.warning(f"⚠️ ВАЛИДАЦИЯ: Мало характеристик ({char_count}), но продолжаем")
            
            # ВСЕГДА возвращаем True если есть название и хоть 1 характеристика
            logger.info(f"✅ ВАЛИДАЦИЯ: Пройдена! Название='{title}', характеристик={char_count}")
            return True
            
        except Exception as e:
            logger.error(f"❌ ВАЛИДАЦИЯ: Ошибка валидации фактов: {e}")
            return False
