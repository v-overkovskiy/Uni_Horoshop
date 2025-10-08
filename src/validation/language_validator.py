"""
Универсальный валидатор языка для любых товаров
"""
import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

class LanguageValidator:
    """Универсальная проверка языка контента"""
    
    # Буквы характерные ТОЛЬКО для украинского
    UKRAINIAN_LETTERS = set('ґєії')
    
    # Буквы характерные ТОЛЬКО для русского
    RUSSIAN_LETTERS = set('ыэъё')
    
    # Частые украинские служебные слова
    UKRAINIAN_WORDS = {
        'це', 'цей', 'ця', 'цього', 'цієї',
        'який', 'яка', 'яке', 'які',
        'буде', 'будуть', 'буває',
        'також', 'навіть', 'через',
        'може', 'можна', 'треба',
        'та', 'й', 'із', 'зі', 'від', 'до', 'на', 'з'
    }
    
    # Частые русские служебные слова
    RUSSIAN_WORDS = {
        'это', 'этот', 'эта', 'этого', 'этой',
        'который', 'которая', 'которое', 'которые',
        'будет', 'будут', 'бывает',
        'также', 'даже', 'через',
        'может', 'можно', 'нужно',
        'и', 'из', 'от', 'до', 'на', 'с'
    }
    
    def validate_text_language(self, text: str, expected_locale: str) -> Tuple[bool, str]:
        """
        Универсальная проверка языка текста
        
        Returns:
            (is_valid, error_message)
        """
        if not text or len(text) < 10:
            return True, ""
        
        text_lower = text.lower()
        
        # МЕТОД 1: Проверка по характерным буквам
        ukrainian_letter_found = any(letter in text_lower for letter in self.UKRAINIAN_LETTERS)
        russian_letter_found = any(letter in text_lower for letter in self.RUSSIAN_LETTERS)
        
        if expected_locale == 'ru':
            if ukrainian_letter_found:
                found_letters = [l for l in self.UKRAINIAN_LETTERS if l in text_lower]
                return False, f"В RU тексте найдены украинские буквы: {found_letters}"
        
        elif expected_locale == 'ua':
            if russian_letter_found:
                found_letters = [l for l in self.RUSSIAN_LETTERS if l in text_lower]
                return False, f"В UA тексте найдены русские буквы: {found_letters}"
        
        # МЕТОД 2: Проверка по служебным словам
        words = re.findall(r'\b\w+\b', text_lower)
        
        if expected_locale == 'ru':
            # Считаем украинские служебные слова
            ua_word_count = sum(1 for word in words if word in self.UKRAINIAN_WORDS)
            if ua_word_count > 3:  # Порог: более 3 украинских слов
                return False, f"В RU тексте найдено {ua_word_count} украинских служебных слов"
        
        elif expected_locale == 'ua':
            # Считаем русские служебные слова
            ru_word_count = sum(1 for word in words if word in self.RUSSIAN_WORDS)
            if ru_word_count > 10:  # Порог: более 10 русских слов (мягче для смешанных текстов)
                return False, f"В UA тексте найдено {ru_word_count} русских служебных слов"
        
        # МЕТОД 3: Использование langdetect (опционально)
        try:
            from langdetect import detect, LangDetectException
            
            detected_lang = detect(text)
            expected_lang = 'ru' if expected_locale == 'ru' else 'uk'
            
            if detected_lang != expected_lang:
                logger.warning(f"⚠️ langdetect определил язык как {detected_lang}, ожидалось {expected_lang}")
                # НЕ возвращаем False - langdetect не всегда точен
        
        except ImportError:
            logger.debug("langdetect не установлен")
        except Exception as e:
            logger.debug(f"langdetect не смог определить язык: {e}")
        
        return True, ""
    
    def detect_language(self, text: str) -> str:
        """
        Определить язык текста (ru или ua)
        
        Returns:
            'ru', 'ua', или 'unknown'
        """
        if not text or len(text) < 10:
            return 'unknown'
        
        text_lower = text.lower()
        
        # Проверка по характерным буквам
        has_ukrainian_letters = any(letter in text_lower for letter in self.UKRAINIAN_LETTERS)
        has_russian_letters = any(letter in text_lower for letter in self.RUSSIAN_LETTERS)
        
        if has_ukrainian_letters and not has_russian_letters:
            return 'ua'
        elif has_russian_letters and not has_ukrainian_letters:
            return 'ru'
        
        # Проверка по служебным словам
        words = re.findall(r'\b\w+\b', text_lower)
        ua_words = sum(1 for word in words if word in self.UKRAINIAN_WORDS)
        ru_words = sum(1 for word in words if word in self.RUSSIAN_WORDS)
        
        if ua_words > ru_words:
            return 'ua'
        elif ru_words > ua_words:
            return 'ru'
        
        # Fallback: используем langdetect с исправлением для болгарского
        try:
            from langdetect import detect
            detected = detect(text)
            
            # ИСПРАВЛЕНИЕ: Если langdetect определил как болгарский (bg), 
            # но в тексте есть украинские буквы - скорее всего это украинский
            if detected == 'bg' and has_ukrainian_letters:
                logger.warning(f"🔧 Исправление: langdetect определил как 'bg', но найдены украинские буквы - считаем 'ua'")
                return 'ua'
            
            return 'ua' if detected == 'uk' else detected
        except:
            return 'unknown'
    
    def validate_content_language(self, content: dict, locale: str) -> Tuple[bool, str]:
        """
        Валидация языка всего контента (описание, FAQ, etc.)
        
        Returns:
            (is_valid, error_message)
        """
        # Проверяем описание
        description = content.get('description', '')
        if isinstance(description, list):
            description = ' '.join(description)
        
        is_valid, error = self.validate_text_language(description, locale)
        if not is_valid:
            return False, f"Описание: {error}"
        
        # Проверяем FAQ
        faq_list = content.get('faq', [])
        for i, faq_item in enumerate(faq_list):
            if isinstance(faq_item, dict):
                question = faq_item.get('question', '')
                answer = faq_item.get('answer', '')
                
                # Проверяем вопрос
                is_valid, error = self.validate_text_language(question, locale)
                if not is_valid:
                    return False, f"FAQ[{i}] вопрос: {error}"
                
                # Проверяем ответ
                is_valid, error = self.validate_text_language(answer, locale)
                if not is_valid:
                    return False, f"FAQ[{i}] ответ: {error}"
        
        # Проверяем преимущества
        advantages = content.get('advantages', [])
        for i, advantage in enumerate(advantages):
            is_valid, error = self.validate_text_language(advantage, locale)
            if not is_valid:
                return False, f"Преимущество[{i}]: {error}"
        
        # Проверяем коммерческую фразу
        note_buy = content.get('note_buy', '')
        is_valid, error = self.validate_text_language(note_buy, locale)
        if not is_valid:
            return False, f"Коммерческая фраза: {error}"
        
        return True, ""
