"""
Универсальный менеджер консистентности объёма
Извлекает разрешённые значения из specs и JSON-LD, нормализует единицы,
валидирует и ремонтирует текстовые блоки
"""

import re
import json
import logging
from typing import List, Dict, Set, Optional, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class VolumeManager:
    """Универсальный менеджер консистентности объёма"""
    
    def __init__(self, locale: str):
        self.locale = locale
        
        # Единицы измерения по локали (включаем массу для универсальности)
        self.volume_units = {
            'ru': ['мл', 'ml', 'литр', 'л', 'l', 'г', 'g', 'кг', 'kg'],
            'ua': ['мл', 'ml', 'літр', 'л', 'l', 'г', 'g', 'кг', 'kg']
        }
        
        self.mass_units = {
            'ru': ['грамм', 'г', 'g', 'килограмм', 'кг', 'kg'],
            'ua': ['грам', 'г', 'g', 'кілограм', 'кг', 'kg']
        }
        
        # Паттерны для извлечения объёма
        self.volume_patterns = {
            'ru': [
                r'объем[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'об\'ём[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'вместимость[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'ёмкость[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)'
            ],
            'ua': [
                r'об\'єм[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'объем[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'вмістимість[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'ємність[:\s]*(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)',
                r'(\d+(?:[.,]\d+)?)\s*([млmlлlгgкг]+)'
            ]
        }
        
        # Паттерны для извлечения массы
        self.mass_patterns = {
            'ru': [
                r'масса[:\s]*(\d+(?:[.,]\d+)?)\s*([гgкгkg]+)',
                r'вес[:\s]*(\d+(?:[.,]\d+)?)\s*([гgкгkg]+)',
                r'(\d+(?:[.,]\d+)?)\s*([гgкгkg]+)',
                r'(\d+(?:[.,]\d+)?)\s*г',
                r'(\d+(?:[.,]\d+)?)\s*кг',
                r'(\d+(?:[.,]\d+)?)\s*грамм',
                r'(\d+(?:[.,]\d+)?)\s*килограмм'
            ],
            'ua': [
                r'маса[:\s]*(\d+(?:[.,]\d+)?)\s*([гgкгkg]+)',
                r'вага[:\s]*(\d+(?:[.,]\d+)?)\s*([гgкгkg]+)',
                r'(\d+(?:[.,]\d+)?)\s*([гgкгkg]+)',
                r'(\d+(?:[.,]\d+)?)\s*г',
                r'(\d+(?:[.,]\d+)?)\s*кг',
                r'(\d+(?:[.,]\d+)?)\s*грам',
                r'(\d+(?:[.,]\d+)?)\s*кілограм'
            ]
        }
    
    def extract_allowed_volumes(self, html: str) -> Set[str]:
        """Извлекает разрешённые объёмы из specs и JSON-LD, исключая технические контексты"""
        allowed_volumes = set()
        
        if not html:
            return allowed_volumes
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Извлекаем из характеристик (ul.specs) - приоритетный источник
        specs_volumes = self._extract_from_specs(soup)
        allowed_volumes.update(specs_volumes)
        
        # 2. Извлекаем из JSON-LD additionalProperty
        jsonld_volumes = self._extract_from_jsonld(soup)
        allowed_volumes.update(jsonld_volumes)
        
        # 3. Извлекаем из заголовков характеристик
        header_volumes = self._extract_from_headers(soup)
        allowed_volumes.update(header_volumes)
        
        # 4. Дополнительная очистка от технических значений
        allowed_volumes = self._filter_technical_volumes(allowed_volumes)
        
        logger.info(f"Извлечены разрешённые объёмы для {self.locale}: {sorted(allowed_volumes)}")
        return allowed_volumes
    
    def _filter_technical_volumes(self, volumes: Set[str]) -> Set[str]:
        """Фильтрует технические объёмы (700л, 1000л и т.д.)"""
        filtered = set()
        
        for volume in volumes:
            # Извлекаем число и единицу
            match = re.search(r'(\d+(?:[.,]\d+)?)\s*([млmlлlгgкгkg]+)', volume, re.IGNORECASE)
            if not match:
                continue
                
            value = match.group(1)
            unit = match.group(2).lower()
            
            try:
                num_value = float(value.replace(',', '.'))
                
                # Фильтруем нереалистичные значения
                if unit in ['л', 'l'] and num_value > 99.9:
                    continue  # Исключаем 700л, 1000л и т.д.
                elif unit in ['г', 'g'] and num_value > 9999:
                    continue  # Исключаем очень большие веса
                elif unit in ['мл', 'ml'] and num_value > 9999:
                    continue  # Исключаем очень большие объёмы
                elif unit in ['кг', 'kg'] and num_value > 999:
                    continue  # Исключаем очень большие массы
                
                filtered.add(volume)
                
            except ValueError:
                # Если не можем распарсить число, оставляем как есть
                filtered.add(volume)
        
        return filtered
    
    def extract_allowed_masses(self, html: str) -> Set[str]:
        """Извлекает разрешённые массы из specs и JSON-LD, исключая технические контексты"""
        allowed_masses = set()
        
        if not html:
            return allowed_masses
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлекаем из specs
            specs_masses = self._extract_mass_from_specs(soup)
            allowed_masses.update(specs_masses)
            
            # Извлекаем из JSON-LD
            jsonld_masses = self._extract_mass_from_jsonld(soup)
            allowed_masses.update(jsonld_masses)
            
            # Фильтруем технические контексты
            filtered_masses = self._filter_technical_masses(allowed_masses)
            
            # Нормализуем единицы
            normalized_masses = set()
            for mass in filtered_masses:
                normalized = self._normalize_mass_unit(mass)
                if normalized:
                    normalized_masses.add(normalized)
            
            return normalized_masses
            
        except Exception as e:
            logger.warning(f"Ошибка извлечения массы: {e}")
            return set()
    
    def _extract_from_specs(self, soup: BeautifulSoup) -> Set[str]:
        """Извлекает объёмы из ul.specs, исключая технические контексты"""
        volumes = set()
        specs_ul = soup.select_one('ul.specs')
        
        if specs_ul:
            for li in specs_ul.find_all('li'):
                # Получаем чистый текст без HTML
                text = li.get_text().strip()
                
                # Пропускаем пустые элементы
                if not text:
                    continue
                
                # Проверяем, что это не технический контекст
                if self._is_technical_spec(text):
                    continue
                
                text_lower = text.lower()
                for pattern in self.volume_patterns[self.locale]:
                    matches = re.findall(pattern, text_lower, re.IGNORECASE)
                    for value, unit in matches:
                        normalized = self._normalize_volume(value, unit)
                        if normalized and self._is_realistic_volume(normalized):
                            volumes.add(normalized)
        
        return volumes
    
    def _is_technical_spec(self, text: str) -> bool:
        """Проверяет, является ли спецификация технической (не объём)"""
        text_lower = text.lower()
        
        # Если содержит объём, то это не техническая спецификация
        if any(keyword in text_lower for keyword in ['объем', 'об\'ём', 'объём', 'мл', 'л', 'литр', 'кг', 'грамм']):
            return False
        
        # Технические ключевые слова в спецификациях
        technical_keywords = [
            'px', 'pixel', 'размер', 'size', 'width', 'height',
            'url', 'http', 'https', 'www', '.com', '.ua', '.ru',
            'src', 'href', 'data-', 'class', 'id', 'style',
            'swiper', 'gallery', 'image', 'img', 'photo'
        ]
        
        # Проверяем наличие технических ключевых слов
        for keyword in technical_keywords:
            if keyword in text_lower:
                return True
        
        # Проверяем паттерны размеров (например, 700x700)
        if re.search(r'\d+x\d+', text_lower):
            return True
        
        return False
    
    def _is_portion_context(self, text: str, volume: str) -> bool:
        """Проверяет, является ли масса порционной (42 г как порция)"""
        text_lower = text.lower()
        volume_lower = volume.lower()
        
        # Контекстные маркеры для порций
        portion_markers = [
            'порция', 'пакет', 'доза', 'portion', 'порція', 'пакетик',
            'одна порция', 'одна доза', 'одна порція', 'одна доза',
            'вес порции', 'вес дозы', 'вага порції', 'вага дози',
            'масса порции', 'масса дозы', 'маса порції', 'маса дози',
            'упаковка содержит', 'упаковка містить', 'пакет содержит', 'пакет містить',
            'в упаковке', 'в упаковці', 'в пакете', 'в пакеті',
            'вес упаковки', 'вага упаковки', 'масса упаковки', 'маса упаковки',
            'вес пакета', 'вага пакета', 'масса пакета', 'маса пакета'
        ]
        
        # Проверяем, есть ли маркеры порций рядом с объёмом
        for marker in portion_markers:
            if marker in text_lower:
                # Проверяем, что объём находится в контексте порции
                context_start = max(0, text_lower.find(volume_lower) - 100)
                context_end = min(len(text_lower), text_lower.find(volume_lower) + len(volume_lower) + 100)
                context = text_lower[context_start:context_end]
                
                if marker in context:
                    return True
        
        return False
    
    def _is_realistic_volume(self, volume: str) -> bool:
        """Проверяет, является ли объём реалистичным"""
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*([млmlлlгgкгkg]+)', volume, re.IGNORECASE)
        if not match:
            return False
        
        value = match.group(1)
        unit = match.group(2).lower()
        
        try:
            num_value = float(value.replace(',', '.'))
            
            # Реалистичные диапазоны для разных единиц
            if unit in ['мл', 'ml']:
                return 0.1 <= num_value <= 5000  # 0.1 мл - 5 л
            elif unit in ['л', 'l']:
                return 0.1 <= num_value <= 50    # 0.1 л - 50 л
            elif unit in ['г', 'g']:
                return 0.1 <= num_value <= 10000 # 0.1 г - 10 кг
            elif unit in ['кг', 'kg']:
                return 0.1 <= num_value <= 100   # 0.1 кг - 100 кг
            
            return True
            
        except ValueError:
            return False
    
    def _extract_from_jsonld(self, soup: BeautifulSoup) -> Set[str]:
        """Извлекает объёмы из JSON-LD additionalProperty"""
        volumes = set()
        
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or '{}')
                items = data if isinstance(data, list) else [data]
                
                for item in items:
                    if item.get('@type') == 'Product':
                        for prop in item.get('additionalProperty', []):
                            name = prop.get('name', '').lower()
                            value = prop.get('value', '')
                            
                            # Проверяем, что это объём
                            if any(keyword in name for keyword in ['объем', 'об\'єм', 'volume', 'capacity']):
                                # Извлекаем число и единицу из значения
                                volume_match = re.search(r'(\d+(?:[.,]\d+)?)\s*([млmlлlгg]+)', str(value), re.IGNORECASE)
                                if volume_match:
                                    normalized = self._normalize_volume(volume_match.group(1), volume_match.group(2))
                                    if normalized:
                                        volumes.add(normalized)
            except (json.JSONDecodeError, KeyError):
                continue
        
        return volumes
    
    def _extract_from_headers(self, soup: BeautifulSoup) -> Set[str]:
        """Извлекает объёмы из заголовков характеристик и заголовка товара"""
        volumes = set()
        
        # 1. Извлекаем из заголовка товара (h2.prod-title)
        prod_title = soup.select_one('h2.prod-title')
        if prod_title:
            title_text = prod_title.get_text().lower()
            for pattern in self.volume_patterns[self.locale]:
                matches = re.findall(pattern, title_text, re.IGNORECASE)
                for value, unit in matches:
                    normalized = self._normalize_volume(value, unit)
                    if normalized and self._is_realistic_volume(normalized):
                        volumes.add(normalized)
        
        # 2. Извлекаем из заголовков характеристик
        for h in soup.select('h2, h3, h4'):
            text = h.get_text().lower()
            if any(keyword in text for keyword in ['характеристик', 'характеристики', 'спецификац']):
                # Ищем следующий элемент с объёмами
                next_elem = h.find_next(['ul', 'table', 'dl'])
                if next_elem:
                    elem_text = next_elem.get_text().lower()
                    for pattern in self.volume_patterns[self.locale]:
                        matches = re.findall(pattern, elem_text, re.IGNORECASE)
                        for value, unit in matches:
                            normalized = self._normalize_volume(value, unit)
                            if normalized and self._is_realistic_volume(normalized):
                                volumes.add(normalized)
        
        return volumes
    
    def _normalize_volume(self, value: str, unit: str) -> Optional[str]:
        """Нормализует объём к стандартному формату"""
        try:
            # Нормализуем число (запятая -> точка)
            value = value.replace(',', '.')
            num_value = float(value)
            
            # Нормализуем единицу
            unit = unit.lower().strip()
            
            # Маппинг единиц к стандартным
            unit_mapping = {
                'ml': 'мл', 'мл': 'мл',
                'l': 'л', 'л': 'л', 'литр': 'л', 'літр': 'л',
                'g': 'г', 'г': 'г', 'грамм': 'г', 'грам': 'г',
                'kg': 'кг', 'кг': 'кг', 'килограмм': 'кг', 'кілограм': 'кг'
            }
            
            normalized_unit = unit_mapping.get(unit, unit)
            
            # Проверяем, что единица поддерживается
            if normalized_unit not in self.volume_units[self.locale]:
                return None
            
            # Форматируем число (убираем лишние нули)
            if num_value == int(num_value):
                formatted_value = str(int(num_value))
            else:
                formatted_value = str(num_value)
            
            return f"{formatted_value} {normalized_unit}"
            
        except (ValueError, TypeError):
            return None
    
    def _canonicalize_mass(self, volume: str) -> str:
        """Канонизирует массу к единому формату (1000 г → 1 кг)"""
        if not volume:
            return volume
        
        # Извлекаем число и единицу
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*([гgкгkg]+)', volume, re.IGNORECASE)
        if not match:
            return volume
        
        value = match.group(1)
        unit = match.group(2).lower()
        
        try:
            num_value = float(value.replace(',', '.'))
            
            # Конвертируем граммы в килограммы
            if unit in ['г', 'g']:
                if num_value >= 1000:
                    kg_value = num_value / 1000
                    if kg_value.is_integer():
                        return f"{int(kg_value)} кг"
                    else:
                        return f"{kg_value} кг"
                else:
                    return f"{int(num_value) if num_value.is_integer() else num_value} г"
            elif unit in ['кг', 'kg']:
                return f"{int(num_value) if num_value.is_integer() else num_value} кг"
            
            return volume
            
        except (ValueError, TypeError):
            return volume
    
    def _are_mass_equivalent(self, vol1: str, vol2: str) -> bool:
        """Проверяет, являются ли массы эквивалентными (1000 г ≡ 1 кг)"""
        canon1 = self._canonicalize_mass(vol1)
        canon2 = self._canonicalize_mass(vol2)
        return canon1 == canon2
    
    def find_volume_mentions(self, text: str) -> List[Tuple[str, int, int]]:
        """Находит все упоминания объёма в тексте, исключая технические контексты"""
        mentions = []
        
        # Паттерны для разных единиц с учётом контекста
        patterns = [
            # мл/ml - всегда ищем
            r'(\d+(?:[.,]\d+)?)\s*([млml]+)',
            # л/l - только для реалистичных значений (0.1-99.9) и с границами слов
            r'\b(\d{1,2}(?:[.,]\d+)?)\s*([лl]+)\b',
            # г/g - только для реалистичных значений
            r'\b(\d{1,4}(?:[.,]\d+)?)\s*([гg]+)\b'
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1)
                unit = match.group(2)
                
                # Проверяем, что это не технический контекст (только для больших чисел)
                if unit.lower() in ['л', 'l'] and self._is_technical_context(text, match.start(), match.end()):
                    continue
                
                # Дополнительная проверка для л/l - исключаем большие числа
                if unit.lower() in ['л', 'l']:
                    try:
                        num_value = float(value.replace(',', '.'))
                        if num_value > 99.9:  # Исключаем 700л, 1000л и т.д.
                            continue
                    except ValueError:
                        continue
                
                normalized = self._normalize_volume(value, unit)
                if normalized:
                    mentions.append((
                        normalized,
                        match.start(),
                        match.end()
                    ))
        
        return mentions
    
    def _is_technical_context(self, text: str, start: int, end: int) -> bool:
        """Проверяет, находится ли упоминание объёма в техническом контексте"""
        # Расширяем контекст для проверки
        context_start = max(0, start - 50)
        context_end = min(len(text), end + 50)
        context = text[context_start:context_end].lower()
        
        # Технические ключевые слова, которые указывают на URL/пути/размеры
        technical_keywords = [
            'src=', 'href=', 'srcset=', 'sizes=', 'width=', 'height=',
            'x', 'px', 'webp', 'jpg', 'png', 'gif', 'svg',
            'url(', 'http', 'https', 'www.', '.com', '.ua', '.ru',
            'data-', 'class=', 'id=', 'style=',
            'swiper', 'gallery', 'image', 'img', 'photo'
        ]
        
        # Проверяем наличие технических ключевых слов в контексте
        for keyword in technical_keywords:
            if keyword in context:
                return True
        
        # Проверяем паттерны размеров изображений (например, 700x700)
        if re.search(r'\d+x\d+', context):
            return True
        
        # Проверяем, что это не в HTML атрибутах
        if re.search(r'[=]\s*["\']?[^"\']*' + re.escape(text[start:end]) + r'[^"\']*["\']?', context):
            return True
        
        return False
    
    def validate_volume_consistency(self, text: str, allowed_volumes: Set[str]) -> List[Dict[str, any]]:
        """Валидирует консистентность объёма в тексте с учётом эквивалентности масс и контекстных порций"""
        errors = []
        
        if not allowed_volumes:
            return errors
        
        mentions = self.find_volume_mentions(text)
        
        for volume, start, end in mentions:
            # Проверяем точное совпадение
            if volume in allowed_volumes:
                continue
            
            # Проверяем эквивалентность масс (1000 г ≡ 1 кг)
            is_equivalent = False
            for allowed_volume in allowed_volumes:
                if self._are_mass_equivalent(volume, allowed_volume):
                    is_equivalent = True
                    break
            
            # Проверяем контекстные порции (42 г как порция при 1 кг упаковке)
            if not is_equivalent and self._is_portion_context(text, volume):
                # Если это порционный контекст, считаем допустимым
                continue
            
            if not is_equivalent:
                errors.append({
                    'type': 'volume_mismatch',
                    'found': volume,
                    'allowed': sorted(allowed_volumes),
                    'position': (start, end),
                    'context': text[max(0, start-20):end+20]
                })
        
        return errors
    
    def repair_mass_mentions(self, text: str, allowed_masses: Set[str]) -> str:
        """Ремонтирует упоминания массы в тексте"""
        if not allowed_masses or not text:
            return text
        
        repaired_text = text
        
        # Если только одно разрешённое значение массы, заменяем все упоминания
        if len(allowed_masses) == 1:
            correct_mass = list(allowed_masses)[0]
            
            # Ищем все упоминания массы в тексте
            for pattern in self.mass_patterns[self.locale]:
                matches = re.finditer(pattern, repaired_text, re.IGNORECASE)
                for match in matches:
                    found_mass = match.group(0)
                    if found_mass != correct_mass:
                        repaired_text = repaired_text.replace(found_mass, correct_mass)
                        logger.info(f"Исправлена масса: '{found_mass}' → '{correct_mass}'")
        
        return repaired_text
    
    def repair_volume_mentions(self, text: str, allowed_volumes: Set[str]) -> str:
        """Ремонтирует упоминания объёма в тексте"""
        if not allowed_volumes:
            return text
        
        # Если только одно разрешённое значение - заменяем все на него
        if len(allowed_volumes) == 1:
            target_volume = list(allowed_volumes)[0]
            mentions = self.find_volume_mentions(text)
            
            for volume, start, end in reversed(mentions):  # Обратный порядок для корректной замены
                if volume != target_volume:
                    text = text[:start] + target_volume + text[end:]
                    logger.info(f"Исправлен объём: {volume} → {target_volume}")
        
        # Если несколько разрешённых значений - заменяем на перечисление
        elif len(allowed_volumes) > 1:
            volumes_list = sorted(allowed_volumes)
            
            # Формируем текст с вариантами
            if self.locale == 'ru':
                variants_text = f"доступны варианты {' и '.join(volumes_list)}"
            else:
                variants_text = f"доступні варіанти {' і '.join(volumes_list)}"
            
            # Заменяем первое упоминание на перечисление вариантов
            mentions = self.find_volume_mentions(text)
            if mentions:
                first_volume, start, end = mentions[0]
                text = text[:start] + variants_text + text[end:]
                logger.info(f"Заменено на варианты: {first_volume} → {variants_text}")
        
        return text
    
    def get_llm_constraints(self, allowed_volumes: Set[str]) -> Dict[str, any]:
        """Возвращает ограничения для LLM"""
        if not allowed_volumes:
            return {}
        
        volumes_list = sorted(allowed_volumes)
        
        if len(volumes_list) == 1:
            constraint_text = f"используй только: {volumes_list[0]}"
        else:
            if self.locale == 'ru':
                constraint_text = f"используй только: {' и '.join(volumes_list)}"
            else:
                constraint_text = f"використовуй тільки: {' і '.join(volumes_list)}"
        
        return {
            'allowed_volumes': volumes_list,
            'constraint_text': constraint_text,
            'faq_format': f"Доступны варианты: {' и '.join(volumes_list)}" if self.locale == 'ru' else f"Доступні варіанти: {' і '.join(volumes_list)}"
        }
    
    def fix_unit_mismatch(self, text: str) -> str:
        """Исправляет смешение единиц измерения (объём vs масса)"""
        if not text:
            return text
        
        repaired_text = text
        
        # Исправляем "объём X грамм" на "масса X г"
        volume_mass_pattern = r'объём[:\s]*(\d+(?:[.,]\d+)?)\s*грамм'
        if self.locale == 'ua':
            volume_mass_pattern = r'об\'єм[:\s]*(\d+(?:[.,]\d+)?)\s*грам'
        
        def replace_volume_mass(match):
            amount = match.group(1)
            if self.locale == 'ru':
                return f"масса {amount} г"
            else:
                return f"маса {amount} г"
        
        repaired_text = re.sub(volume_mass_pattern, replace_volume_mass, repaired_text, flags=re.IGNORECASE)
        
        # Исправляем "объём X кг" на "масса X кг"
        volume_kg_pattern = r'объём[:\s]*(\d+(?:[.,]\d+)?)\s*кг'
        if self.locale == 'ua':
            volume_kg_pattern = r'об\'єм[:\s]*(\d+(?:[.,]\d+)?)\s*кг'
        
        def replace_volume_kg(match):
            amount = match.group(1)
            if self.locale == 'ru':
                return f"масса {amount} кг"
            else:
                return f"маса {amount} кг"
        
        repaired_text = re.sub(volume_kg_pattern, replace_volume_kg, repaired_text, flags=re.IGNORECASE)
        
        # Нормализуем "град." в "°C"
        temp_pattern = r'(\d+(?:[.,]\d+)?)\s*град\.?'
        repaired_text = re.sub(temp_pattern, r'\1°C', repaired_text, flags=re.IGNORECASE)
        
        if repaired_text != text:
            logger.info(f"Исправлено смешение единиц: '{text[:50]}...' → '{repaired_text[:50]}...'")
        
        return repaired_text
    
    def _extract_mass_from_specs(self, soup: BeautifulSoup) -> Set[str]:
        """Извлекает массы из ul.specs"""
        masses = set()
        specs_ul = soup.select_one('ul.specs')
        
        if specs_ul:
            for li in specs_ul.find_all('li'):
                text = li.get_text(strip=True)
                for pattern in self.mass_patterns[self.locale]:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    for match in matches:
                        if len(match) == 2:
                            value, unit = match
                            mass = f"{value} {unit}"
                            masses.add(mass)
                        else:
                            masses.add(match)
        
        return masses
    
    def _extract_mass_from_jsonld(self, soup: BeautifulSoup) -> Set[str]:
        """Извлекает массы из JSON-LD Product schema"""
        masses = set()
        
        try:
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        additional_props = data.get('additionalProperty', [])
                        for prop in additional_props:
                            if isinstance(prop, dict):
                                name = prop.get('name', '').lower()
                                value = prop.get('value', '')
                                
                                # Ищем свойства массы
                                if any(keyword in name for keyword in ['масса', 'вес', 'маса', 'вага', 'weight', 'mass']):
                                    for pattern in self.mass_patterns[self.locale]:
                                        matches = re.findall(pattern, value, re.IGNORECASE)
                                        for match in matches:
                                            if len(match) == 2:
                                                val, unit = match
                                                mass = f"{val} {unit}"
                                                masses.add(mass)
                                            else:
                                                masses.add(match)
                except (json.JSONDecodeError, TypeError):
                    continue
        except Exception as e:
            logger.warning(f"Ошибка извлечения массы из JSON-LD: {e}")
        
        return masses
    
    def _filter_technical_masses(self, masses: Set[str]) -> Set[str]:
        """Фильтрует технические массы (из URL, размеров изображений и т.д.)"""
        filtered = set()
        
        for mass in masses:
            # Проверяем, что это не техническая масса
            if self._is_technical_mass(mass):
                continue
            
            # Проверяем реалистичность значения
            if self._is_realistic_mass(mass):
                filtered.add(mass)
        
        return filtered
    
    def _is_technical_mass(self, mass: str) -> bool:
        """Проверяет, является ли масса технической (из URL, размеров и т.д.)"""
        # Исключаем массы из технических контекстов
        technical_contexts = [
            'href=', 'src=', 'srcset=', 'sizes=',
            'width=', 'height=', 'px', 'x', 'w', 'h'
        ]
        
        for context in technical_contexts:
            if context in mass.lower():
                return True
        
        return False
    
    def _is_realistic_mass(self, mass: str) -> bool:
        """Проверяет реалистичность массы"""
        try:
            # Извлекаем число из массы
            number_match = re.search(r'(\d+(?:[.,]\d+)?)', mass)
            if not number_match:
                return False
            
            number = float(number_match.group(1).replace(',', '.'))
            
            # Проверяем диапазоны для разных единиц
            if 'кг' in mass.lower() or 'kg' in mass.lower():
                return 0.001 <= number <= 50  # 1г - 50кг
            elif 'г' in mass.lower() or 'g' in mass.lower():
                return 0.1 <= number <= 10000  # 0.1г - 10кг
            
            return True
        except (ValueError, AttributeError):
            return False
    
    def _normalize_mass_unit(self, mass: str) -> str:
        """Нормализует единицы массы"""
        # Приводим к стандартному формату
        mass = mass.strip()
        
        # Нормализуем единицы
        if 'кг' in mass.lower() or 'kg' in mass.lower():
            mass = re.sub(r'кг|kg', 'кг', mass, flags=re.IGNORECASE)
        elif 'г' in mass.lower() or 'g' in mass.lower():
            mass = re.sub(r'г|g', 'г', mass, flags=re.IGNORECASE)
        
        return mass
