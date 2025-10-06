"""
Нормализатор брендов для исправления смешения кириллицы и латиницы
"""

import re
import logging
from typing import Dict, Set, Optional

logger = logging.getLogger(__name__)

class BrandNormalizer:
    """Нормализатор брендов для исправления смешения кириллицы и латиницы"""
    
    def __init__(self):
        # Словарь нормализации брендов
        self.brand_mappings = {
            # Смешение кириллицы и латиницы
            'ItaлWAX': 'ItalWax',
            'Itaлwax': 'ItalWax', 
            'ITAлWAX': 'ITALWAX',
            'ITAлwax': 'ITALWAX',
            'itaлwax': 'italwax',
            'itaлWAX': 'italWAX',
            
            # Стандартизация регистра
            'italwax': 'ItalWax',
            'ITALWAX': 'ItalWax',
            'ItalWAX': 'ItalWax',
            'Italwax': 'ItalWax',
            
            # Другие бренды
            'ESTI': 'ESTI',
            'esti': 'ESTI',
            'Esti': 'ESTI',
            'BUCOS': 'BUCOS',
            'bucos': 'BUCOS',
            'Bucos': 'BUCOS',
            'EPILAX': 'EPILAX',
            'epilax': 'EPILAX',
            'Epilax': 'EPILAX',
        }
        
        # Паттерны для поиска смешения кириллицы и латиницы
        self.mixed_patterns = [
            r'[A-Za-z]+[а-яё]+[A-Za-z]+',  # латиница + кириллица + латиница
            r'[а-яё]+[A-Za-z]+[а-яё]+',    # кириллица + латиница + кириллица
            r'[A-Za-z]+[а-яё]+',           # латиница + кириллица
            r'[а-яё]+[A-Za-z]+',           # кириллица + латиница
        ]
    
    def normalize_brand(self, brand: str) -> str:
        """
        Нормализует бренд, исправляя смешение кириллицы и латиницы
        
        Args:
            brand: Исходный бренд
            
        Returns:
            str: Нормализованный бренд
        """
        if not brand:
            return brand
        
        original_brand = brand.strip()
        
        # Проверяем точное совпадение в словаре
        if original_brand in self.brand_mappings:
            normalized = self.brand_mappings[original_brand]
            logger.info(f"Бренд нормализован: '{original_brand}' → '{normalized}'")
            return normalized
        
        # Проверяем смешение кириллицы и латиницы
        if self._has_mixed_script(original_brand):
            normalized = self._fix_mixed_script(original_brand)
            if normalized != original_brand:
                logger.info(f"Исправлено смешение скриптов: '{original_brand}' → '{normalized}'")
                return normalized
        
        # Стандартизируем регистр для известных брендов
        normalized = self._standardize_case(original_brand)
        if normalized != original_brand:
            logger.info(f"Стандартизирован регистр: '{original_brand}' → '{normalized}'")
            return normalized
        
        return original_brand
    
    def _has_mixed_script(self, text: str) -> bool:
        """Проверяет, содержит ли текст смешение кириллицы и латиницы"""
        for pattern in self.mixed_patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _fix_mixed_script(self, text: str) -> str:
        """Исправляет смешение кириллицы и латиницы"""
        # Словарь замен кириллических букв на латинские
        cyrillic_to_latin = {
            'а': 'a', 'в': 'B', 'е': 'e', 'к': 'K', 'м': 'M', 'н': 'H', 'о': 'o', 'п': 'P', 'р': 'p', 'с': 'C', 'т': 'T', 'у': 'y', 'х': 'X',
            'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H', 'О': 'O', 'П': 'P', 'Р': 'P', 'С': 'C', 'Т': 'T', 'У': 'Y', 'Х': 'X'
        }
        
        # Заменяем кириллические буквы на латинские
        fixed = text
        for cyr, lat in cyrillic_to_latin.items():
            fixed = fixed.replace(cyr, lat)
        
        return fixed
    
    def _standardize_case(self, text: str) -> str:
        """Стандартизирует регистр для известных брендов"""
        # Проверяем частичные совпадения
        text_lower = text.lower()
        
        for known_brand in self.brand_mappings.keys():
            if text_lower == known_brand.lower():
                return self.brand_mappings[known_brand]
        
        return text
    
    def normalize_specs_brands(self, specs: list) -> list:
        """
        Нормализует бренды в списке характеристик
        
        Args:
            specs: Список характеристик [{'name': '...', 'value': '...'}]
            
        Returns:
            list: Нормализованный список характеристик
        """
        if not specs:
            return specs
        
        normalized_specs = []
        
        for spec in specs:
            if not isinstance(spec, dict):
                normalized_specs.append(spec)
                continue
            
            normalized_spec = spec.copy()
            
            # Нормализуем название характеристики
            if 'name' in spec:
                normalized_spec['name'] = self.normalize_brand(spec['name'])
            
            # Нормализуем значение характеристики
            if 'value' in spec:
                normalized_spec['value'] = self.normalize_brand(spec['value'])
            
            normalized_specs.append(normalized_spec)
        
        return normalized_specs
    
    def get_normalization_report(self, original_brand: str, normalized_brand: str) -> Dict[str, any]:
        """
        Создает отчет о нормализации бренда
        
        Args:
            original_brand: Исходный бренд
            normalized_brand: Нормализованный бренд
            
        Returns:
            Dict: Отчет о нормализации
        """
        return {
            'original': original_brand,
            'normalized': normalized_brand,
            'changed': original_brand != normalized_brand,
            'change_type': self._get_change_type(original_brand, normalized_brand),
            'mixed_script_fixed': self._has_mixed_script(original_brand) and not self._has_mixed_script(normalized_brand),
            'case_standardized': original_brand.lower() == normalized_brand.lower() and original_brand != normalized_brand
        }
    
    def _get_change_type(self, original: str, normalized: str) -> str:
        """Определяет тип изменения при нормализации"""
        if original == normalized:
            return 'no_change'
        elif self._has_mixed_script(original) and not self._has_mixed_script(normalized):
            return 'mixed_script_fixed'
        elif original.lower() == normalized.lower() and original != normalized:
            return 'case_standardized'
        elif original in self.brand_mappings:
            return 'dictionary_mapping'
        else:
            return 'unknown'


