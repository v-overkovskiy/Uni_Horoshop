"""
Жёсткая безопасная выборка фактов - только проверенные данные
"""
import re
import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)

class SafeFactsExtractor:
    """Извлекает только безопасные факты без спорных данных"""
    
    def __init__(self):
        # Белый список полей для вывода
        self.SAFE_KEYS = {
            'brand', 'category', 'color', 'country', 'series', 
            'form_factor', 'pack_mass', 'pack_volume', 'title',
            'type', 'application', 'material'
        }
        
        # Паттерны для удаления спорных данных
        self.CONTROVERSIAL_PATTERNS = [
            # Плавающие граммы без маркера порции
            (r'\b\d+[\s\u00A0]*(г|гр|грам|грамм)\b(?!\s*(в\s+упаковке|в\s+пакете|на\s+порцию|на\s+процедуру))', ''),
            # Температуры и диапазоны
            (r'\d+\s*[–-]\s*\d+\s*°\s*C', ''),
            (r'\d+\s*°\s*C(?!\s*(температура|нагрев))', ''),
            # Проценты
            (r'\d+\s*%', ''),
            # Время действия
            (r'\d+\s*(час|часа|часов|день|дня|дней|неделя|недели|недель)', ''),
            # Порции без контекста
            (r'\b\d+\s*(порция|порции|порций)\b', ''),
        ]
    
    def extract_safe_facts(self, specs: List[Dict[str, str]], h1: str, 
                          mass_facts: List[str], volume_facts: List[str]) -> Dict[str, Any]:
        """Извлекает только безопасные факты"""
        safe = {'title': h1}
        
        # Извлекаем безопасные поля из характеристик
        for spec in specs:
            name = spec.get('name', '').lower()
            value = spec.get('value', '')
            
            # Проверяем, является ли поле безопасным
            for safe_key in self.SAFE_KEYS:
                if safe_key in name:
                    safe[safe_key] = value
                    break
        
        # Определяем канон упаковки
        safe['pack'] = self._canon_pack(mass_facts, volume_facts)
        
        return safe
    
    def _canon_pack(self, mass_facts: List[str], volume_facts: List[str]) -> Optional[str]:
        """Определяет канон упаковки (приоритет массы/объёма упаковки)"""
        # Приоритет: масса упаковки > объём упаковки
        if mass_facts:
            return mass_facts[0]
        elif volume_facts:
            return volume_facts[0]
        return None
    
    def strip_controversial_numbers(self, html: str) -> str:
        """Удаляет спорные числа из HTML"""
        if not html:
            return html
        
        original_html = html
        
        for pattern, replacement in self.CONTROVERSIAL_PATTERNS:
            html = re.sub(pattern, replacement, html, flags=re.I)
        
        if original_html != html:
            logger.info("🧹 Удалены спорные числа из HTML")
        
        return html
    
    def is_safe_fact(self, key: str, value: str) -> bool:
        """Проверяет, является ли факт безопасным"""
        key_lower = key.lower()
        
        # Проверяем ключ
        if not any(safe_key in key_lower for safe_key in self.SAFE_KEYS):
            return False
        
        # Проверяем значение на спорные данные
        for pattern, _ in self.CONTROVERSIAL_PATTERNS:
            if re.search(pattern, value, flags=re.I):
                return False
        
        return True
    
    def get_safe_specs(self, specs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Фильтрует характеристики, оставляя только безопасные"""
        safe_specs = []
        
        for spec in specs:
            name = spec.get('name', '')
            value = spec.get('value', '')
            
            if self.is_safe_fact(name, value):
                safe_specs.append(spec)
            else:
                logger.debug(f"🚫 Исключен спорный факт: {name}: {value}")
        
        return safe_specs

