"""
Финальные Quality Guards - последний барьер перед записью в HTML
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
from .topic_classifier import TopicClassifier
from .anti_generic_filter import AntiGenericFilter
from .answer_templates import AnswerTemplates

logger = logging.getLogger(__name__)

class FinalQualityGuards:
    """Финальные Quality Guards для проверки качества FAQ"""
    
    def __init__(self):
        self.topic_classifier = TopicClassifier()
        self.anti_generic_filter = AntiGenericFilter()
        self.answer_templates = AnswerTemplates()
        
        # Строгие требования к качеству
        self.quality_requirements = {
            'min_faq_count': 6,
            'max_faq_count': 6,
            'min_quality_score': 0.7,
            'max_duplicate_topics': 0,
            'max_generic_answers': 0,
            'min_answer_length': 30,
            'max_answer_length': 500
        }

    def validate_faq_quality(self, faq_items: List[Dict[str, str]], locale: str, 
                           specs: List[Dict[str, str]] = None) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Финальная валидация качества FAQ
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            specs: Характеристики товара для улучшения ответов
            
        Returns:
            (is_valid, issues, quality_metrics)
        """
        issues = []
        quality_metrics = {}
        
        # 1. Проверка количества FAQ
        faq_count = len(faq_items)
        if faq_count < self.quality_requirements['min_faq_count']:
            issues.append(f"Недостаточно FAQ: {faq_count} < {self.quality_requirements['min_faq_count']}")
        elif faq_count > self.quality_requirements['max_faq_count']:
            issues.append(f"Слишком много FAQ: {faq_count} > {self.quality_requirements['max_faq_count']}")
        
        quality_metrics['faq_count'] = faq_count
        
        # 2. Дедупликация по темам
        deduplicated_faq = self.topic_classifier.deduplicate_by_topic(faq_items, locale)
        duplicate_count = faq_count - len(deduplicated_faq)
        
        if duplicate_count > self.quality_requirements['max_duplicate_topics']:
            issues.append(f"Обнаружены дубликаты тем: {duplicate_count}")
        
        quality_metrics['duplicate_count'] = duplicate_count
        quality_metrics['deduplicated_count'] = len(deduplicated_faq)
        
        # 3. Фильтрация generic ответов
        filtered_faq = self.anti_generic_filter.filter_generic_faq(deduplicated_faq, locale)
        generic_count = len(deduplicated_faq) - len(filtered_faq)
        
        if generic_count > self.quality_requirements['max_generic_answers']:
            issues.append(f"Обнаружены generic ответы: {generic_count}")
        
        quality_metrics['generic_count'] = generic_count
        quality_metrics['filtered_count'] = len(filtered_faq)
        
        # 4. Улучшение качества ответов
        if specs and len(filtered_faq) < self.quality_requirements['min_faq_count']:
            improved_faq = self._improve_faq_answers(filtered_faq, specs, locale)
            quality_metrics['improved_count'] = len(improved_faq)
            filtered_faq = improved_faq
        
        # 5. Проверка длины ответов
        length_issues = self._validate_answer_lengths(filtered_faq)
        issues.extend(length_issues)
        
        # 6. Вычисление итоговой оценки качества
        quality_score = self.anti_generic_filter.get_quality_score(filtered_faq, locale)
        quality_metrics['quality_score'] = quality_score
        
        if quality_score < self.quality_requirements['min_quality_score']:
            issues.append(f"Низкая оценка качества: {quality_score:.2f} < {self.quality_requirements['min_quality_score']}")
        
        # 7. Финальная проверка
        is_valid = len(issues) == 0 and len(filtered_faq) >= self.quality_requirements['min_faq_count']
        
        if is_valid:
            logger.info(f"✅ FAQ прошел финальную валидацию качества: {len(filtered_faq)} FAQ, оценка: {quality_score:.2f}")
        else:
            logger.error(f"❌ FAQ не прошел финальную валидацию: {issues}")
        
        return is_valid, issues, quality_metrics

    def _improve_faq_answers(self, faq_items: List[Dict[str, str]], specs: List[Dict[str, str]], 
                           locale: str) -> List[Dict[str, str]]:
        """
        Улучшает качество ответов в FAQ
        
        Args:
            faq_items: Список FAQ
            specs: Характеристики товара
            locale: Локаль
            
        Returns:
            Улучшенный список FAQ
        """
        improved_items = []
        
        for item in faq_items:
            question = item.get('question', '') or item.get('q', '')
            answer = item.get('answer', '') or item.get('a', '')
            
            # Пытаемся улучшить ответ с помощью шаблонов
            improved_answer = self.answer_templates.generate_quality_answer(question, specs, locale)
            
            if improved_answer and len(improved_answer) > len(answer):
                improved_item = item.copy()
                improved_item['answer'] = improved_answer
                improved_items.append(improved_item)
                logger.info(f"✅ Улучшен ответ: '{question[:30]}...'")
            else:
                improved_items.append(item)
        
        return improved_items

    def _validate_answer_lengths(self, faq_items: List[Dict[str, str]]) -> List[str]:
        """
        Проверяет длину ответов
        
        Args:
            faq_items: Список FAQ
            
        Returns:
            Список проблем с длиной
        """
        issues = []
        
        for i, item in enumerate(faq_items):
            answer = item.get('answer', '') or item.get('a', '')
            answer_length = len(answer.strip())
            
            if answer_length < self.quality_requirements['min_answer_length']:
                issues.append(f'FAQ {i+1}: ответ слишком короткий ({answer_length} символов)')
            elif answer_length > self.quality_requirements['max_answer_length']:
                issues.append(f'FAQ {i+1}: ответ слишком длинный ({answer_length} символов)')
        
        return issues

    def get_missing_topics(self, faq_items: List[Dict[str, str]], locale: str) -> List[str]:
        """
        Определяет недостающие темы в FAQ
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            
        Returns:
            Список недостающих тем
        """
        return self.topic_classifier.get_missing_topics(faq_items, locale)

    def generate_missing_faq(self, missing_topics: List[str], specs: List[Dict[str, str]], 
                          locale: str, count: int) -> List[Dict[str, str]]:
        """
        Генерирует недостающие FAQ для указанных тем
        
        Args:
            missing_topics: Список недостающих тем
            specs: Характеристики товара
            locale: Локаль
            count: Количество FAQ для генерации
            
        Returns:
            Список сгенерированных FAQ
        """
        generated_faq = []
        
        for topic in missing_topics[:count]:
            # Создаем вопрос для темы
            question = self._create_question_for_topic(topic, locale)
            
            # Генерируем качественный ответ
            answer = self.answer_templates.generate_quality_answer(question, specs, locale)
            
            if answer:
                generated_faq.append({
                    'question': question,
                    'answer': answer
                })
                logger.info(f"✅ Сгенерирован FAQ для темы '{topic}': '{question[:30]}...'")
        
        return generated_faq

    def _create_question_for_topic(self, topic: str, locale: str) -> str:
        """Создает вопрос для указанной темы"""
        question_templates = {
            'volume_weight': {
                'ru': 'Какой объём продукта?',
                'ua': 'Який об\'єм продукту?'
            },
            'storage': {
                'ru': 'Как хранить продукт?',
                'ua': 'Як зберігати продукт?'
            },
            'skin_type': {
                'ru': 'Подходит ли для чувствительной кожи?',
                'ua': 'Чи підходить для чутливої шкіри?'
            },
            'usage': {
                'ru': 'Как использовать продукт?',
                'ua': 'Як використовувати продукт?'
            },
            'safety': {
                'ru': 'Безопасен ли продукт?',
                'ua': 'Чи безпечний продукт?'
            },
            'composition': {
                'ru': 'Из чего состоит продукт?',
                'ua': 'З чого складається продукт?'
            },
            'effect': {
                'ru': 'Какой эффект от продукта?',
                'ua': 'Який ефект від продукту?'
            },
            'contraindications': {
                'ru': 'Есть ли противопоказания?',
                'ua': 'Чи є протипоказання?'
            }
        }
        
        if topic in question_templates:
            return question_templates[topic][locale]
        
        # Fallback вопрос
        if locale == 'ru':
            return f'Что нужно знать о {topic}?'
        else:
            return f'Що потрібно знати про {topic}?'

    def enforce_quality_standards(self, faq_items: List[Dict[str, str]], locale: str, 
                                specs: List[Dict[str, str]] = None) -> Tuple[List[Dict[str, str]], bool]:
        """
        Принудительно применяет стандарты качества к FAQ
        
        Args:
            faq_items: Список FAQ
            locale: Локаль
            specs: Характеристики товара
            
        Returns:
            (improved_faq, success)
        """
        logger.info(f"🔧 Применение стандартов качества к {len(faq_items)} FAQ для {locale}")
        
        # 1. Дедупликация по темам
        deduplicated_faq = self.topic_classifier.deduplicate_by_topic(faq_items, locale)
        logger.info(f"🔧 После дедупликации: {len(deduplicated_faq)} FAQ")
        
        # 2. Фильтрация generic ответов
        filtered_faq = self.anti_generic_filter.filter_generic_faq(deduplicated_faq, locale)
        logger.info(f"🔧 После фильтрации generic: {len(filtered_faq)} FAQ")
        
        # 3. Улучшение качества ответов
        if specs:
            improved_faq = self._improve_faq_answers(filtered_faq, specs, locale)
            logger.info(f"🔧 После улучшения ответов: {len(improved_faq)} FAQ")
        else:
            improved_faq = filtered_faq
        
        # 4. Дозаполнение недостающих FAQ
        if len(improved_faq) < self.quality_requirements['min_faq_count']:
            missing_topics = self.get_missing_topics(improved_faq, locale)
            needed_count = self.quality_requirements['min_faq_count'] - len(improved_faq)
            
            if missing_topics and specs:
                generated_faq = self.generate_missing_faq(missing_topics, specs, locale, needed_count)
                improved_faq.extend(generated_faq)
                logger.info(f"🔧 Дозаполнено {len(generated_faq)} FAQ")
        
        # 5. Финальная валидация
        is_valid, issues, metrics = self.validate_faq_quality(improved_faq, locale, specs)
        
        if is_valid:
            logger.info(f"✅ Стандарты качества применены успешно: {len(improved_faq)} FAQ")
            return improved_faq, True
        else:
            logger.error(f"❌ Не удалось применить стандарты качества: {issues}")
            return improved_faq, False
