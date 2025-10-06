"""
Исправление терминологии: объём → масса для кг/г
"""
import re
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class TerminologyFixer:
    """Исправляет терминологию объём/масса"""
    
    def __init__(self):
        # Паттерны для замены "объём" на "масса" для кг/г
        self.volume_to_mass_patterns = {
            'ru': [
                (r'объём[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'масса: \1 \2'),
                (r'об\'ём[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'масса: \1 \2'),
                (r'вместимость[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'масса: \1 \2'),
                (r'ёмкость[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'масса: \1 \2'),
                # FAQ паттерны
                (r'какой объём', r'какой вес'),
                (r'какой об\'ём', r'какой вес'),
                (r'какой объём\?', r'какой вес?'),
                (r'какой об\'ём\?', r'какой вес?'),
                (r'объём составляет', r'вес составляет'),
                (r'об\'ём составляет', r'вес составляет'),
                (r'объём равен', r'вес равен'),
                (r'об\'ём равен', r'вес равен'),
            ],
            'ua': [
                (r'об\'єм[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'вага: \1 \2'),
                (r'объем[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'вага: \1 \2'),
                (r'вмістимість[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'вага: \1 \2'),
                (r'ємність[:\s]*(\d+(?:[.,]\d+)?)\s*([кгkgгg]+)', r'вага: \1 \2'),
                # FAQ паттерны
                (r'який об\'єм', r'яка вага'),
                (r'який объем', r'яка вага'),
                (r'який об\'єм\?', r'яка вага?'),
                (r'який объем\?', r'яка вага?'),
                (r'об\'єм становить', r'вага становить'),
                (r'объем становить', r'вага становить'),
                (r'об\'єм дорівнює', r'вага дорівнює'),
                (r'объем дорівнює', r'вага дорівнює'),
            ]
        }
        
        # Паттерны для исправления температурных артефактов
        self.temperature_fix_patterns = {
            'ru': [
                (r'(\d+(?:[–-]\d+)?)\s*°CC', r'\1 °C'),
                (r'(\d+(?:[–-]\d+)?)\s*град\.', r'\1 °C'),
                (r'(\d+(?:[–-]\d+)?)\s*градусов?', r'\1 °C'),
            ],
            'ua': [
                (r'(\d+(?:[–-]\d+)?)\s*°CC', r'\1 °C'),
                (r'(\d+(?:[–-]\d+)?)\s*град\.', r'\1 °C'),
                (r'(\d+(?:[–-]\d+)?)\s*градусів?', r'\1 °C'),
            ]
        }
    
    def fix_volume_to_mass(self, text: str, locale: str) -> str:
        """Исправляет 'объём' на 'масса' для кг/г"""
        if not text:
            return text
        
        patterns = self.volume_to_mass_patterns.get(locale, [])
        result = text
        
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    def fix_temperature_artifacts(self, text: str, locale: str) -> str:
        """Исправляет температурные артефакты (°CC → °C)"""
        if not text:
            return text
        
        patterns = self.temperature_fix_patterns.get(locale, [])
        result = text
        
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    def fix_specs_terminology(self, specs: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """Исправляет терминологию в характеристиках"""
        if not specs:
            return specs
        
        fixed_specs = []
        for spec in specs:
            name = spec.get('name', '')
            value = spec.get('value', '')
            
            # Исправляем название характеристики
            fixed_name = self.fix_volume_to_mass(name, locale)
            
            # Исправляем значение
            fixed_value = self.fix_volume_to_mass(value, locale)
            fixed_value = self.fix_temperature_artifacts(fixed_value, locale)
            
            fixed_specs.append({
                'name': fixed_name,
                'value': fixed_value
            })
        
        return fixed_specs
    
    def fix_html_terminology(self, html: str, locale: str) -> str:
        """Исправляет терминологию в HTML"""
        if not html:
            return html
        
        # Исправляем в тексте
        result = self.fix_volume_to_mass(html, locale)
        result = self.fix_temperature_artifacts(result, locale)
        
        return result
