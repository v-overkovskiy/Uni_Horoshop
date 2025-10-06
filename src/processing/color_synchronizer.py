"""
Синхронизатор цветов для исправления несоответствий
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ColorSynchronizer:
    """Синхронизатор цветов между названием и характеристиками"""
    
    def __init__(self):
        # Словарь соответствий цветов
        self.color_mapping = {
            'ru': {
                'коралл': 'коралловый',
                'корал': 'коралловый',
                'coral': 'коралловый',
                'белый': 'белый',
                'бел': 'белый',
                'white': 'белый',
                'чёрный': 'чёрный',
                'черный': 'чёрный',
                'чёрн': 'чёрный',
                'black': 'чёрный',
                'розовый': 'розовый',
                'розов': 'розовый',
                'pink': 'розовый',
                'синий': 'синий',
                'син': 'синий',
                'blue': 'синий',
                'зелёный': 'зелёный',
                'зеленый': 'зелёный',
                'зел': 'зелёный',
                'green': 'зелёный',
                'красный': 'красный',
                'красн': 'красный',
                'red': 'красный',
                'жёлтый': 'жёлтый',
                'желтый': 'жёлтый',
                'жёлт': 'жёлтый',
                'yellow': 'жёлтый',
                'фиолетовый': 'фиолетовый',
                'фиолет': 'фиолетовый',
                'purple': 'фиолетовый',
                'оранжевый': 'оранжевый',
                'оранж': 'оранжевый',
                'orange': 'оранжевый',
                'серый': 'серый',
                'сер': 'серый',
                'gray': 'серый',
                'grey': 'серый'
            },
            'ua': {
                'корал': 'кораловий',
                'коралл': 'кораловий',
                'coral': 'кораловий',
                'білий': 'білий',
                'біл': 'білий',
                'white': 'білий',
                'чорний': 'чорний',
                'чорн': 'чорний',
                'black': 'чорний',
                'рожевий': 'рожевий',
                'рожев': 'рожевий',
                'pink': 'рожевий',
                'синій': 'синій',
                'син': 'синій',
                'blue': 'синій',
                'зелений': 'зелений',
                'зел': 'зелений',
                'green': 'зелений',
                'червоний': 'червоний',
                'червон': 'червоний',
                'red': 'червоний',
                'жовтий': 'жовтий',
                'жовт': 'жовтий',
                'yellow': 'жовтий',
                'фіолетовий': 'фіолетовий',
                'фіолет': 'фіолетовий',
                'purple': 'фіолетовий',
                'помаранчевий': 'помаранчевий',
                'помаранч': 'помаранчевий',
                'orange': 'помаранчевий',
                'сірий': 'сірий',
                'сір': 'сірий',
                'gray': 'сірий',
                'grey': 'сірий'
            }
        }
        
        # Паттерны для поиска цветов в тексте
        self.color_patterns = {
            'ru': [
                r'цвет[:\s]*([а-яё\s]+)',
                r'колор[:\s]*([а-яё\s]+)',
                r'оттенок[:\s]*([а-яё\s]+)',
                r'расцветка[:\s]*([а-яё\s]+)'
            ],
            'ua': [
                r'колір[:\s]*([а-яіїєґ\s]+)',
                r'відтінок[:\s]*([а-яіїєґ\s]+)',
                r'розфарбування[:\s]*([а-яіїєґ\s]+)'
            ]
        }
    
    def extract_color_from_title(self, title: str, locale: str) -> Optional[str]:
        """Извлекает цвет из названия товара"""
        if not title:
            return None
        
        title_lower = title.lower()
        
        # Ищем цвета в названии
        for color_key, color_value in self.color_mapping[locale].items():
            if color_key in title_lower:
                logger.debug(f"Найден цвет в названии: {color_key} → {color_value}")
                return color_value
        
        return None
    
    def extract_color_from_specs(self, specs: List[Dict[str, str]], locale: str) -> Optional[str]:
        """Извлекает цвет из характеристик"""
        if not specs:
            return None
        
        # Ищем цвет в характеристиках
        for spec in specs:
            name = spec.get('name', '').lower()
            value = spec.get('value', '').lower()
            
            # Проверяем название характеристики
            if any(keyword in name for keyword in ['цвет', 'колор', 'оттенок', 'колір', 'відтінок']):
                # Нормализуем значение цвета
                normalized_color = self._normalize_color(value, locale)
                if normalized_color:
                    logger.debug(f"Найден цвет в характеристиках: {value} → {normalized_color}")
                    return normalized_color
        
        return None
    
    def _normalize_color(self, color_text: str, locale: str) -> Optional[str]:
        """Нормализует текст цвета"""
        if not color_text:
            return None
        
        color_lower = color_text.lower().strip()
        
        # Ищем точное соответствие
        for color_key, color_value in self.color_mapping[locale].items():
            if color_key == color_lower:
                return color_value
        
        # Ищем частичное соответствие
        for color_key, color_value in self.color_mapping[locale].items():
            if color_key in color_lower:
                return color_value
        
        return None
    
    def synchronize_colors(self, title: str, specs: List[Dict[str, str]], locale: str) -> Tuple[Optional[str], List[Dict[str, str]]]:
        """Синхронизирует цвета между названием и характеристиками"""
        # Извлекаем цвет из названия
        title_color = self.extract_color_from_title(title, locale)
        
        # Извлекаем цвет из характеристик
        specs_color = self.extract_color_from_specs(specs, locale)
        
        logger.debug(f"Цвета: название='{title_color}', характеристики='{specs_color}'")
        
        # Определяем правильный цвет
        if title_color and specs_color:
            if title_color != specs_color:
                logger.warning(f"Несоответствие цветов: название='{title_color}' vs характеристики='{specs_color}'")
                # Приоритет у названия
                correct_color = title_color
            else:
                correct_color = title_color
        elif title_color:
            correct_color = title_color
        elif specs_color:
            correct_color = specs_color
        else:
            return None, specs
        
        # Обновляем характеристики
        updated_specs = []
        color_updated = False
        
        for spec in specs:
            name = spec.get('name', '').lower()
            value = spec.get('value', '')
            
            # Если это характеристика цвета, обновляем её
            if any(keyword in name for keyword in ['цвет', 'колор', 'оттенок', 'колір', 'відтінок']):
                spec['value'] = correct_color
                color_updated = True
                logger.info(f"Обновлён цвет в характеристиках: {value} → {correct_color}")
            
            updated_specs.append(spec)
        
        # Если не нашли характеристику цвета, но есть цвет в названии, добавляем её
        if not color_updated and correct_color:
            color_key = 'цвет' if locale == 'ru' else 'колір'
            updated_specs.append({
                'name': color_key,
                'value': correct_color
            })
            logger.info(f"Добавлена характеристика цвета: {color_key} = {correct_color}")
        
        return correct_color, updated_specs


