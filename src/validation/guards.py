"""
Валидационные guards для проверки качества контента
"""
import logging
from typing import List, Dict, Any, Tuple
from .locale_validator import LocaleValidator

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass

# Глобальный экземпляр валидатора локализации
locale_validator = LocaleValidator()

def faq_guard(faq_items: List[Dict[str, str]]) -> None:
    """Проверяет что FAQ содержит ровно 6 Q&A"""
    if not faq_items:
        raise ValidationError("FAQ must contain exactly 6 Q&A, got 0")
    
    if len(faq_items) != 6:
        raise ValidationError(f"FAQ must contain exactly 6 Q&A, got {len(faq_items)}")
    
    # Проверяем что все элементы имеют вопрос и ответ
    for i, item in enumerate(faq_items):
        question = item.get('question', '') or item.get('q', '')
        answer = item.get('answer', '') or item.get('a', '')
        
        if not question.strip() or not answer.strip():
            raise ValidationError(f"FAQ item {i+1} has empty question or answer")
        
        # Дополнительная проверка на минимальную длину
        if len(question.strip()) < 5:
            raise ValidationError(f"FAQ item {i+1} question too short: {len(question.strip())} chars")
        
        if len(answer.strip()) < 10:
            raise ValidationError(f"FAQ item {i+1} answer too short: {len(answer.strip())} chars")
    
    logger.info(f"✅ FAQ validation passed: {len(faq_items)} Q&A")

def specs_guard(specs: List[Dict[str, str]], locale: str = 'ru') -> Tuple[List[Dict[str, str]], bool]:
    """
    Проверяет и нормализует характеристики (3-8 элементов)
    Возвращает (normalized_specs, was_clamped)
    """
    if not specs:
        raise ValidationError("Specs must contain at least 3 items, got 0")
    
    # СТРОГАЯ ВАЛИДАЦИЯ: проверяем смешение локалей в характеристиках
    is_valid, errors = locale_validator.validate_specs_locale_strict(specs, locale)
    if not is_valid:
        raise ValidationError(f"Locale mixing detected in specs ({locale}): {'; '.join(errors)}")
    
    # Проверяем валидные элементы
    valid_specs = []
    for spec in specs:
        name = spec.get('name', '') or spec.get('label', '')
        value = spec.get('value', '')
        
        if name.strip() and value.strip():
            valid_specs.append(spec)
    
    if len(valid_specs) < 3:
        raise ValidationError(f"Specs must contain at least 3 valid items, got {len(valid_specs)}")
    
    # Приоритизируем и усекаем до 8 элементов
    was_clamped = len(valid_specs) > 8
    if was_clamped:
        valid_specs = locale_validator.prioritize_specs(valid_specs, locale)
        logger.info(f"✅ Specs validation passed: {len(valid_specs)} items (clamped from {len(specs)})")
    else:
        logger.info(f"✅ Specs validation passed: {len(valid_specs)} items")
    
    return valid_specs, was_clamped

def description_guard(description: str) -> None:
    """Проверяет что описание содержит минимум 2 абзаца"""
    if not description or not description.strip():
        raise ValidationError("Description must contain at least 2 paragraphs")
    
    # Проверяем что описание достаточно длинное (минимум 200 символов)
    if len(description.strip()) < 200:
        raise ValidationError(f"Description must be at least 200 characters, got {len(description.strip())}")
    
    # Проверяем наличие точек (признак предложений)
    sentences = description.count('.')
    if sentences < 4:  # Минимум 4 предложения для 2 абзацев
        raise ValidationError(f"Description must contain at least 4 sentences, got {sentences}")
    
    logger.info(f"✅ Description validation passed: {len(description)} chars, {sentences} sentences")

def anti_placeholders_guard(content: str, field_name: str) -> None:
    """Проверяет контент на наличие заглушек"""
    is_valid, errors = locale_validator.validate_anti_placeholders(content)
    if not is_valid:
        raise ValidationError(f"Placeholders found in {field_name}: {'; '.join(errors)}")
    
    logger.info(f"✅ Anti-placeholders validation passed for {field_name}")

def locale_content_guard(content: str, locale: str, field_name: str) -> None:
    """Проверяет контент на соответствие локали"""
    is_valid, errors = locale_validator.validate_locale_content(content, locale)
    if not is_valid:
        raise ValidationError(f"Locale validation failed for {field_name} ({locale}): {'; '.join(errors)}")
    
    logger.info(f"✅ Locale validation passed for {field_name} ({locale})")

def structure_guard(blocks: Dict[str, Any], locale: str) -> None:
    """Проверяет структуру блоков контента"""
    is_valid, errors = locale_validator.validate_structure(blocks, locale)
    if not is_valid:
        raise ValidationError(f"Structure validation failed for {locale}: {'; '.join(errors)}")
    
    logger.info(f"✅ Structure validation passed for {locale}")

