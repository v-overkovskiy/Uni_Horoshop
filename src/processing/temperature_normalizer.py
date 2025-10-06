"""
Нормализатор единиц температуры для RU/UA
"""
import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class TemperatureNormalizer:
    """Нормализатор единиц температуры"""
    
    def __init__(self):
        # Паттерны для поиска температуры
        self.temp_patterns = {
            'ru': [
                r'(\d+(?:[–-]\d+)?)\s*град\.',  # 40 град.
                r'(\d+(?:[–-]\d+)?)\s*градусов?',  # 40 градусов, 38-40 градусов
                r'(\d+(?:[–-]\d+)?)\s*°C',  # 40 °C
                r'(\d+(?:[–-]\d+)?)\s*°',  # 40°
            ],
            'ua': [
                r'(\d+(?:[–-]\d+)?)\s*град\.',  # 40 град.
                r'(\d+(?:[–-]\d+)?)\s*градусів?',  # 40 градусів, 38-40 градусів
                r'(\d+(?:[–-]\d+)?)\s*°C',  # 40 °C
                r'(\d+(?:[–-]\d+)?)\s*°',  # 40°
            ]
        }
        
        # Словари замен
        self.replacements = {
            'ru': {
                'град.': '°C',
                'градусов': '°C',
                'градус': '°C',
                '°': '°C'
            },
            'ua': {
                'град.': '°C',
                'градусів': '°C',
                'градус': '°C',
                '°': '°C'
            }
        }
    
    def normalize_temperature(self, text: str, locale: str) -> str:
        """Нормализует единицы температуры в тексте"""
        if not text:
            return text
        
        patterns = self.temp_patterns.get(locale, [])
        replacements = self.replacements.get(locale, {})
        
        result = text
        
        # Применяем замены
        for old_unit, new_unit in replacements.items():
            # Заменяем "40 град." на "40 °C"
            result = re.sub(
                rf'(\d+(?:[–-]\d+)?)\s*{re.escape(old_unit)}',
                rf'\1 {new_unit}',
                result,
                flags=re.IGNORECASE
            )
        
        return result
    
    def extract_temperatures(self, text: str, locale: str) -> List[Tuple[str, str]]:
        """Извлекает температуры из текста"""
        if not text:
            return []
        
        patterns = self.temp_patterns.get(locale, [])
        temperatures = []
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                temp_value = match.group(1)
                full_match = match.group(0)
                temperatures.append((temp_value, full_match))
        
        return temperatures
    
    def validate_temperature_consistency(self, texts: List[str], locale: str) -> Dict[str, any]:
        """Проверяет консистентность температур в текстах"""
        all_temps = []
        
        for text in texts:
            temps = self.extract_temperatures(text, locale)
            all_temps.extend(temps)
        
        # Группируем по значениям
        temp_groups = {}
        for value, full_match in all_temps:
            if value not in temp_groups:
                temp_groups[value] = []
            temp_groups[value].append(full_match)
        
        # Проверяем консистентность
        inconsistent = []
        for value, matches in temp_groups.items():
            unique_matches = set(matches)
            if len(unique_matches) > 1:
                inconsistent.append({
                    'value': value,
                    'variants': list(unique_matches)
                })
        
        return {
            'temperatures_found': len(all_temps),
            'unique_values': list(temp_groups.keys()),
            'inconsistent': inconsistent,
            'is_consistent': len(inconsistent) == 0
        }


