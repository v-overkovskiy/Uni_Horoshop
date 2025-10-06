"""
Улучшенный санитайзер преимуществ с автодозаполнением
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple
from src.processing.advantages_sanitizer import AdvantagesSanitizer
from src.processing.brand_normalizer import BrandNormalizer

logger = logging.getLogger(__name__)

class AdvantagesEnhancer:
    """Улучшенный санитайзер преимуществ с автодозаполнением"""
    
    def __init__(self, locale: str):
        self.locale = locale
        self.sanitizer = AdvantagesSanitizer(locale)
        self.brand_normalizer = BrandNormalizer()
        
        # Минимальное количество преимуществ
        self.min_advantages = 3
        self.max_advantages = 4
        
        # Шаблоны для автодозаполнения
        self.templates = {
            'ru': {
                'power': "Быстрый нагрев {power} Вт",
                'volume': "Удобный объём {volume} мл",
                'mass': "Большой вес {mass} г для профессионального применения",
                'mass_kg': "Большой вес {mass} кг для профессионального применения",
                'skin_type': "Подходит для {skin_type} кожи",
                'brand': "Оригинальный бренд {brand}",
                'material': "Качественный материал {material}",
                'temperature': "Точная регулировка температуры до {temp}°C",
                'warranty': "Гарантия качества {warranty}",
                'professional': "Профессиональное качество",
                'durable': "Долговечная конструкция",
                'safe': "Безопасное использование"
            },
            'ua': {
                'power': "Швидкий нагрів {power} Вт",
                'volume': "Зручний об'єм {volume} мл",
                'mass': "Велика вага {mass} г для професійного використання",
                'mass_kg': "Велика вага {mass} кг для професійного використання",
                'skin_type': "Підходить для {skin_type} шкіри",
                'brand': "Оригінальний бренд {brand}",
                'material': "Якісний матеріал {material}",
                'temperature': "Точна регулювання температури до {temp}°C",
                'warranty': "Гарантія якості {warranty}",
                'professional': "Професійна якість",
                'durable': "Довговічна конструкція",
                'safe': "Безпечне використання"
            }
        }
    
    def enhance_advantages(self, advantages: List[str], specs: List[Dict[str, str]], 
                          facts: Dict[str, any] = None) -> Tuple[List[str], Dict[str, any]]:
        """
        Улучшает список преимуществ с автодозаполнением
        
        Args:
            advantages: Исходный список преимуществ
            specs: Список характеристик товара
            facts: Дополнительные факты о товаре
            
        Returns:
            Tuple[List[str], Dict]: (улучшенные преимущества, отчет)
        """
        if not facts:
            facts = {}
        
        # Нормализуем характеристики
        normalized_specs = self.brand_normalizer.normalize_specs_brands(specs)
        
        # Извлекаем факты из характеристик
        extracted_facts = self._extract_facts_from_specs(normalized_specs)
        facts.update(extracted_facts)
        
        # Санитизируем исходные преимущества
        sanitizer_result = self.sanitizer.sanitize(advantages)
        if isinstance(sanitizer_result, tuple):
            clean_advantages = sanitizer_result[0]  # Берем только список преимуществ
        else:
            clean_advantages = sanitizer_result
        
        # Проверяем, нужно ли автодозаполнение
        if len(clean_advantages) < self.min_advantages:
            logger.info(f"Недостаточно преимуществ ({len(clean_advantages)}), запускаем автодозаполнение")
            
            # Автодозаполняем недостающие преимущества
            auto_filled = self._auto_fill_advantages(clean_advantages, facts)
            clean_advantages = auto_filled[:self.max_advantages]
        
        # Создаем отчет
        report = {
            'original_count': len(advantages),
            'clean_count': len(clean_advantages),
            'auto_filled': len(clean_advantages) - len(advantages),
            'facts_used': list(facts.keys()),
            'normalized_specs': len(normalized_specs) != len(specs)
        }
        
        return clean_advantages, report
    
    def _extract_facts_from_specs(self, specs: List[Dict[str, str]]) -> Dict[str, any]:
        """Извлекает факты из характеристик"""
        facts = {}
        
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            
            name = spec.get('name', '').lower()
            value = spec.get('value', '')
            
            # Извлекаем мощность
            if 'мощность' in name or 'power' in name:
                power_match = re.search(r'(\d+)\s*вт', value.lower())
                if power_match:
                    facts['power_w'] = int(power_match.group(1))
            
            # Извлекаем объём
            elif 'объем' in name or 'об\'єм' in name or 'volume' in name:
                volume_match = re.search(r'(\d+(?:[.,]\d+)?)\s*мл', value.lower())
                if volume_match:
                    facts['volume_ml'] = volume_match.group(1)
            
            # Извлекаем массу
            elif 'масса' in name or 'маса' in name or 'вес' in name or 'вага' in name or 'weight' in name:
                mass_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(г|кг|g|kg)', value.lower())
                if mass_match:
                    amount = mass_match.group(1)
                    unit = mass_match.group(2)
                    if unit in ['кг', 'kg']:
                        facts['mass_kg'] = amount
                    else:
                        facts['mass_g'] = amount
            
            # Извлекаем тип кожи
            elif 'тип' in name and 'кож' in name:
                facts['skin_type'] = value
            
            # Извлекаем материал
            elif 'материал' in name or 'матеріал' in name or 'material' in name:
                facts['material'] = value
            
            # Извлекаем температуру
            elif 'температура' in name or 'temp' in name:
                temp_match = re.search(r'(\d+(?:[.,]\d+)?)\s*°?c', value.lower())
                if temp_match:
                    facts['temperature'] = temp_match.group(1)
            
            # Извлекаем гарантию
            elif 'гарантия' in name or 'гарантія' in name or 'warranty' in name:
                facts['warranty'] = value
            
            # Извлекаем бренд
            elif 'бренд' in name or 'brand' in name:
                facts['brand'] = value
        
        return facts
    
    def _auto_fill_advantages(self, existing_advantages: List[str], facts: Dict[str, any]) -> List[str]:
        """Автодозаполняет недостающие преимущества"""
        templates = self.templates[self.locale]
        candidates = []
        
        # 1. Числовые и измеримые факты (приоритет)
        if 'power_w' in facts:
            candidates.append(templates['power'].format(power=facts['power_w']))
        
        if 'volume_ml' in facts:
            candidates.append(templates['volume'].format(volume=facts['volume_ml']))
        
        if 'mass_kg' in facts:
            candidates.append(templates['mass_kg'].format(mass=facts['mass_kg']))
        elif 'mass_g' in facts:
            candidates.append(templates['mass'].format(mass=facts['mass_g']))
        
        if 'temperature' in facts:
            candidates.append(templates['temperature'].format(temp=facts['temperature']))
        
        # 2. Сценарии применения
        if 'skin_type' in facts:
            candidates.append(templates['skin_type'].format(skin_type=facts['skin_type']))
        
        # 3. Материалы и бренд
        if 'material' in facts:
            candidates.append(templates['material'].format(material=facts['material']))
        
        if 'brand' in facts:
            candidates.append(templates['brand'].format(brand=facts['brand']))
        
        if 'warranty' in facts:
            candidates.append(templates['warranty'].format(warranty=facts['warranty']))
        
        # 4. Общие преимущества
        candidates.extend([
            templates['professional'],
            templates['durable'],
            templates['safe']
        ])
        
        # Фильтруем кандидатов
        valid_candidates = self._filter_candidates(candidates, existing_advantages)
        
        # Добавляем недостающие преимущества
        result = list(existing_advantages)
        for candidate in valid_candidates:
            if len(result) >= self.min_advantages:
                break
            if candidate not in result:
                result.append(candidate)
        
        return result[:self.max_advantages]
    
    def _filter_candidates(self, candidates: List[str], existing: List[str]) -> List[str]:
        """Фильтрует кандидатов, исключая дубликаты и невалидные"""
        valid = []
        existing_lower = [str(adv).lower() for adv in existing]
        
        for candidate in candidates:
            # Проверяем на дубликаты
            if candidate.lower() in existing_lower:
                continue
            
            # Проверяем на стоп-фразы
            if self._has_stop_phrases(candidate):
                continue
            
            # Проверяем на несоответствие единиц измерения
            if self._has_unit_mismatch(candidate):
                continue
            
            valid.append(candidate)
        
        return valid
    
    def _has_stop_phrases(self, text: str) -> bool:
        """Проверяет наличие стоп-фраз"""
        stop_phrases = [
            'проверенная временем рецептура',
            'перевірена часом рецептура',
            'дополнительная информация',
            'додаткова інформація',
            'подробнее',
            'подробиці'
        ]
        
        text_lower = text.lower()
        return any(phrase in text_lower for phrase in stop_phrases)
    
    def _has_unit_mismatch(self, text: str) -> bool:
        """Проверяет несоответствие единиц измерения"""
        # Если в тексте есть мл, но товар по массе в кг
        if 'мл' in text.lower() and 'кг' in text.lower():
            return True
        
        # Если в тексте есть г, но товар по объёму в мл
        if 'г' in text.lower() and 'мл' in text.lower():
            return True
        
        return False
