"""
Адаптер для нормализации формата FAQ между компонентами
"""
import logging
from typing import List, Dict, Any, Union

logger = logging.getLogger(__name__)


def coerce_faq_list(obj: Any) -> List[Dict[str, str]]:
    """
    Нормализует FAQ в единый формат list[{'question','answer'}]
    
    Args:
        obj: Любой формат FAQ от ContentEnhancer
        
    Returns:
        Список FAQ в нормализованном формате
    """
    if obj is None:
        return []
    
    # Если это одиночный dict с question
    if isinstance(obj, dict) and "question" in obj:
        return [{"question": obj["question"], "answer": obj.get("answer", "")}]
    
    # Если это dict с ключом 'faqs'
    if isinstance(obj, dict) and "faqs" in obj:
        obj = obj["faqs"]
    
    # Если это не список, возвращаем пустой
    if not isinstance(obj, list):
        logger.warning(f"⚠️ Неожиданный формат FAQ: {type(obj)}")
        return []
    
    out = []
    for item in obj:
        if not isinstance(item, dict):
            continue
            
        # Конвертируем 'q'/'a' в 'question'/'answer'
        if "q" in item or "a" in item:
            out.append({
                "question": item.get("q", ""),
                "answer": item.get("a", "")
            })
        else:
            out.append({
                "question": item.get("question", ""),
                "answer": item.get("answer", "")
            })
    
    logger.info(f"✅ FAQ нормализован: {len(out)} элементов")
    return out


def is_placeholder_faq(question: str, answer: str) -> bool:
    """
    Проверяет, является ли FAQ заглушкой
    """
    placeholder_patterns = [
        'запасной вопрос', 'запасной ответ', 'placeholder', 'stub',
        'дополнительный вопрос', 'дополнительный ответ', 'заглушка'
    ]
    
    question_lower = question.lower()
    answer_lower = answer.lower()
    
    for pattern in placeholder_patterns:
        if pattern in question_lower or pattern in answer_lower:
            return True
    
    return False


def filter_placeholders(faq_list: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Фильтрует заглушки из списка FAQ
    """
    filtered = []
    blocked_count = 0
    
    for item in faq_list:
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        
        if is_placeholder_faq(question, answer):
            blocked_count += 1
            logger.warning(f"🚫 Заглушка заблокирована: '{question}'")
            continue
        
        filtered.append(item)
    
    if blocked_count > 0:
        logger.warning(f"🚫 Заблокировано заглушек: {blocked_count}")
    
    return filtered


def validate_faq_format(faq_list: List[Dict[str, str]]) -> bool:
    """
    Валидирует формат FAQ
    """
    if not isinstance(faq_list, list):
        return False
    
    for item in faq_list:
        if not isinstance(item, dict):
            return False
        if "question" not in item or "answer" not in item:
            return False
        if not isinstance(item["question"], str) or not isinstance(item["answer"], str):
            return False
    
    return True


def log_faq_diagnostics(faq_list: List[Dict[str, str]], stage: str) -> None:
    """
    Логирует диагностическую информацию о FAQ
    """
    logger.info(f"🔧 FAQ {stage}: len={len(faq_list)}, valid_format={validate_faq_format(faq_list)}")
    
    if faq_list:
        questions = [item.get("question", "") for item in faq_list]
        logger.info(f"🔧 FAQ вопросы: {questions[:3]}{'...' if len(questions) > 3 else ''}")

