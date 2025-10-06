"""
Валидатор локализации для проверки корректности RU/UA контента
"""
import re
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class LocaleValidator:
    """Валидатор для проверки корректности локализации контента"""
    
    def __init__(self):
        # Словарь нормализации UA-лексем
        self.ua_normalization = {
            # Исправления орфографии
            'Жосткі': 'Жорсткі',
            'Горячий': 'Гарячий',
            'Лице': 'Обличчя',
            'Тип воску': 'Тип віску',
            'Область застосування': 'Область застосування',  # уже правильно
            'Температура': 'Температура',  # уже правильно
            'Вага': 'Вага',  # уже правильно
            'Об\'єм': 'Об\'єм',  # уже правильно
            'Матеріал': 'Матеріал',  # уже правильно
            'Колір': 'Колір',  # уже правильно
            'Серія': 'Серія',  # уже правильно
            'Клас': 'Клас',  # уже правильно
            'SPF': 'SPF',  # уже правильно
            'Зони': 'Зони',  # уже правильно
        }
        
        # Нейтральные слова, которые не должны блокировать валидацию
        self.neutral_whitelist = {
            'ru': ['результат', 'максимум', 'минимум', 'оптимум', 'продукт', 'материал', 'классификация', 'класс', 'клас'],
            'ua': ['результат', 'максимум', 'мінімум', 'оптимум', 'продукт', 'матеріал', 'класифікація', 'клас']
        }
        
        # RU-лексемы, которые не должны встречаться в UA-контенте (только ключи-спецификации)
        self.ru_forbidden_in_ua = [
            'Область применения', 'Температура плавления', 'Вес', 'Объем', 'Материал',
            'Цвет', 'Серия', 'Зоны', 'Тип кожи', 'Тип волос', 'Минимальная длина',
            'Применение', 'Назначение', 'Классификация косметического средства',
            'Производитель', 'Страна', 'Объём упаковки'
        ]
        
        # UA-лексемы, которые не должны встречаться в RU-контенте (только ключи-спецификации)
        self.ua_forbidden_in_ru = [
            'Область застосування', 'Температура плавлення', 'Вага', 'Об\'єм', 'Матеріал',
            'Колір', 'Серія', 'Зони', 'Тип шкіри', 'Тип волосся', 'Мінімальна довжина',
            'Застосування', 'Призначення', 'Класифікація косметичного засобу',
            'Виробник', 'Країна', 'Об\'єм упаковки'
        ]
        
        # Паттерны анти-заглушек
        self.placeholder_patterns = [
            r'^\.+$',  # Только точки
            r'^\.\s*$',  # Точка с пробелами
            r'^\.\s*\.\s*$',  # Множественные точки
            r'^\.\s*<p>\s*\.\s*</p>\s*$',  # HTML с точками
            r'^Не вказано$',  # "Не указано"
            r'^N/A$',  # N/A
            r'^\.\.\.+$',  # Многоточия
            r'^<strong>\s*купити\s*</strong>$',  # Пустой strong
            r'^<strong>\s*купить\s*</strong>$',  # Пустой strong RU
        ]
        
        # Приоритетный список для характеристик
        self.specs_priority = [
            'Бренд', 'бренд', 'Brand', 'brand',
            'Тип', 'тип', 'Type', 'type',
            'Об\'єм', 'об\'єм', 'Объем', 'объем', 'Вага', 'вага', 'Вес', 'вес',
            'Матеріал', 'матеріал', 'Материал', 'материал',
            'Температура', 'температура', 'Temperature', 'temperature',
            'Зони', 'зони', 'Зоны', 'зоны', 'Область', 'область',
            'Серія', 'серія', 'Серия', 'серия', 'Клас', 'клас', 'Класс', 'класс', 'SPF', 'spf',
            'Колір', 'колір', 'Цвет', 'цвет'
        ]

    def validate_locale_content(self, content: str, locale: str) -> Tuple[bool, List[str]]:
        """
        Валидирует контент на соответствие локали
        Возвращает (is_valid, errors)
        """
        errors = []
        
        if locale == 'ua':
            # Проверяем на наличие RU-лексем в UA-контенте
            for ru_word in self.ru_forbidden_in_ua:
                if ru_word in content:
                    # Проверяем, не является ли это нейтральным словом
                    if not self._is_neutral_word(ru_word, locale):
                        errors.append(f"RU-лексема '{ru_word}' найдена в UA-контенте")
            
            # Проверяем орфографические ошибки
            if 'Жосткі' in content:
                errors.append("Орфографическая ошибка: 'Жосткі' должно быть 'Жорсткі'")
            
            if 'Горячий' in content:
                errors.append("RU-лексема 'Горячий' в UA-контенте, должно быть 'Гарячий'")
            
            if 'Лице' in content:
                errors.append("RU-лексема 'Лице' в UA-контенте, должно быть 'Обличчя'")
        
        elif locale == 'ru':
            # Проверяем на наличие UA-лексем в RU-контенте
            for ua_word in self.ua_forbidden_in_ru:
                if ua_word in content:
                    # Проверяем, не является ли это нейтральным словом
                    if not self._is_neutral_word(ua_word, locale):
                        errors.append(f"UA-лексема '{ua_word}' найдена в RU-контенте")
        
        # Проверяем анти-заглушки
        for pattern in self.placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                errors.append(f"Найдена заглушка: '{content[:50]}...'")
        
        return len(errors) == 0, errors
    
    def _is_neutral_word(self, word: str, locale: str) -> bool:
        """Проверяет, является ли слово нейтральным для данной локали"""
        neutral_words = self.neutral_whitelist.get(locale, [])
        return word.lower() in [w.lower() for w in neutral_words]

    def validate_specs_locale_strict(self, specs: List[Dict], locale: str) -> Tuple[bool, List[str]]:
        """
        Строго валидирует характеристики на смешение локалей с матчингом по слову-целиком
        Возвращает (is_valid, errors)
        """
        errors = []
        
        for i, spec in enumerate(specs):
            name = spec.get('name', '') or spec.get('label', '')
            value = spec.get('value', '')
            
            # Нормализуем апострофы перед проверкой
            name_normalized = self._normalize_apostrophes(name)
            value_normalized = self._normalize_apostrophes(value)
            
            # Проверяем название характеристики
            if locale == 'ua':
                for ru_word in self.ru_forbidden_in_ua:
                    if self._match_word_whole(ru_word, name_normalized):
                        # Проверяем, не является ли это нейтральным словом
                        if not self._is_neutral_word(ru_word, locale):
                            errors.append(f"RU-лексема '{ru_word}' в названии характеристики UA: '{name}'")
                    if self._match_word_whole(ru_word, value_normalized):
                        if not self._is_neutral_word(ru_word, locale):
                            errors.append(f"RU-лексема '{ru_word}' в значении характеристики UA: '{value}'")
            elif locale == 'ru':
                for ua_word in self.ua_forbidden_in_ru:
                    if self._match_word_whole(ua_word, name_normalized):
                        # Проверяем, не является ли это нейтральным словом
                        if not self._is_neutral_word(ua_word, locale):
                            errors.append(f"UA-лексема '{ua_word}' в названии характеристики RU: '{name}'")
                    if self._match_word_whole(ua_word, value_normalized):
                        if not self._is_neutral_word(ua_word, locale):
                            errors.append(f"UA-лексема '{ua_word}' в значении характеристики RU: '{value}'")
                
                # Дополнительная проверка на UA-буквы с границами слов для RU
                ua_letters_pattern = r'\b[іїєґІЇЄҐ]\w*\b'
                if re.search(ua_letters_pattern, name):
                    errors.append(f"UA-буквы в названии характеристики RU: '{name}'")
                if re.search(ua_letters_pattern, value):
                    errors.append(f"UA-буквы в значении характеристики RU: '{value}'")
        
        return len(errors) == 0, errors
    
    def _normalize_apostrophes(self, text: str) -> str:
        """Нормализует различные варианты апострофов в тексте"""
        if not text:
            return text
        
        # Заменяем все варианты апострофов на стандартный
        apostrophes = ['\'', ''', ''', '`', '´']
        normalized = text
        for apostrophe in apostrophes:
            normalized = normalized.replace(apostrophe, '\'')
        
        return normalized
    
    def _match_word_whole(self, word: str, text: str) -> bool:
        """Проверяет точное совпадение слова с границами слов"""
        if not word or not text:
            return False
        
        # Экранируем специальные символы для regex
        import re
        escaped_word = re.escape(word)
        
        # Паттерн для поиска слова целиком с возможным двоеточием
        pattern = r'\b' + escaped_word + r':?\b'
        
        return bool(re.search(pattern, text, re.IGNORECASE))

    def normalize_ua_content(self, content: str) -> str:
        """
        Нормализует UA-контент, заменяя RU-лексемы на правильные UA
        """
        normalized = content
        
        for ru_word, ua_word in self.ua_normalization.items():
            normalized = normalized.replace(ru_word, ua_word)
        
        return normalized

    def validate_specs_range(self, specs: List[Dict], locale: str) -> Tuple[bool, List[str], bool]:
        """
        Валидирует количество характеристик (3-8) и возвращает усеченный список
        Возвращает (is_valid, errors, was_clamped)
        """
        errors = []
        was_clamped = False
        
        if len(specs) < 3:
            errors.append(f"Недостаточно характеристик: {len(specs)} < 3")
            return False, errors, False
        
        if len(specs) > 8:
            was_clamped = True
            logger.info(f"Характеристики усечены с {len(specs)} до 8 для {locale}")
        
        return len(specs) >= 3, errors, was_clamped

    def prioritize_specs(self, specs: List[Dict], locale: str) -> List[Dict]:
        """
        Приоритизирует характеристики по заданному порядку
        """
        if len(specs) <= 8:
            return specs
        
        # Создаем словарь для быстрого поиска
        specs_dict = {}
        for spec in specs:
            key = spec.get('name', '').strip()
            if key:
                specs_dict[key] = spec
        
        # Отбираем по приоритету
        prioritized = []
        used_keys = set()
        
        for priority_key in self.specs_priority:
            for spec_key, spec in specs_dict.items():
                if (priority_key.lower() in spec_key.lower() or 
                    spec_key.lower() in priority_key.lower()) and spec_key not in used_keys:
                    prioritized.append(spec)
                    used_keys.add(spec_key)
                    if len(prioritized) >= 8:
                        break
            if len(prioritized) >= 8:
                break
        
        # Если не набрали 8, добавляем оставшиеся
        if len(prioritized) < 8:
            for spec_key, spec in specs_dict.items():
                if spec_key not in used_keys:
                    prioritized.append(spec)
                    if len(prioritized) >= 8:
                        break
        
        return prioritized[:8]

    def validate_structure(self, blocks: Dict, locale: str) -> Tuple[bool, List[str]]:
        """
        Валидирует структуру блоков контента
        """
        errors = []
        
        # Проверяем заголовок
        title = blocks.get('title', '')
        if not title or title.strip() == '':
            errors.append(f"Отсутствует заголовок prod-title для {locale}")
        
        # Проверяем описание
        description = blocks.get('description', '')
        if not description or description.strip() == '' or description.strip() == '.':
            errors.append(f"Пустое или некорректное описание для {locale}")
        
        # Проверяем note-buy
        note_buy = blocks.get('note_buy', '')
        if not note_buy or '<strong>купити </strong>' in note_buy or '<strong>купить </strong>' in note_buy:
            errors.append(f"Пустой или некорректный note-buy для {locale}")
        
        # Проверяем FAQ
        faq = blocks.get('faq', [])
        if not faq or len(faq) < 6:
            errors.append(f"Недостаточно FAQ для {locale}: {len(faq) if faq else 0} < 6")
        
        # Проверяем характеристики
        specs = blocks.get('specs', [])
        if len(specs) < 3:
            errors.append(f"Недостаточно характеристик для {locale}: {len(specs)} < 3")
        
        return len(errors) == 0, errors

    def validate_anti_placeholders(self, content: str) -> Tuple[bool, List[str]]:
        """
        Проверяет контент на наличие заглушек
        """
        errors = []
        
        for pattern in self.placeholder_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                errors.append(f"Найдена заглушка: '{content[:50]}...'")
        
        return len(errors) == 0, errors
