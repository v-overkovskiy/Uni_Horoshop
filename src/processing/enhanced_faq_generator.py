"""
Улучшенный генератор FAQ с схемой "10 → 6" и валидацией единиц
"""
import re
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FAQCandidate:
    """Кандидат FAQ с метаданными"""
    question: str
    answer: str
    topic: str
    unit_type: str  # 'volume', 'weight', 'other'
    score: float = 0.0
    is_valid: bool = True
    issues: List[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []

class EnhancedFAQGenerator:
    """Улучшенный генератор FAQ с детерминированным отбором лучших 6"""
    
    def __init__(self):
        # Паттерны для определения типа единиц
        self.volume_patterns = {
            'ru': [r'\d+\s*мл', r'\d+\s*л', r'миллилитр', r'литр'],
            'ua': [r'\d+\s*мл', r'\d+\s*л', r'мілілітр', r'літр']
        }
        
        self.weight_patterns = {
            'ru': [r'\d+\s*г(?:рамм)?', r'\d+\s*кг', r'грамм', r'килограмм'],
            'ua': [r'\d+\s*г(?:рам)?', r'\d+\s*кг', r'грам', r'кілограм']
        }
        
        # Темы для покрытия
        self.topics = {
            'ru': [
                'состав/материал', 'как использовать', 'область применения', 
                'свойства/эффект', 'объём или горение/срок', 'аромат/запах', 
                'безопасность/гипоалергенно', 'хранение', 'противопоказания', 'качество',
                'упаковка', 'срок годности', 'применение', 'результат'
            ],
            'ua': [
                'склад/матеріал', 'як використовувати', 'область застосування',
                'властивості/ефект', 'об\'єм або горіння/термін', 'аромат/запах',
                'безпека/гіпоалергенно', 'зберігання', 'протипоказання', 'якість',
                'упаковка', 'термін придатності', 'застосування', 'результат'
            ]
        }
        
        # Шаблоны вопросов для нормализации единиц
        self.unit_question_templates = {
            'ru': {
                'volume': [
                    "Какой объём продукта?",
                    "Сколько миллилитров в упаковке?",
                    "Какой объём упаковки?",
                    "Какой объём содержимого?"
                ],
                'weight': [
                    "Какой вес продукта?",
                    "Сколько весит упаковка?",
                    "Какой вес упаковки?",
                    "Какой вес содержимого?"
                ]
            },
            'ua': {
                'volume': [
                    "Який об'єм продукту?",
                    "Скільки мілілітрів в упаковці?",
                    "Який об'єм упаковки?",
                    "Який об'єм вмісту?"
                ],
                'weight': [
                    "Яка вага продукту?",
                    "Скільки важить упаковка?",
                    "Яка вага упаковки?",
                    "Яка вага вмісту?"
                ]
            }
        }
        
        # Запрещённые ответы (плейсхолдеры)
        self.forbidden_answers = {
            'ru': ['да', 'нет', 'не указано', 'не вказано', 'примерно', 'приблизительно', 
                   'обычно', 'зазвичай', 'несколько', 'кілька', 'около', 'близько'],
            'ua': ['так', 'ні', 'не вказано', 'не вказано', 'приблизно', 'приблизно',
                   'зазвичай', 'зазвичай', 'кілька', 'кілька', 'близько', 'близько']
        }

    def generate_enhanced_faq(self, facts: Dict[str, Any], specs: List[Dict[str, str]], 
                            locale: str, title: str) -> List[Dict[str, str]]:
        """
        Генерирует улучшенный FAQ по схеме "10 → 6"
        """
        logger.info(f"🔧 Генерация улучшенного FAQ для {locale}")
        
        # 1. Генерируем 10 кандидатов
        candidates = self._generate_10_candidates(facts, specs, locale, title)
        
        # 2. Валидируем и нормализуем кандидатов
        validated_candidates = self._validate_and_normalize_candidates(candidates, locale)
        
        # 3. Отбираем лучшие 6
        selected_faq = self._select_best_6(validated_candidates, locale)
        
        # 4. Конвертируем в формат для экспорта (HTMLBuilder ожидает 'question' и 'answer')
        result = []
        for candidate in selected_faq:
            result.append({
                'question': candidate.question,
                'answer': candidate.answer
            })
        
        logger.info(f"✅ Сгенерировано {len(result)} FAQ для {locale}")
        return result

    def _generate_10_candidates(self, facts: Dict[str, Any], specs: List[Dict[str, str]], 
                               locale: str, title: str) -> List[FAQCandidate]:
        """Генерирует 10 кандидатных FAQ на основе фактов"""
        candidates = []
        
        # Извлекаем информацию из specs
        spec_info = self._extract_spec_info(specs, locale)
        
        # Генерируем кандидатов на основе тем
        topics = self.topics[locale]
        
        # Генерируем кандидатов для всех доступных тем, но ограничиваем до 10
        for topic in topics:
            if len(candidates) >= 10:
                break
            question, answer = self._generate_qa_for_topic(topic, facts, spec_info, locale, title)
            
            if question and answer:
                # Определяем тип единиц в ответе
                unit_type = self._detect_unit_type(answer, locale)
                
                candidate = FAQCandidate(
                    question=question,
                    answer=answer,
                    topic=topic,
                    unit_type=unit_type
                )
                candidates.append(candidate)
        
        # Если кандидатов меньше 10, генерируем дополнительные
        additional_topics = [
            'качество', 'якість', 'безопасность', 'безпека', 'хранение', 'зберігання',
            'результат', 'результат', 'упаковка', 'упаковка', 'срок годности', 'термін придатності'
        ]
        
        for topic in additional_topics:
            if len(candidates) >= 10:
                break
            question, answer = self._generate_qa_for_topic(topic, facts, spec_info, locale, title)
            if question and answer:
                unit_type = self._detect_unit_type(answer, locale)
                candidate = FAQCandidate(
                    question=question,
                    answer=answer,
                    topic=topic,
                    unit_type=unit_type
                )
                candidates.append(candidate)
        
        # Жестко ограничиваем до 10 кандидатов
        candidates = candidates[:10]
        
        return candidates

    def _extract_spec_info(self, specs: List[Dict[str, str]], locale: str) -> Dict[str, Any]:
        """Извлекает информацию из характеристик"""
        info = {
            'volume': None,
            'weight': None,
            'material': None,
            'brand': None,
            'color': None,
            'purpose': None
        }
        
        for spec in specs:
            name = spec.get('name', '').lower()
            value = spec.get('value', '')
            
            if any(word in name for word in ['объём', 'об\'єм', 'объем', 'volume']):
                info['volume'] = value
            elif any(word in name for word in ['вес', 'вага', 'weight']):
                info['weight'] = value
            elif any(word in name for word in ['материал', 'матеріал', 'material']):
                info['material'] = value
            elif any(word in name for word in ['бренд', 'производитель', 'виробник']):
                info['brand'] = value
            elif any(word in name for word in ['цвет', 'колір', 'color']):
                info['color'] = value
            elif any(word in name for word in ['назначение', 'призначення', 'purpose']):
                info['purpose'] = value
        
        return info

    def _generate_qa_for_topic(self, topic: str, facts: Dict[str, Any], 
                              spec_info: Dict[str, Any], locale: str, title: str) -> Tuple[str, str]:
        """Генерирует вопрос-ответ для конкретной темы"""
        
        if topic in ['состав/материал', 'склад/матеріал']:
            if spec_info['material']:
                if locale == 'ru':
                    return "Из какого материала изготовлен продукт?", spec_info['material']
                else:
                    return "З якого матеріалу виготовлений продукт?", spec_info['material']
            else:
                if locale == 'ru':
                    return "Из какого материала изготовлен продукт?", "Продукт изготовлен из качественных материалов"
                else:
                    return "З якого матеріалу виготовлений продукт?", "Продукт виготовлений з якісних матеріалів"
        
        elif topic in ['как использовать', 'як використовувати']:
            if locale == 'ru':
                return "Как правильно использовать продукт?", "Следуйте инструкциям на упаковке"
            else:
                return "Як правильно використовувати продукт?", "Дотримуйтесь інструкцій на упаковці"
        
        elif topic in ['область применения', 'область застосування']:
            if spec_info['purpose']:
                if locale == 'ru':
                    return "Для чего предназначен продукт?", spec_info['purpose']
                else:
                    return "Для чого призначений продукт?", spec_info['purpose']
            else:
                if locale == 'ru':
                    return "Для чего предназначен продукт?", "Продукт предназначен для профессионального использования"
                else:
                    return "Для чого призначений продукт?", "Продукт призначений для професійного використання"
        
        elif topic in ['свойства/эффект', 'властивості/ефект']:
            if locale == 'ru':
                return "Какие свойства имеет продукт?", "Продукт обладает высокими качественными характеристиками"
            else:
                return "Які властивості має продукт?", "Продукт має високі якісні характеристики"
        
        elif topic in ['объём или горение/срок', 'об\'єм або горіння/термін']:
            if spec_info['volume']:
                if locale == 'ru':
                    return "Какой объём продукта?", spec_info['volume']
                else:
                    return "Який об'єм продукту?", spec_info['volume']
            elif spec_info['weight']:
                if locale == 'ru':
                    return "Какой вес продукта?", spec_info['weight']
                else:
                    return "Яка вага продукту?", spec_info['weight']
            else:
                if locale == 'ru':
                    return "Какой объём продукта?", "Объём указан на упаковке"
                else:
                    return "Який об'єм продукту?", "Об'єм вказано на упаковці"
        
        elif topic in ['аромат/запах', 'аромат/запах']:
            if spec_info['color']:
                if locale == 'ru':
                    return "Какой аромат у продукта?", f"Продукт имеет приятный аромат {spec_info['color']}"
                else:
                    return "Який аромат у продукту?", f"Продукт має приємний аромат {spec_info['color']}"
            else:
                if locale == 'ru':
                    return "Какой аромат у продукта?", "Продукт имеет приятный аромат"
                else:
                    return "Який аромат у продукту?", "Продукт має приємний аромат"
        
        elif topic in ['безопасность/гипоаллергенно', 'безпека/гіпоалергенно']:
            if locale == 'ru':
                return "Безопасен ли продукт для кожи?", "Продукт безопасен для всех типов кожи"
            else:
                return "Чи безпечний продукт для шкіри?", "Продукт безпечний для всіх типів шкіри"
        
        elif topic in ['хранение', 'зберігання']:
            if locale == 'ru':
                return "Как хранить продукт?", "Храните в сухом прохладном месте"
            else:
                return "Як зберігати продукт?", "Зберігайте в сухому прохолодному місці"
        
        elif topic in ['противопоказания', 'протипоказання']:
            if locale == 'ru':
                return "Есть ли противопоказания?", "Перед использованием проконсультируйтесь со специалистом"
            else:
                return "Чи є протипоказання?", "Перед використанням проконсультуйтеся зі спеціалістом"
        
        elif topic in ['качество', 'якість']:
            if spec_info['brand']:
                if locale == 'ru':
                    return "Какой бренд продукта?", spec_info['brand']
                else:
                    return "Який бренд продукту?", spec_info['brand']
            else:
                if locale == 'ru':
                    return "Какой бренд продукта?", "Продукт от проверенного производителя"
                else:
                    return "Який бренд продукту?", "Продукт від перевіреного виробника"
        
        # Дополнительные темы для генерации большего количества FAQ
        elif topic in ['упаковка', 'упаковка']:
            if locale == 'ru':
                return "Какая упаковка у продукта?", "Продукт поставляется в удобной упаковке"
            else:
                return "Яка упаковка у продукту?", "Продукт поставляється в зручній упаковці"
        
        elif topic in ['срок годности', 'термін придатності']:
            if locale == 'ru':
                return "Какой срок годности?", "Срок годности указан на упаковке"
            else:
                return "Який термін придатності?", "Термін придатності вказано на упаковці"
        
        elif topic in ['применение', 'застосування']:
            if locale == 'ru':
                return "Как применять продукт?", "Применяйте согласно инструкции"
            else:
                return "Як застосовувати продукт?", "Застосовуйте згідно з інструкцією"
        
        elif topic in ['результат', 'результат']:
            if locale == 'ru':
                return "Какой результат от использования?", "Продукт обеспечивает отличный результат"
            else:
                return "Який результат від використання?", "Продукт забезпечує відмінний результат"
        
        return None, None

    def _detect_unit_type(self, text: str, locale: str) -> str:
        """Определяет тип единиц в тексте"""
        text_lower = text.lower()
        
        # Проверяем объём
        for pattern in self.volume_patterns[locale]:
            if re.search(pattern, text_lower):
                return 'volume'
        
        # Проверяем вес
        for pattern in self.weight_patterns[locale]:
            if re.search(pattern, text_lower):
                return 'weight'
        
        return 'other'

    def _validate_and_normalize_candidates(self, candidates: List[FAQCandidate], locale: str) -> List[FAQCandidate]:
        """Валидирует и нормализует кандидатов с улучшенными правилами"""
        validated = []
        
        for candidate in candidates:
            # Проверяем длину вопроса и ответа
            if len(candidate.question.strip()) < 6:
                candidate.is_valid = False
                candidate.issues.append('question_too_short')
            
            if len(candidate.answer.strip()) < 40:  # Возвращаем порог 40 символов
                candidate.is_valid = False
                candidate.issues.append('answer_too_short')
            
            # Проверяем на плейсхолдеры
            answer_lower = candidate.answer.lower().strip()
            if answer_lower in self.forbidden_answers[locale]:
                candidate.is_valid = False
                candidate.issues.append('placeholder_answer')
            
            # Проверяем на дефолтные вопросы про вес
            if self._is_weight_stub_question(candidate.question, locale):
                candidate.is_valid = False
                candidate.issues.append('weight_stub_question')
            
            # Нормализуем вопрос (заглавная буква, знак вопроса)
            candidate.question = self._normalize_question(candidate.question, locale)
            
            # Проверяем соответствие единиц
            if not self._validate_unit_consistency(candidate, locale):
                # Пытаемся исправить вопрос
                fixed_question = self._fix_unit_consistency(candidate, locale)
                if fixed_question:
                    candidate.question = fixed_question
                    candidate.issues.append('unit_consistency_fixed')
                else:
                    candidate.is_valid = False
                    candidate.issues.append('unit_consistency_error')
            
            if candidate.is_valid:
                validated.append(candidate)
        
        return validated

    def _normalize_question(self, question: str, locale: str) -> str:
        """Нормализует вопрос: заглавная буква, знак вопроса"""
        question = question.strip()
        
        if not question:
            return question
        
        # Убираем существующий знак вопроса
        if question.endswith('?'):
            question = question[:-1]
        
        # Делаем первую букву заглавной
        question = question[0].upper() + question[1:] if len(question) > 1 else question.upper()
        
        # Добавляем знак вопроса
        question += '?'
        
        return question

    def _is_weight_stub_question(self, question: str, locale: str) -> bool:
        """Проверяет, является ли вопрос дефолтной заглушкой про вес"""
        question_lower = question.lower().strip()
        
        # Проверяем типичные заглушки про вес
        weight_stubs = [
            'какой вес упаковки',
            'какой вес продукта',
            'какой вес',
            'яка вага упаковки',
            'яка вага продукту',
            'яка вага'
        ]
        
        for stub in weight_stubs:
            if stub in question_lower:
                return True
        
        return False

    def _validate_unit_consistency(self, candidate: FAQCandidate, locale: str) -> bool:
        """Проверяет соответствие единиц в вопросе и ответе"""
        if candidate.unit_type == 'other':
            return True
        
        question_lower = candidate.question.lower()
        
        # Проверяем, соответствует ли вопрос типу единиц в ответе
        if candidate.unit_type == 'volume':
            volume_words = ['объём', 'об\'єм', 'миллилитр', 'мілілітр', 'литр', 'літр']
            return any(word in question_lower for word in volume_words)
        elif candidate.unit_type == 'weight':
            weight_words = ['вес', 'вага', 'грамм', 'грам', 'килограмм', 'кілограм']
            return any(word in question_lower for word in weight_words)
        
        return True

    def _fix_unit_consistency(self, candidate: FAQCandidate, locale: str) -> str:
        """Исправляет несоответствие единиц в вопросе"""
        if candidate.unit_type == 'other':
            return candidate.question
        
        question_lower = candidate.question.lower()
        
        # Если вопрос про вес, а ответ про объём
        if candidate.unit_type == 'volume' and 'вес' in question_lower:
            if locale == 'ru':
                return question_lower.replace('вес', 'объём').capitalize() + '?'
            else:
                return question_lower.replace('вага', 'об\'єм').capitalize() + '?'
        
        # Если вопрос про объём, а ответ про вес
        elif candidate.unit_type == 'weight' and ('объём' in question_lower or 'об\'єм' in question_lower):
            if locale == 'ru':
                return question_lower.replace('объём', 'вес').capitalize() + '?'
            else:
                return question_lower.replace('об\'єм', 'вага').capitalize() + '?'
        
        # Используем шаблоны как fallback
        templates = self.unit_question_templates[locale][candidate.unit_type]
        for template in templates:
            if template not in candidate.question:
                return template
        
        return candidate.question

    def _select_best_6(self, candidates: List[FAQCandidate], locale: str) -> List[FAQCandidate]:
        """Отбирает лучшие 6 FAQ с покрытием тем"""
        if len(candidates) <= 6:
            return candidates
        
        # Группируем по темам
        topic_groups = {}
        for candidate in candidates:
            topic = candidate.topic
            if topic not in topic_groups:
                topic_groups[topic] = []
            topic_groups[topic].append(candidate)
        
        # Выбираем по одному из каждой темы (минимум 4 разные темы)
        selected = []
        used_topics = set()
        
        # Сначала выбираем по одному из каждой темы
        for topic, group in topic_groups.items():
            if len(selected) < 6 and group:
                # Берем первый элемент из группы (они уже отсортированы по приоритету)
                best_candidate = group[0]
                selected.append(best_candidate)
                used_topics.add(topic)
        
        # Если нужно больше, добираем из оставшихся
        remaining_candidates = [c for c in candidates if c not in selected]
        
        while len(selected) < 6 and remaining_candidates:
            selected.append(remaining_candidates.pop(0))
        
        return selected[:6]

    def get_diagnostic_info(self, candidates: List[FAQCandidate], selected: List[FAQCandidate]) -> Dict[str, Any]:
        """Возвращает диагностическую информацию"""
        # Подсчитываем статистику
        lowercase_count = sum(1 for c in candidates if c.question and c.question[0].islower())
        unit_mismatch_count = sum(1 for c in candidates if 'unit_consistency_error' in c.issues)
        weight_stub_count = sum(1 for c in candidates if 'weight_stub_question' in c.issues)
        
        # Собираем действия по исправлению
        repair_actions = []
        for c in selected:
            if c.issues:
                repair_actions.extend(c.issues)
        
        # Проверяем, был ли исправлен первый слот
        first_slot_repaired = False
        if selected and len(selected) > 0:
            first_candidate = selected[0]
            if any(action in ['unit_consistency_fixed', 'q_capitalized'] for action in first_candidate.issues):
                first_slot_repaired = True
        
        return {
            'faq_q_lowercase_count': lowercase_count,
            'faq_unit_mismatch_count': unit_mismatch_count,
            'faq_weight_stub_count': weight_stub_count,
            'faq_first_slot_repaired': first_slot_repaired,
            'faq_repaired': any('unit_consistency_fixed' in c.issues for c in selected),
            'faq_repair_actions': repair_actions,
            'faq_candidates_total': len(candidates),
            'faq_selected_count': len(selected),
            'topics_covered': len(set(c.topic for c in selected))
        }
