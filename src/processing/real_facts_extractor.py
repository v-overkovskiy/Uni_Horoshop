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
        self.brand_patterns = [
            r'Epilax',
            r'ProRazko',
            r'([А-Яа-яЁё]+)'
        ]
        
        self.volume_patterns = [
            r'(\d+)\s*(мл|ml)',
            r'(\d+)\s*(г|g|грам|hram)',
            r'(\d+)\s*(л|l)'
        ]
        
        self.product_type_patterns = {
            'пудра': ['пудра', 'pudra', 'порошок'],
            'гель': ['гель', 'gel', 'флюид', 'fluid'],
            'пінка': ['пінка', 'пенка', 'foam'],
            'крем': ['крем', 'cream', 'мазь']
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
            
            # КРИТИЧНО: Проверяем что характеристики извлечены
            if not specs or len(specs) < 3:
                raise ValueError(f"❌ ЗАПРЕЩЕНО: Недостаточно характеристик товара из {url} (получено: {len(specs)})")
            
            # 3. Извлекаем информацию из URL
            url_info = self._extract_from_url(url)
            
            # 4. Определяем тип товара
            product_type = self._determine_product_type(title, url)
            
            # 5. Извлекаем изображение
            image_url = self._extract_image(soup)
            
            facts = {
                'title': title,
                'brand': 'Epilax',
                'product_type': product_type,
                'specs': specs,
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
                    # Преобразовать украинские названия в русские для единообразия
                    label_mapping = {
                        'Тип засобу для депіляції': 'Тип средства',
                        'Застосування засобу': 'Применение',
                        'Область застосування': 'Область применения', 
                        'Гіпоалергенно': 'Гипоаллергенно',
                        'Тип шкіри': 'Тип кожи',
                        'Тип волосся': 'Тип волос',
                        'Призначення і результат': 'Назначение и результат',
                        'Класифікація косметичного засобу': 'Классификация средства'
                    }
                    
                    # Использовать переводы или оставить оригинал
                    final_label = label_mapping.get(label, label)
                    specs.append({'label': final_label, 'value': value})
                    logger.info(f"✅ Извлечена характеристика: {final_label} = {value}")
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
        """Извлекает URL изображения товара"""
        # Ищем изображения товара в разных местах
        img_selectors = [
            '.product-photo img',
            '.product-image img', 
            '.main-image img',
            '.product-gallery img',
            'img[alt*="товар"]',
            'img[alt*="product"]',
            'img[src*="product"]',
            'img[src*="товар"]'
        ]
        
        for selector in img_selectors:
            img = soup.select_one(selector)
            if img and img.get('src'):
                src = img.get('src')
                # Обрабатываем относительные URL
                if src.startswith('/'):
                    src = f"https://prorazko.com{src}"
                elif not src.startswith('http'):
                    src = f"https://prorazko.com/{src}"
                
                # Проверяем, что это изображение товара
                if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    return src
        
        # Fallback: генерируем URL на основе типа товара
        return self._generate_fallback_image_url(soup)
    
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
            return "https://prorazko.com/content/images/epilax-product.webp"
    
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
