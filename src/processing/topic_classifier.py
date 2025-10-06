"""
Классификатор тем для FAQ вопросов
"""
import re
import logging
from typing import Dict, List, Set, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TopicMatch:
    """Результат классификации темы"""
    topic: str
    confidence: float
    matched_patterns: List[str]

class TopicClassifier:
    """Классификатор тем для FAQ вопросов"""
    
    def __init__(self):
        # Паттерны для определения тем вопросов
        self.topic_patterns = {
            'storage': {
                'ru': [
                    r'как\s+хранить',
                    r'где\s+хранить',
                    r'условия\s+хранения',
                    r'температура\s+хранения',
                    r'срок\s+хранения',
                    r'збер[её]гание',
                    r'хранение'
                ],
                'ua': [
                    r'як\s+збер[іи]гати',
                    r'де\s+збер[іи]гати',
                    r'умови\s+збер[іи]гання',
                    r'температура\s+збер[іи]гання',
                    r'терм[іи]н\s+збер[іи]гання',
                    r'збер[іи]гання'
                ]
            },
            'skin_type': {
                'ru': [
                    r'тип\s+кожи',
                    r'для\s+какой\s+кожи',
                    r'подходит\s+ли\s+для',
                    r'чувствительная\s+кожа',
                    r'сухая\s+кожа',
                    r'жирная\s+кожа',
                    r'комбинированная\s+кожа',
                    r'кожа'
                ],
                'ua': [
                    r'тип\s+шк[іи]ри',
                    r'для\s+яко[іи]\s+шк[іи]ри',
                    r'підходить\s+чи\s+для',
                    r'чутлива\s+шк[іи]ра',
                    r'суха\s+шк[іи]ра',
                    r'жирна\s+шк[іи]ра',
                    r'комбінована\s+шк[іи]ра',
                    r'шк[іи]ра'
                ]
            },
            'contraindications': {
                'ru': [
                    r'противопоказания',
                    r'противопоказано',
                    r'нельзя\s+использовать',
                    r'ограничения',
                    r'осторожно',
                    r'беременность',
                    r'кормление'
                ],
                'ua': [
                    r'протипоказання',
                    r'протипоказано',
                    r'не можна\s+використовувати',
                    r'обмеження',
                    r'обережно',
                    r'вагітність',
                    r'годування'
                ]
            },
            'volume_weight': {
                'ru': [
                    r'объ[её]м',
                    r'сколько\s+мл',
                    r'сколько\s+литр',
                    r'вес',
                    r'сколько\s+весит',
                    r'грамм',
                    r'килограм'
                ],
                'ua': [
                    r'об\'[еє]м',
                    r'ск[іи]льки\s+мл',
                    r'ск[іи]льки\s+л[іи]тр',
                    r'вага',
                    r'ск[іи]льки\s+важить',
                    r'грам',
                    r'к[іи]лограм'
                ]
            },
            'usage': {
                'ru': [
                    r'как\s+использовать',
                    r'как\s+применять',
                    r'способ\s+применения',
                    r'инструкция',
                    r'метод\s+использования',
                    r'использование'
                ],
                'ua': [
                    r'як\s+використовувати',
                    r'як\s+застосовувати',
                    r'спосіб\s+застосування',
                    r'інструкція',
                    r'метод\s+використання',
                    r'використання'
                ]
            },
            'safety': {
                'ru': [
                    r'безопасно\s+ли',
                    r'безопасность',
                    r'гипоаллергенно',
                    r'аллергия',
                    r'побочные\s+эффекты',
                    r'вредно\s+ли'
                ],
                'ua': [
                    r'безпечно\s+чи',
                    r'безпека',
                    r'гіпоалергенно',
                    r'алергія',
                    r'побічні\s+ефекти',
                    r'шкідливо\s+чи'
                ]
            },
            'composition': {
                'ru': [
                    r'состав',
                    r'из\s+чего\s+сделан',
                    r'компоненты',
                    r'ингредиенты',
                    r'материал',
                    r'вещества'
                ],
                'ua': [
                    r'склад',
                    r'з\s+чого\s+зроблений',
                    r'компоненти',
                    r'інгредієнти',
                    r'матеріал',
                    r'речовини'
                ]
            },
            'effect': {
                'ru': [
                    r'эффект',
                    r'результат',
                    r'действие',
                    r'что\s+даст',
                    r'какой\s+эффект',
                    r'работает\s+ли'
                ],
                'ua': [
                    r'ефект',
                    r'результат',
                    r'дія',
                    r'що\s+дасть',
                    r'який\s+ефект',
                    r'працює\s+чи'
                ]
            }
        }
        
        # Приоритеты тем (чем выше, тем важнее)
        self.topic_priority = {
            'volume_weight': 10,
            'composition': 9,
            'usage': 8,
            'effect': 7,
            'safety': 6,
            'skin_type': 5,
            'storage': 4,
            'contraindications': 3
        }

    def classify_question(self, question: str, locale: str) -> Optional[TopicMatch]:
        """
        Классифицирует вопрос по теме
        
        Args:
            question: Текст вопроса
            locale: Локаль ('ru' или 'ua')
            
        Returns:
            TopicMatch или None если тема не определена
        """
        if locale not in ['ru', 'ua']:
            logger.warning(f"Неподдерживаемая локаль: {locale}")
            return None
        
        question_lower = question.lower().strip()
        best_match = None
        best_confidence = 0.0
        
        for topic, patterns in self.topic_patterns.items():
            if locale not in patterns:
                continue
                
            matched_patterns = []
            for pattern in patterns[locale]:
                if re.search(pattern, question_lower):
                    matched_patterns.append(pattern)
            
            if matched_patterns:
                # Подсчитываем уверенность на основе количества совпадений
                confidence = len(matched_patterns) / len(patterns[locale])
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = TopicMatch(
                        topic=topic,
                        confidence=confidence,
                        matched_patterns=matched_patterns
                    )
        
        if best_match and best_confidence > 0.1:  # Минимальный порог уверенности
            logger.debug(f"Вопрос '{question[:50]}...' классифицирован как '{best_match.topic}' (уверенность: {best_confidence:.2f})")
            return best_match
        
        logger.debug(f"Не удалось классифицировать вопрос: '{question[:50]}...'")
        return None

    def get_topic_priority(self, topic: str) -> int:
        """Возвращает приоритет темы"""
        return self.topic_priority.get(topic, 0)

    def deduplicate_by_topic(self, faq_items: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """
        Дедуплицирует FAQ по темам, оставляя только один вопрос на тему
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            
        Returns:
            Дедуплицированный список FAQ
        """
        if not faq_items:
            return []
        
        # Классифицируем все вопросы
        classified_items = []
        for item in faq_items:
            question = item.get('question', '') or item.get('q', '')
            topic_match = self.classify_question(question, locale)
            
            classified_items.append({
                'item': item,
                'topic': topic_match.topic if topic_match else 'unknown',
                'confidence': topic_match.confidence if topic_match else 0.0,
                'priority': self.get_topic_priority(topic_match.topic if topic_match else 'unknown')
            })
        
        # Сортируем по приоритету темы и уверенности
        classified_items.sort(key=lambda x: (x['priority'], x['confidence']), reverse=True)
        
        # Отбираем уникальные темы
        seen_topics = set()
        deduplicated = []
        
        for classified_item in classified_items:
            topic = classified_item['topic']
            
            if topic not in seen_topics:
                seen_topics.add(topic)
                deduplicated.append(classified_item['item'])
                logger.info(f"✅ Выбран FAQ по теме '{topic}': {classified_item['item'].get('question', '')[:50]}...")
            else:
                logger.info(f"❌ Отброшен дубликат темы '{topic}': {classified_item['item'].get('question', '')[:50]}...")
        
        logger.info(f"Дедупликация завершена: {len(faq_items)} → {len(deduplicated)} FAQ")
        return deduplicated

    def get_missing_topics(self, faq_items: List[Dict[str, str]], locale: str) -> List[str]:
        """
        Определяет недостающие темы в FAQ
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            
        Returns:
            Список недостающих тем
        """
        if not faq_items:
            return list(self.topic_priority.keys())
        
        # Определяем уже использованные темы
        used_topics = set()
        for item in faq_items:
            question = item.get('question', '') or item.get('q', '')
            topic_match = self.classify_question(question, locale)
            if topic_match:
                used_topics.add(topic_match.topic)
        
        # Возвращаем недостающие темы, отсортированные по приоритету
        missing_topics = []
        for topic, priority in sorted(self.topic_priority.items(), key=lambda x: x[1], reverse=True):
            if topic not in used_topics:
                missing_topics.append(topic)
        
        return missing_topics
