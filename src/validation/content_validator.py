"""
Валидатор качества LLM-контента
Проверяет контент на шаблоны, полноту и запрещённые данные
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class ContentValidator:
    """Валидация качества контента перед принятием"""
    
    # Запрещённые шаблонные фразы
    TEMPLATE_PHRASES = {
        'ru': [
            'качественный продукт',
            'профессиональный продукт',
            'эффективный продукт',
            'отличный выбор',
            'идеальный вариант',
            'превосходное качество',
            'идеальное средство',
            'качественный товар',
            'профессиональный уход',
            'эффективный результат'
        ],
        'ua': [
            'якісний продукт',
            'професійний продукт',
            'ефективний продукт',
            'чудовий вибір',
            'ідеальний варіант',
            'чудова якість',
            'ідеальний засіб',
            'якісний товар',
            'професійний догляд',
            'ефективний результат'
        ]
    }
    
    # Запрещённые слова/фразы
    FORBIDDEN_CONTENT = [
        'не указано', 'не вказано',
        'не известно', 'не відомо',
        'uah', 'грн', 'цена', 'ціна',
        'стоимость', 'вартість'
    ]
    
    # Запрещённые лейблы характеристик
    FORBIDDEN_SPEC_LABELS = [
        'цена', 'price', 'ціна',
        'стоимость', 'вартість', 'cost'
    ]

    @staticmethod
    def validate_description(description: str, locale: str) -> Tuple[bool, str]:
        """
        Валидация описания товара
        
        Returns:
            (is_valid, error_message)
        """
        
        if not description or len(description.strip()) < 50:
            return False, f"❌ Описание слишком короткое: {len(description)} символов"
        
        desc_lower = description.lower()
        
        # 1. Проверка на шаблонные фразы
        templates = ContentValidator.TEMPLATE_PHRASES.get(locale, [])
        for phrase in templates:
            if phrase in desc_lower:
                return False, f"❌ ШАБЛОН: '{phrase}'"
        
        # 2. Проверка на запрещённый контент
        for forbidden in ContentValidator.FORBIDDEN_CONTENT:
            if forbidden in desc_lower:
                return False, f"❌ ЗАПРЕЩЕНО: '{forbidden}'"
        
        # 3. Проверка HTML структуры (должны быть теги <p>)
        import re
        paragraphs = re.findall(r'<p>(.*?)</p>', description)
        if len(paragraphs) != 2:
            return False, f"❌ Параграфов {len(paragraphs)}, нужно ровно 2"
        
        # 4. Проверка количества предложений (6-10)
        total_sentences = 0
        for p in paragraphs:
            clean = re.sub(r'<.*?>', '', p)
            sentences = [s.strip() for s in re.split(r'[.!?]+', clean) if s.strip()]
            total_sentences += len(sentences)
        
        if total_sentences < 6 or total_sentences > 10:
            return False, f"❌ Предложений {total_sentences}, нужно 6-10"
        
        # 5. Проверка минимальной длины
        clean_text = re.sub(r'<.*?>', '', description)
        words = clean_text.split()
        if len(words) < 50:  # Увеличили минимум
            return False, f"❌ Мало слов: {len(words)}/50"
        
        return True, ""

    @staticmethod
    def validate_faq(faq_items: List[Dict], locale: str) -> Tuple[bool, str]:
        """
        Валидация FAQ
        
        Returns:
            (is_valid, error_message)
        """
        
        if not faq_items or len(faq_items) < 6:
            return False, f"❌ FAQ мало вопросов: {len(faq_items)}/6"
        
        for i, item in enumerate(faq_items, 1):
            question = item.get('question', '').strip()
            answer = item.get('answer', '').strip()
            
            if not question or len(question) < 10:
                return False, f"❌ FAQ #{i}: вопрос пустой/короткий"
            
            if not answer or len(answer) < 20:
                return False, f"❌ FAQ #{i}: ответ пустой/короткий"
            
            # Проверка на запрещённый контент
            combined = (question + ' ' + answer).lower()
            for forbidden in ContentValidator.FORBIDDEN_CONTENT:
                if forbidden in combined:
                    return False, f"❌ FAQ #{i}: запрещено '{forbidden}'"
        
        return True, ""

    @staticmethod
    def validate_benefits(benefits: List[str], locale: str) -> Tuple[bool, str]:
        """
        Валидация преимуществ
        
        Returns:
            (is_valid, error_message)
        """
        
        if not benefits or len(benefits) < 3:
            return False, f"❌ Мало преимуществ: {len(benefits)}/3"
        
        for i, benefit in enumerate(benefits, 1):
            if not benefit or len(benefit.strip()) < 10:
                return False, f"❌ Преимущество #{i} пустое/короткое"
            
            benefit_lower = benefit.lower()
            
            # Проверка на шаблоны
            templates = ContentValidator.TEMPLATE_PHRASES.get(locale, [])
            for phrase in templates:
                if phrase in benefit_lower:
                    return False, f"❌ Преимущество #{i}: шаблон '{phrase}'"
        
        return True, ""

    @staticmethod
    def filter_specifications(specs: List[Dict]) -> List[Dict]:
        """
        Фильтрация характеристик (убирает запрещённые)
        
        Returns:
            Отфильтрованный список характеристик
        """
        
        filtered = []
        
        for spec in specs:
            label = str(spec.get('label', '')).lower()
            value = str(spec.get('value', '')).lower()
            
            # Пропускаем запрещённые лейблы
            if any(forbidden in label for forbidden in ContentValidator.FORBIDDEN_SPEC_LABELS):
                logger.warning(f"⚠️ Отфильтрована характеристика: {label}")
                continue
            
            # Пропускаем запрещённые значения
            if any(forbidden in value for forbidden in ContentValidator.FORBIDDEN_CONTENT):
                logger.warning(f"⚠️ Отфильтровано значение: {value}")
                continue
            
            filtered.append(spec)
        
        return filtered

    @staticmethod
    def validate_all_content(content: Dict, locale: str) -> Tuple[bool, List[str]]:
        """
        Полная валидация всего контента
        
        Returns:
            (is_valid, list_of_errors)
        """
        
        errors = []
        
        # 1. Валидация описания
        if 'description' in content:
            valid, error = ContentValidator.validate_description(
                content['description'], locale
            )
            if not valid:
                errors.append(f"Описание: {error}")
        
        # 2. Валидация FAQ
        if 'faq' in content:
            valid, error = ContentValidator.validate_faq(
                content['faq'], locale
            )
            if not valid:
                errors.append(f"FAQ: {error}")
        
        # 3. Валидация преимуществ
        if 'benefits' in content:
            valid, error = ContentValidator.validate_benefits(
                content['benefits'], locale
            )
            if not valid:
                errors.append(f"Преимущества: {error}")
        
        is_valid = len(errors) == 0
        
        return is_valid, errors