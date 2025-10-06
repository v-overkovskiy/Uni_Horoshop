"""
Нормализация единиц измерения по локали
"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class UnitsNormalizer:
    """Нормализация единиц измерения для RU/UA локалей"""
    
    def __init__(self, locale: str):
        self.locale = locale
        self._setup_locale_units()
    
    def _setup_locale_units(self):
        """Настройка единиц измерения для локали"""
        if self.locale == 'ru':
            self.units = {
                'volume': {
                    'ml': 'мл',
                    'l': 'л',
                    'liter': 'л',
                    'литр': 'л',
                    'миллилитр': 'мл'
                },
                'weight': {
                    'g': 'г',
                    'gram': 'г',
                    'kg': 'кг',
                    'килограмм': 'кг',
                    'грамм': 'г'
                },
                'length': {
                    'cm': 'см',
                    'mm': 'мм',
                    'm': 'м',
                    'метр': 'м',
                    'сантиметр': 'см',
                    'миллиметр': 'мм'
                }
            }
            self.spec_labels = {
                'brand': 'Бренд',
                'type': 'Тип',
                'material': 'Материал',
                'volume': 'Объем',
                'weight': 'Вес',
                'color': 'Цвет',
                'size': 'Размер',
                'purpose': 'Назначение'
            }
        else:  # ua
            self.units = {
                'volume': {
                    'ml': 'мл',
                    'l': 'л',
                    'liter': 'л',
                    'літр': 'л',
                    'мілілітр': 'мл'
                },
                'weight': {
                    'g': 'г',
                    'gram': 'г',
                    'kg': 'кг',
                    'кілограм': 'кг',
                    'грам': 'г'
                },
                'length': {
                    'cm': 'см',
                    'mm': 'мм',
                    'm': 'м',
                    'метр': 'м',
                    'сантиметр': 'см',
                    'міліметр': 'мм'
                }
            }
            self.spec_labels = {
                'brand': 'бренд',
                'type': 'тип',
                'material': 'матеріал',
                'volume': 'об\'єм',
                'weight': 'вага',
                'color': 'колір',
                'size': 'розмір',
                'purpose': 'призначення'
            }
    
    def normalize_volume(self, value: str) -> str:
        """Нормализация объема"""
        return self._normalize_unit(value, 'volume')
    
    def normalize_weight(self, value: str) -> str:
        """Нормализация веса"""
        return self._normalize_unit(value, 'weight')
    
    def normalize_length(self, value: str) -> str:
        """Нормализация длины"""
        return self._normalize_unit(value, 'length')
    
    def _normalize_unit(self, value: str, unit_type: str) -> str:
        """Нормализация единицы измерения"""
        if not value:
            return value
        
        value = value.strip()
        units_map = self.units.get(unit_type, {})
        
        # Ищем единицы измерения в значении
        for eng_unit, loc_unit in units_map.items():
            if eng_unit in value.lower():
                value = value.replace(eng_unit, loc_unit)
                break
        
        return value
    
    def normalize_spec_label(self, label: str) -> str:
        """Нормализация лейбла характеристики"""
        if not label:
            return label
        
        label = label.strip().lower()
        
        # Ищем соответствие в словаре лейблов
        for eng_label, loc_label in self.spec_labels.items():
            if eng_label in label:
                return loc_label
        
        # Если не найдено, возвращаем как есть
        return label
    
    def clean_specs(self, specs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Очистка и нормализация характеристик"""
        if not specs:
            return specs
        
        cleaned_specs = []
        seen_values = set()
        
        for spec in specs:
            if not isinstance(spec, dict) or 'name' not in spec or 'value' not in spec:
                continue
            
            name = spec['name'].strip()
            value = spec['value'].strip()
            
            if not name or not value:
                continue
            
            # Нормализуем лейбл
            normalized_name = self.normalize_spec_label(name)
            
            # Нормализуем значение
            normalized_value = self._normalize_value(value)
            
            # Проверяем на дубликаты по значению
            if normalized_value in seen_values:
                continue
            
            # Проверяем на русские лейблы в UA
            if self.locale == 'ua' and self._has_russian_label(normalized_name):
                continue
            
            cleaned_specs.append({
                'name': normalized_name,
                'value': normalized_value
            })
            seen_values.add(normalized_value)
        
        return cleaned_specs
    
    def _normalize_value(self, value: str) -> str:
        """Нормализация значения характеристики"""
        # Нормализуем единицы измерения
        value = self.normalize_volume(value)
        value = self.normalize_weight(value)
        value = self.normalize_length(value)
        
        return value
    
    def _has_russian_label(self, label: str) -> bool:
        """Проверка на русские лейблы в UA"""
        russian_labels = ['Материал', 'Объем', 'Вес', 'Тип', 'Назначение', 'Цвет', 'Размер']
        return any(ru_label in label for ru_label in russian_labels)
    
    def detect_product_type(self, title: str, specs: List[Dict[str, str]]) -> Optional[str]:
        """Определение типа товара по заголовку и характеристикам"""
        if not title:
            return None
        
        title_lower = title.lower()
        
        # Ключевые слова для определения типа
        type_keywords = {
            'свеча': ['свеча', 'свічка', 'candle', 'воск', 'віск'],
            'тоник': ['тоник', 'тонік', 'tonic', 'депиляция', 'депіляція'],
            'молочко': ['молочко', 'молочко', 'milk', 'spf', 'солнцезащитный', 'сонцезахисний'],
            'дезодорант': ['дезодорант', 'дезодорант', 'deodorant', 'стик', 'стік']
        }
        
        for product_type, keywords in type_keywords.items():
            if any(keyword in title_lower for keyword in keywords):
                return product_type
        
        return None


