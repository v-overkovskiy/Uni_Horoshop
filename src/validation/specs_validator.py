"""
Валидатор характеристик для предотвращения выдуманных данных
"""
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

def validate_specs_integrity(final_specs: List[Dict[str, str]], source_facts: List[Tuple[str, str]]) -> Tuple[List[Dict[str, str]], str]:
    """
    Проверяет, что финальные характеристики совпадают с исходником.
    Если нет — возвращает NEEDS_REVISIONS и исправляет.
    
    Args:
        final_specs: Финальные характеристики в формате [{"name": "Тип", "value": "Воскоплав"}]
        source_facts: Исходные факты из HTML в формате [("Тип", "Воскоплав"), ...]
    
    Returns:
        Tuple[отфильтрованные характеристики, статус]
    """
    if not source_facts:
        logger.warning("Нет исходных фактов для валидации - возвращаем пустой список")
        return [], "VALID"
    
    # Импортируем функцию строгого фильтра
    from src.parsing.specs_extractor import strict_filter_fake_characteristics
    
    # Применяем строгий фильтр
    filtered_specs = strict_filter_fake_characteristics(final_specs, source_facts)
    
    # Проверяем, были ли удалены характеристики
    if len(filtered_specs) != len(final_specs):
        removed_count = len(final_specs) - len(filtered_specs)
        logger.warning(f"Критик добавил {removed_count} выдуманных характеристик — исправляем!")
        return filtered_specs, "NEEDS_REVISIONS: Fake specs added"
    
    logger.info(f"✅ Валидация характеристик пройдена: {len(filtered_specs)} характеристик соответствуют исходнику")
    return final_specs, "VALID"

def validate_and_filter_specs(final_specs: List[Dict[str, str]], source_facts: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    """
    Жёстко удаляет всё, что не совпадает с source_facts по ключу и значению.
    
    Args:
        final_specs: Финальные характеристики
        source_facts: Исходные факты из HTML
    
    Returns:
        Отфильтрованный список характеристик
    """
    if not source_facts:
        logger.warning("Нет исходных фактов для фильтрации - возвращаем пустой список")
        return []
    
    # Создаем множество для быстрого поиска (нормализованные ключи и значения)
    valid_pairs = set()
    for key, value in source_facts:
        normalized_key = key.strip().lower()
        normalized_value = value.strip().lower()
        valid_pairs.add((normalized_key, normalized_value))
    
    filtered_specs = []
    removed_count = 0
    
    for spec in final_specs:
        spec_key = spec.get('name', '').strip().lower()
        spec_value = spec.get('value', '').strip().lower()
        
        if (spec_key, spec_value) in valid_pairs:
            filtered_specs.append(spec)
        else:
            removed_count += 1
            logger.warning(f"🚫 Удаляем выдуманную характеристику после ContentCritic: {spec.get('name', '')}: {spec.get('value', '')}")
    
    if removed_count > 0:
        logger.info(f"🔒 Пост-валидация: удалено {removed_count} выдуманных характеристик")
    
    return filtered_specs

def validate_specs_against_source(final_specs: List[Dict[str, str]], source_html: str, locale: str = 'ru') -> Tuple[List[Dict[str, str]], str]:
    """
    Валидирует характеристики против исходного HTML
    
    Args:
        final_specs: Финальные характеристики
        source_html: Исходный HTML страницы
        locale: Локаль
    
    Returns:
        Tuple[отфильтрованные характеристики, статус]
    """
    try:
        # Извлекаем исходные факты из HTML
        from src.parsing.specs_extractor import extract_specs
        
        # Получаем исходные характеристики из HTML
        source_specs = extract_specs(source_html, locale)
        
        # Преобразуем в формат кортежей для валидации
        source_facts = [(spec.get('name', ''), spec.get('value', '')) for spec in source_specs]
        
        # Валидируем
        return validate_specs_integrity(final_specs, source_facts)
        
    except Exception as e:
        logger.error(f"❌ Ошибка валидации характеристик: {e}")
        return final_specs, "ERROR"

def log_specs_changes(original_specs: List[Dict[str, str]], final_specs: List[Dict[str, str]]) -> None:
    """
    Логирует изменения в характеристиках
    
    Args:
        original_specs: Исходные характеристики
        final_specs: Финальные характеристики
    """
    original_count = len(original_specs)
    final_count = len(final_specs)
    
    if original_count != final_count:
        logger.warning(f"📊 Изменение количества характеристик: {original_count} → {final_count}")
        
        # Логируем добавленные характеристики
        original_keys = {spec.get('name', '').lower() for spec in original_specs}
        final_keys = {spec.get('name', '').lower() for spec in final_specs}
        
        added_keys = final_keys - original_keys
        removed_keys = original_keys - final_keys
        
        if added_keys:
            logger.warning(f"➕ Добавлены характеристики: {list(added_keys)}")
        
        if removed_keys:
            logger.warning(f"➖ Удалены характеристики: {list(removed_keys)}")
    else:
        logger.info(f"📊 Количество характеристик не изменилось: {final_count}")
