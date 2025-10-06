"""
Генератор коммерческих фраз ProRazko с правильными падежами
"""
import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

class NoteBuyGenerator:
    """Генерирует коммерческие фразы по точной формуле ProRazko"""
    
    def __init__(self):
        # Паттерны для склонения украинских слов
        self.ua_declensions = {
            r'пудра\s+(\w+)': r'пудру \1',
            r'гель\s+(\w+)': r'гель \1',
            r'пінка\s+(\w+)': r'пінку \1',
            r'флюїд\s+(\w+)': r'флюїд \1',
            r'крем\s+(\w+)': r'крем \1'
        }
        
        # Паттерны для склонения русских слов
        self.ru_declensions = {
            r'пудра\s+(\w+)': r'пудру \1',
            r'гель\s+(\w+)': r'гель \1',
            r'пенка\s+(\w+)': r'пенку \1',
            r'флюид\s+(\w+)': r'флюид \1',
            r'крем\s+(\w+)': r'крем \1'
        }
    
    def generate_note_buy(self, product_title: str, locale: str) -> str:
        """Генерирует коммерческую фразу по точной формуле ProRazko"""
        try:
            if locale == 'ua':
                declined_title = self.decline_title_ua(product_title)
                return f'У нашому інтернет-магазині ProRazko можна <strong>купити {declined_title.lower()}</strong> з швидкою доставкою по Україні.'
            else:  # ru
                declined_title = self.decline_title_ru(product_title)
                return f'В нашем интернет-магазине ProRazko можно <strong>купить {declined_title.lower()}</strong> с быстрой доставкой по Украине и гарантией качества.'
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации note_buy: {e}")
            return self._create_fallback_note_buy(product_title, locale)
    
    def decline_title_ua(self, title: str) -> str:
        """Склоняет украинский заголовок в знахідний відмінок (що купити?)"""
        declined = title.lower()
        
        # Специальные правила склонения для украинского
        transformations = {
            'пудра': 'пудру',
            'пінка': 'пінку',
            'ензимна': 'ензимну',
            'інтимна': 'інтимну',
            'гель': 'гель',  # не відмінюється
            'флюїд': 'флюїд',  # не відмінюється
            'для душу': 'для душу',  # не відмінюється
            'для очищення': 'для очищення',  # не відмінюється
            'для інтимної': 'для інтимної'  # не відмінюється
        }
        
        for original, declined_form in transformations.items():
            if original in declined:
                declined = declined.replace(original, declined_form)
        
        logger.info(f"✅ Украинское склонение: '{title}' -> '{declined}'")
        return declined
    
    def decline_title_ru(self, title: str) -> str:
        """Склоняет русский заголовок в винительный падеж (что купить?)"""
        declined = title.lower()
        
        # Специальные правила склонения для русского
        transformations = {
            'пудра': 'пудру',
            'пенка': 'пенку',
            'энзимная': 'энзимную',
            'интимная': 'интимную',
            'гель': 'гель',  # не склоняется
            'флюид': 'флюид',  # не склоняется
            'для душа': 'для душа',  # не склоняется
            'для очищения': 'для очищения',  # не склоняется
            'для интимной': 'для интимной'  # не склоняется
        }
        
        for original, declined_form in transformations.items():
            if original in declined:
                declined = declined.replace(original, declined_form)
        
        logger.info(f"✅ Русское склонение: '{title}' -> '{declined}'")
        return declined
    
    def _create_fallback_note_buy(self, product_title: str, locale: str) -> str:
        """Создает fallback коммерческую фразу"""
        if locale == 'ua':
            return f'У нашому інтернет-магазині ProRazko можна <strong>купити {product_title.lower()}</strong> з доставкою по Україні.'
        else:
            return f'В нашем интернет-магазине ProRazko можно <strong>купить {product_title.lower()}</strong> с доставкой по Украине.'