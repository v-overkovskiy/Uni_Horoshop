"""
Улучшенный генератор note_buy с правильным склонением и шаблонами
"""
import re
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class EnhancedNoteBuyGenerator:
    """Улучшенный генератор note_buy с симметричными шаблонами и склонением"""
    
    def __init__(self):
        # Шаблоны для RU и UA с двумя отдельными <strong> тегами
        self.templates = {
            'ru': "В нашем интернет-магазине ProRazko можно <strong>купить {np_acc_lowercased_first}</strong> с быстрой доставкой по Украине и гарантией качества.",
            'ua': "У нашому інтернет-магазині ProRazko можна <strong>купити {np_acc_lowercased_first}</strong> з швидкою доставкою по Україні та гарантією якості."
        }
        
        # Правила склонения для RU (винительный падеж)
        self.ru_declension_rules = {
            # Женский род на -ая/-яя
            'ая': 'ую',  # ароматическая → ароматическую
            'яя': 'юю',  # массажная → массажную
            # Простые окончания
            'а': 'у',  # красота → красоту
            'я': 'ю',  # земля → землю
        }
        
        # Правила склонения для UA (знахідний відмінок)
        self.ua_declension_rules = {
            # Жіночий рід на -а/-я
            'а': 'у',  # ароматична → ароматичну
            'я': 'ю',  # масажна → масажну
            # Винятки для складних випадків
            'ая': 'ую',  # красива → красиву
            'яя': 'юю',  # синя → синю
        }
        
        # Паттерны для определения рода и склонения
        self.gender_patterns = {
            'ru': {
                'feminine': [r'ая\b', r'яя\b', r'а\b', r'я\b'],
                'masculine': [r'ый\b', r'ий\b', r'ой\b', r'ый\b'],
                'neuter': [r'ое\b', r'ее\b', r'ое\b']
            },
            'ua': {
                'feminine': [r'а\b', r'я\b'],
                'masculine': [r'ий\b', r'ий\b'],
                'neuter': [r'е\b', r'е\b']
            }
        }

    def generate_enhanced_note_buy(self, title: str, locale: str) -> Dict[str, Any]:
        """
        Генерирует улучшенный note_buy с правильным склонением и новым шаблоном
        """
        logger.info(f"🔧 Генерация улучшенного note_buy для {locale}")
        
        if not title or not title.strip():
            return {
                'content': '',
                'has_kupit_kupyty': False,
                'declined': False,
                'two_strongs': False,
                'first_char_lowered': False,
                'declension_debug': {
                    'first_adj': '',
                    'first_noun': '',
                    'rules_applied': []
                },
                'lowercase_debug': {
                    'position': -1,
                    'original_char': '',
                    'lowercased_char': ''
                }
            }
        
        # Извлекаем первое прилагательное и первое существительное
        first_adj, first_noun = self._extract_first_words(title)
        
        # Применяем склонение
        declined_title, declension_info = self._apply_declension(title, first_adj, first_noun, locale)
        
        # Применяем понижение первого символа
        np_acc_lowercased_first, lowercase_debug = self._lowercase_first_grapheme(declined_title)
        
        # Генерируем контент с новым шаблоном
        template = self.templates[locale]
        content = template.format(np_acc_lowercased_first=np_acc_lowercased_first)
        
        # Проверяем наличие "купить/купити" и одного <strong> тега
        has_kupit = 'купить' in content if locale == 'ru' else 'купити' in content
        single_strong = content.count('<strong>') == 1
        first_char_lowered = lowercase_debug['position'] >= 0
        
        return {
            'content': content,
            'has_kupit_kupyty': has_kupit,
            'declined': declension_info['rules_applied'],
            'single_strong': single_strong,
            'range_from': 'купить' if locale == 'ru' else 'купити',
            'range_to': 'end_of_product_name',
            'first_char_lowered': first_char_lowered,
            'declension_debug': {
                'first_adj': first_adj,
                'first_noun': first_noun,
                'rules_applied': declension_info['rules_applied']
            },
            'lowercase_debug': lowercase_debug
        }

    def _extract_first_words(self, title: str) -> Tuple[str, str]:
        """Извлекает первое прилагательное и первое существительное"""
        words = title.split()
        
        first_adj = ''
        first_noun = ''
        
        for i, word in enumerate(words):
            # Очищаем слово от знаков препинания
            clean_word = re.sub(r'[^\w]', '', word)
            
            if not clean_word:
                continue
            
            # Определяем локаль по содержимому
            locale = 'ru' if any(char in title for char in 'ыъьэ') else 'ua'
            
            # Проверяем, является ли слово прилагательным
            if self._is_adjective(clean_word, locale):
                if not first_adj:
                    first_adj = clean_word
            # Проверяем, является ли слово существительным
            elif self._is_noun(clean_word, locale):
                if not first_noun:
                    first_noun = clean_word
                    break  # Берем только первое существительное
        
        return first_adj, first_noun

    def _is_adjective(self, word: str, locale: str) -> bool:
        """Проверяет, является ли слово прилагательным"""
        # Исключаем предлоги и служебные слова
        excluded_words = ['для', 'по', 'на', 'в', 'с', 'от', 'до', 'за', 'под', 'над', 'при', 'без', 'из', 'к', 'о', 'об', 'про', 'со', 'во']
        if word.lower() in excluded_words:
            return False
        
        if locale == 'ru':
            # Русские прилагательные
            adjective_endings = ['ый', 'ий', 'ой', 'ая', 'яя', 'ое', 'ее']
        else:
            # Украинские прилагательные
            adjective_endings = ['ий', 'а', 'я', 'е', 'е']
        
        return any(word.endswith(ending) for ending in adjective_endings)

    def _is_noun(self, word: str, locale: str) -> bool:
        """Проверяет, является ли слово существительным"""
        # Исключаем предлоги и служебные слова
        excluded_words = ['для', 'по', 'на', 'в', 'с', 'от', 'до', 'за', 'под', 'над', 'при', 'без', 'из', 'к', 'о', 'об', 'про', 'со', 'во']
        if word.lower() in excluded_words:
            return False
        
        if locale == 'ru':
            # Русские существительные
            noun_endings = ['а', 'я', 'о', 'е', 'ь', 'и', 'ы']
        else:
            # Украинские существительные
            noun_endings = ['а', 'я', 'о', 'е', 'ь', 'и', 'и']
        
        return any(word.endswith(ending) for ending in noun_endings)

    def _apply_declension(self, title: str, first_adj: str, first_noun: str, locale: str) -> Tuple[str, Dict[str, Any]]:
        """Применяет склонение к заголовку с исправлением дублирования леммы"""
        if not first_adj and not first_noun:
            return title, {'rules_applied': []}
        
        # Проверяем, нужно ли склонять
        if not self._should_decline(first_adj, first_noun, locale):
            return title, {'rules_applied': []}
        
        words = title.split()
        rules_applied = []
        
        # Склоняем только первые два слова (прилагательное + существительное)
        # чтобы избежать дублирования леммы
        for i, word in enumerate(words[:2]):  # Ограничиваем первыми двумя словами
            clean_word = re.sub(r'[^\w]', '', word)
            
            if not clean_word:
                continue
            
            # Определяем тип слова
            is_adj = self._is_adjective(clean_word, locale)
            is_noun = self._is_noun(clean_word, locale)
            
            if (is_adj or is_noun) and self._is_feminine(clean_word, locale):
                if is_adj:
                    declined_word = self._decline_adjective(clean_word, locale)
                    word_type = 'adj'
                else:
                    declined_word = self._decline_noun(clean_word, locale)
                    word_type = 'noun'
                
                if declined_word != clean_word:
                    # Заменяем слово в исходном тексте, сохраняя знаки препинания
                    original_word = words[i]
                    # Находим позицию чистого слова в исходном
                    clean_start = original_word.find(clean_word)
                    if clean_start >= 0:
                        # Заменяем только чистую часть, сохраняя знаки препинания
                        new_word = original_word[:clean_start] + declined_word + original_word[clean_start + len(clean_word):]
                        words[i] = new_word
                        rules_applied.append(f'{word_type}_{clean_word}→{declined_word}')
        
        return ' '.join(words), {'rules_applied': rules_applied}

    def _should_decline(self, first_adj: str, first_noun: str, locale: str) -> bool:
        """Определяет, нужно ли склонять слова"""
        # Склоняем если есть прилагательное женского рода
        adj_feminine = self._is_feminine(first_adj, locale) if first_adj else False
        noun_feminine = self._is_feminine(first_noun, locale) if first_noun else False
        
        # Склоняем если есть хотя бы одно слово женского рода
        return adj_feminine or noun_feminine

    def _is_feminine(self, word: str, locale: str) -> bool:
        """Проверяет, является ли слово женского рода"""
        patterns = self.gender_patterns[locale]['feminine']
        
        for pattern in patterns:
            if re.search(pattern, word):
                return True
        
        # Дополнительная проверка для слов, заканчивающихся на -а, -я
        if word.endswith(('а', 'я')):
            return True
        
        return False

    def _decline_adjective(self, adj: str, locale: str) -> str:
        """Склоняет прилагательное"""
        rules = self.ru_declension_rules if locale == 'ru' else self.ua_declension_rules
        
        # Применяем правила склонения в порядке убывания длины окончания
        # Сначала проверяем длинные окончания, потом короткие
        sorted_rules = sorted(rules.items(), key=lambda x: len(x[0]), reverse=True)
        
        for ending, replacement in sorted_rules:
            if adj.endswith(ending):
                return adj[:-len(ending)] + replacement
        
        return adj

    def _decline_noun(self, noun: str, locale: str) -> str:
        """Склоняет существительное"""
        # Для существительных женского рода на -а/-я
        if locale == 'ru':
            if noun.endswith('а'):
                return noun[:-1] + 'у'
            elif noun.endswith('я'):
                return noun[:-1] + 'ю'
        else:  # ua
            if noun.endswith('а'):
                return noun[:-1] + 'у'
            elif noun.endswith('я'):
                return noun[:-1] + 'ю'
        
        return noun

    def _lowercase_first_grapheme(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Приводит к нижнему регистру только первый буквенный символ
        """
        if not text:
            return text, {'position': -1, 'original_char': '', 'lowercased_char': ''}
        
        # Ищем первый буквенный символ (кириллица/латиница)
        for i, char in enumerate(text):
            if char.isalpha():
                # Проверяем, не является ли это брендом (латиница в верхнем регистре)
                if char.isupper() and char.isascii():
                    # Проверяем, не является ли это частью бренда
                    word_start = i
                    while word_start > 0 and text[word_start - 1].isalnum():
                        word_start -= 1
                    
                    word_end = i
                    while word_end < len(text) and text[word_end].isalnum():
                        word_end += 1
                    
                    word = text[word_start:word_end]
                    
                    # Если это бренд (все символы латиница в верхнем регистре), пропускаем
                    if word.isalpha() and word.isupper() and word.isascii() and len(word) > 1:
                        continue
                
                # Приводим к нижнему регистру
                lowercased_text = text[:i] + char.lower() + text[i+1:]
                
                return lowercased_text, {
                    'position': i,
                    'original_char': char,
                    'lowercased_char': char.lower()
                }
        
        # Если не найдено буквенных символов
        return text, {'position': -1, 'original_char': '', 'lowercased_char': ''}

    def get_diagnostic_info(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Возвращает диагностическую информацию"""
        return {
            'note_buy_has_kupit_kupyty': result['has_kupit_kupyty'],
            'note_buy_declined': result['declined'],
            'note_buy_single_strong': result['single_strong'],
            'note_buy_range_from': result['range_from'],
            'note_buy_range_to': result['range_to'],
            'note_buy_first_char_lowered': result['first_char_lowered'],
            'note_buy_before': '',  # Будет заполнено в вызывающем коде
            'note_buy_after': result['content'],
            'declension_debug': result['declension_debug'],
            'lowercase_debug': result['lowercase_debug']
        }
    
    def generate(self, product_data: Dict[str, Any], locale: str) -> str:
        """
        Генерирует note_buy с использованием актуального заголовка из объекта
        """
        try:
            # Используем заголовок из объекта, а НЕ парсим заново из HTML
            title = product_data.get('title', '')
            
            if not title:
                # Fallback: пытаемся извлечь заголовок из фактов
                title = self._extract_title_from_facts(product_data, locale)
            
            if not title:
                # Последний fallback
                title = f"Epilax, 5 мл" if locale == 'ru' else f"Epilax, 5 мл"
                logger.warning(f"⚠️ Используем fallback заголовок: {title}")
            
            # Генерируем note_buy с актуальным заголовком
            result = self.generate_enhanced_note_buy(title, locale)
            return result['content']
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации note_buy: {e}")
            # Fallback note_buy
            if locale == 'ua':
                return "У нашому інтернет-магазині ProRazko можна <strong>купити товар</strong>"
            else:
                return "В нашем интернет-магазине ProRazko можно <strong>купить товар</strong>"
    
    def _extract_title_from_facts(self, product_data: Dict[str, Any], locale: str) -> str:
        """Извлекает заголовок из фактов о товаре"""
        try:
            facts = product_data.get('facts', {})
            brand = facts.get('brand', 'Epilax')
            volume = facts.get('volume', '')
            weight = facts.get('weight', '')
            
            size_info = volume or weight
            if size_info:
                return f"{brand}, {size_info}"
            else:
                return brand
                
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения заголовка из фактов: {e}")
            return f"Epilax, 5 мл" if locale == 'ru' else f"Epilax, 5 мл"