def note_buy_guard(note_buy: str, locale: str = 'ru', specs: List[Dict[str, str]] = None, h1: str = "") -> Dict[str, Any]:
    """Проверяет note-buy на смешение локалей и автоматически санитизирует"""
    issues = []
    sanitized = False
    source = "original"
    
    if not note_buy or not note_buy.strip():
        return {
            'valid': False,
            'issues': ['empty_note_buy'],
            'sanitized': False,
            'source': 'empty'
        }
    
    # Проверяем на смешение локалей
    if locale == 'ru':
        # Ищем UA-токены в RU note-buy
        ua_patterns = [
            r'[іїєґ\']',  # UA буквы
            r'тепл\w+\s+віс\w+',  # "теплий віск"
            r'банці',  # "банці"
            r'перлин\w+',  # "перлина"
            r'купити',  # "купити" вместо "купить"
            r'нашому\s+інтернет-магазині'  # "нашому інтернет-магазині"
        ]
    else:  # ua
        # Ищем RU-токены в UA note-buy
        ru_patterns = [
            r'[ыэъё]',  # RU буквы
            r'тепл\w+\s+воск',  # "теплый воск"
            r'банке',  # "банке"
            r'перлин\w+',  # "перлина"
            r'купить',  # "купить" вместо "купити"
            r'нашем\s+интернет-магазине'  # "нашем интернет-магазине"
        ]
    
    import re
    patterns = ua_patterns if locale == 'ru' else ru_patterns
    
    for pattern in patterns:
        if re.search(pattern, note_buy, re.IGNORECASE):
            issues.append('locale_mixing')
            break
    
    # Проверяем на пустое содержимое в <strong> тегах
    import re
    strong_pattern = r'<strong>(.*?)</strong>'
    strong_matches = re.findall(strong_pattern, note_buy, re.DOTALL)
    
    empty_strong = False
    for match in strong_matches:
        if not match.strip() or match.strip() in ['купить', 'купити']:
            empty_strong = True
            issues.append('empty_strong_content')
            break
    
    # Если найдено смешение локалей ИЛИ пустое содержимое в strong, санитизируем
    if 'locale_mixing' in issues or empty_strong:
        logger.warning(f"⚠️ Обнаружена проблема в note-buy для {locale}: {note_buy[:50]}...")
        
        # Строим безопасное название из specs
        if specs or h1:
            from src.processing.safe_templates import SafeTemplates
            safe_templates = SafeTemplates()
            # Используем h1 для извлечения бренда/серии/объема
            safe_note_buy = safe_templates.render_note_buy(h1, locale, specs or [])
            sanitized = True
            source = "safe_constructor"
            
            logger.info(f"✅ Note-buy санитизирован для {locale}: {safe_note_buy[:50]}...")
            
            return {
                'valid': True,
                'issues': [],
                'sanitized': True,
                'source': 'safe_constructor',
                'sanitized_content': safe_note_buy
            }
        else:
            logger.error(f"❌ Не удалось санитизировать note-buy для {locale}: нет specs")
            return {
                'valid': False,
                'issues': ['locale_mixing_no_specs'] if 'locale_mixing' in issues else ['empty_strong_no_specs'],
                'sanitized': False,
                'source': 'failed_sanitization'
            }
    
    return {
        'valid': True,
        'issues': [],
        'sanitized': False,
        'source': 'original'
    }

def locale_title_guard(title: str, locale: str, specs: List[Dict[str, str]] = None) -> Dict[str, Any]:
    """Проверяет заголовок на смешение локалей и санитизирует при необходимости"""
    issues = []
    sanitized = False
    source = "original"
    
    if not title or not title.strip():
        return {
            'valid': False,
            'issues': ['empty_title'],
            'sanitized': False,
            'source': 'empty'
        }
    
    # Проверяем на смешение локалей
    if locale == 'ru':
        # Ищем UA-токены в RU заголовке
        ua_patterns = [
            r'[іїєґ\']',  # UA буквы
            r'віск',  # "віск" вместо "воск"
            r'банц[іи]',  # "банці" вместо "банке"
            r'перлин\w+',  # "перлина" вместо "жемчуг"
            r'картридж[іи]',  # "картриджі" вместо "картридже"
            r'гранул[аі]',  # "гранули" вместо "гранулы"
            r'тепл\w+\s+віс\w+'  # "теплий віск"
        ]
    else:  # ua
        # Ищем RU-токены в UA заголовке
        ru_patterns = [
            r'[ыэъё]',  # RU буквы
            r'воск',  # "воск" вместо "віск"
            r'банк[ае]',  # "банке" вместо "банці"
            r'жемчуг',  # "жемчуг" вместо "перлина"
            r'картридже',  # "картридже" вместо "картриджі"
            r'гранулы',  # "гранулы" вместо "гранули"
            r'тепл\w+\s+воск'  # "теплый воск"
        ]
    
    import re
    patterns = ua_patterns if locale == 'ru' else ru_patterns
    
    for pattern in patterns:
        if re.search(pattern, title, re.IGNORECASE):
            issues.append('locale_mixing')
            break
    
    # Если найдено смешение локалей, санитизируем
    if 'locale_mixing' in issues:
        logger.warning(f"⚠️ Обнаружено смешение локалей в заголовке для {locale}: {title[:50]}...")
        
        # Строим безопасное название из specs
        if specs:
            from src.processing.safe_templates import SafeTemplates
            safe_templates = SafeTemplates()
            safe_title = safe_templates._build_safe_name_from_specs(specs, locale, title)
            sanitized = True
            source = "safe_constructor"
            
            logger.info(f"✅ Заголовок санитизирован для {locale}: {safe_title[:50]}...")
            
            return {
                'valid': True,
                'issues': [],
                'sanitized': True,
                'source': 'safe_constructor',
                'sanitized_content': safe_title
            }
        else:
            logger.error(f"❌ Не удалось санитизировать заголовок для {locale}: нет specs")
            return {
                'valid': False,
                'issues': ['locale_mixing_no_specs'],
                'sanitized': False,
                'source': 'failed_sanitization'
            }
    
    return {
        'valid': True,
        'issues': [],
        'sanitized': False,
        'source': 'original'
    }
