"""
Усиленный anti-generic фильтр для отсеивания заглушек и шаблонных ответов
"""
import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class AntiGenericFilter:
    """Фильтр для отсеивания generic ответов и заглушек"""
    
    def __init__(self):
        # Запрещенные фразы и паттерны
        self.forbidden_patterns = {
            'ru': [
                # Инструкции и упаковка
                r'согласно\s+инструкции',
                r'по\s+инструкции',
                r'на\s+упаковке',
                r'в\s+инструкции',
                r'следуйте\s+инструкции',
                r'читайте\s+инструкцию',
                
                # Общие места хранения
                r'в\s+сухом\s+прохладном\s+месте',
                r'в\s+сухом\s+месте',
                r'в\s+прохладном\s+месте',
                r'при\s+комнатной\s+температуре',
                r'в\s+темном\s+месте',
                
                # Общие противопоказания
                r'при\s+индивидуальной\s+непереносимости',
                r'при\s+аллергии',
                r'при\s+чувствительности',
                r'проконсультируйтесь\s+со\s+специалистом',
                r'проконсультируйтесь\s+с\s+врачом',
                
                # Общие ответы о безопасности
                r'безопасен\s+при\s+правильном\s+использовании',
                r'безопасен\s+для\s+всех\s+типов\s+кожи',
                r'подходит\s+для\s+всех\s+типов\s+кожи',
                r'гипоаллергенный',
                r'не\s+содержит\s+вредных\s+веществ',
                
                # Общие ответы о качестве
                r'высокое\s+качество',
                r'качественный\s+продукт',
                r'проверенный\s+производитель',
                r'надежный\s+бренд',
                r'отличный\s+результат',
                r'эффективный\s+продукт',
                
                # Общие ответы об использовании
                r'используйте\s+по\s+назначению',
                r'применяйте\s+по\s+назначению',
                r'следуйте\s+рекомендациям',
                r'соблюдайте\s+правила\s+использования',
                
                # Слишком короткие ответы
                r'^да\.?$',
                r'^нет\.?$',
                r'^не\s+указано\.?$',
                r'^не\s+вказано\.?$',
                r'^примерно\.?$',
                r'^приблизительно\.?$',
                r'^около\.?$',
                r'^близько\.?$'
            ],
            'ua': [
                # Інструкції та упаковка
                r'згідно\s+з\s+інструкцією',
                r'за\s+інструкцією',
                r'на\s+упаковці',
                r'в\s+інструкції',
                r'дотримуйтесь\s+інструкції',
                r'читайте\s+інструкцію',
                
                # Загальні місця зберігання
                r'в\s+сухому\s+прохолодному\s+місці',
                r'в\s+сухому\s+місці',
                r'в\s+прохолодному\s+місці',
                r'при\s+кімнатній\s+температурі',
                r'в\s+темному\s+місці',
                
                # Загальні протипоказання
                r'при\s+індивідуальній\s+непереносимості',
                r'при\s+алергії',
                r'при\s+чутливості',
                r'проконсультуйтеся\s+зі\s+спеціалістом',
                r'проконсультуйтеся\s+з\s+лікарем',
                
                # Загальні відповіді про безпеку
                r'безпечний\s+при\s+правильному\s+використанні',
                r'безпечний\s+для\s+всіх\s+типів\s+шкіри',
                r'підходить\s+для\s+всіх\s+типів\s+шкіри',
                r'гіпоалергенний',
                r'не\s+містить\s+шкідливих\s+речовин',
                
                # Загальні відповіді про якість
                r'висока\s+якість',
                r'якісний\s+продукт',
                r'перевірений\s+виробник',
                r'надійний\s+бренд',
                r'відмінний\s+результат',
                r'ефективний\s+продукт',
                
                # Загальні відповіді про використання
                r'використовуйте\s+за\s+призначенням',
                r'застосовуйте\s+за\s+призначенням',
                r'дотримуйтесь\s+рекомендацій',
                r'дотримуйтесь\s+правил\s+використання',
                
                # Занадто короткі відповіді
                r'^так\.?$',
                r'^ні\.?$',
                r'^не\s+вказано\.?$',
                r'^приблизно\.?$',
                r'^близько\.?$'
            ]
        }
        
        # Минимальные требования к качеству ответа
        self.quality_requirements = {
            'min_length': 20,  # Минимальная длина ответа
            'min_words': 3,    # Минимальное количество слов
            'max_generic_ratio': 0.3  # Максимальная доля generic фраз
        }

    def is_generic_answer(self, answer: str, locale: str) -> Tuple[bool, List[str]]:
        """
        Проверяет, является ли ответ generic/заглушкой
        
        Args:
            answer: Текст ответа
            locale: Локаль
            
        Returns:
            (is_generic, matched_patterns)
        """
        if not answer or not answer.strip():
            return True, ['empty_answer']
        
        answer_lower = answer.lower().strip()
        matched_patterns = []
        
        # Проверяем запрещенные паттерны
        if locale in self.forbidden_patterns:
            for pattern in self.forbidden_patterns[locale]:
                if re.search(pattern, answer_lower):
                    matched_patterns.append(pattern)
        
        # Проверяем минимальные требования
        if len(answer.strip()) < self.quality_requirements['min_length']:
            matched_patterns.append('too_short')
        
        word_count = len(answer.split())
        if word_count < self.quality_requirements['min_words']:
            matched_patterns.append('too_few_words')
        
        # Проверяем долю generic фраз
        if matched_patterns:
            generic_ratio = len(matched_patterns) / max(1, word_count)
            if generic_ratio > self.quality_requirements['max_generic_ratio']:
                matched_patterns.append('high_generic_ratio')
        
        is_generic = len(matched_patterns) > 0
        
        if is_generic:
            logger.debug(f"Generic ответ обнаружен: '{answer[:50]}...' - {matched_patterns}")
        
        return is_generic, matched_patterns

    def filter_generic_faq(self, faq_items: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """
        Фильтрует generic FAQ из списка
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            
        Returns:
            Отфильтрованный список FAQ
        """
        if not faq_items:
            return []
        
        filtered_items = []
        rejected_count = 0
        
        for item in faq_items:
            question = item.get('question', '') or item.get('q', '')
            answer = item.get('answer', '') or item.get('a', '')
            
            is_generic, patterns = self.is_generic_answer(answer, locale)
            
            if not is_generic:
                filtered_items.append(item)
                logger.debug(f"✅ FAQ принят: '{question[:30]}...'")
            else:
                rejected_count += 1
                logger.info(f"❌ FAQ отклонен (generic): '{question[:30]}...' - {patterns}")
        
        logger.info(f"Фильтрация generic FAQ: {len(faq_items)} → {len(filtered_items)} (отклонено: {rejected_count})")
        return filtered_items

    def validate_faq_quality(self, faq_items: List[Dict[str, str]], locale: str) -> Tuple[bool, List[str]]:
        """
        Валидирует качество FAQ списка
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            
        Returns:
            (is_valid, issues)
        """
        if not faq_items:
            return False, ['empty_faq_list']
        
        issues = []
        
        for i, item in enumerate(faq_items):
            question = item.get('question', '') or item.get('q', '')
            answer = item.get('answer', '') or item.get('a', '')
            
            # Проверяем наличие вопроса и ответа
            if not question.strip():
                issues.append(f'FAQ {i+1}: empty question')
                continue
            
            if not answer.strip():
                issues.append(f'FAQ {i+1}: empty answer')
                continue
            
            # Проверяем на generic
            is_generic, patterns = self.is_generic_answer(answer, locale)
            if is_generic:
                issues.append(f'FAQ {i+1}: generic answer - {patterns}')
        
        is_valid = len(issues) == 0
        
        if not is_valid:
            logger.warning(f"FAQ не прошел валидацию качества: {issues}")
        else:
            logger.info("✅ FAQ прошел валидацию качества")
        
        return is_valid, issues

    def get_quality_score(self, faq_items: List[Dict[str, str]], locale: str) -> float:
        """
        Вычисляет оценку качества FAQ
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            
        Returns:
            Оценка от 0.0 до 1.0
        """
        if not faq_items:
            return 0.0
        
        total_score = 0.0
        valid_items = 0
        
        for item in faq_items:
            answer = item.get('answer', '') or item.get('a', '')
            
            if not answer.strip():
                continue
            
            is_generic, patterns = self.is_generic_answer(answer, locale)
            
            if not is_generic:
                # Базовый балл за не-generic ответ
                base_score = 0.5
                
                # Бонус за длину
                length_bonus = min(0.3, len(answer.strip()) / 200)
                
                # Бонус за конкретность (отсутствие общих фраз)
                specificity_bonus = 0.2 if len(patterns) == 0 else 0.0
                
                item_score = base_score + length_bonus + specificity_bonus
                total_score += min(1.0, item_score)
                valid_items += 1
        
        if valid_items == 0:
            return 0.0
        
        return total_score / valid_items
