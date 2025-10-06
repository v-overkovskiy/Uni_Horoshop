"""
Система очереди ремонта для URL, которые падают на базовой валидации
"""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RepairReason(Enum):
    """Причины отправки в ремонт"""
    DESC_TOO_SHORT = "desc_too_short"  # Описание менее 4 предложений
    VOLUME_CONFLICT = "volume_conflict"  # Конфликт объемных данных
    MASS_CONFLICT = "mass_conflict"  # Конфликт массовых данных
    LOCALE_MIXING = "locale_mixing"  # Смешение локалей
    SPECS_INVALID = "specs_invalid"  # Невалидные характеристики
    FAQ_INVALID = "faq_invalid"  # Невалидный FAQ
    ANTI_PLACEHOLDERS = "anti_placeholders"  # Анти-заглушки
    STRUCTURE_INVALID = "structure_invalid"  # Невалидная структура

@dataclass
class RepairItem:
    """Элемент очереди ремонта"""
    url: str
    input_index: int
    failing_locale: str  # 'ru' или 'ua'
    reason: RepairReason
    original_result: Dict[str, Any]  # Оригинальный результат
    error_details: str  # Детали ошибки
    
class RepairQueue:
    """Очередь ремонта для URL с проблемами валидации"""
    
    def __init__(self):
        self.queue: List[RepairItem] = []
        self.completed: List[RepairItem] = []
        self.failed: List[RepairItem] = []
        
    def enqueue_repair(self, url: str, input_index: int, failing_locale: str, 
                      reason: RepairReason, original_result: Dict[str, Any], 
                      error_details: str = "") -> None:
        """Добавляет URL в очередь ремонта"""
        
        repair_item = RepairItem(
            url=url,
            input_index=input_index,
            failing_locale=failing_locale,
            reason=reason,
            original_result=original_result,
            error_details=error_details
        )
        
        self.queue.append(repair_item)
        logger.info(f"🔧 URL добавлен в очередь ремонта: {url} (индекс: {input_index}, локаль: {failing_locale}, причина: {reason.value})")
    
    def get_pending_items(self) -> List[RepairItem]:
        """Возвращает список элементов, ожидающих ремонта"""
        return self.queue.copy()
    
    def mark_completed(self, repair_item: RepairItem, repaired_result: Dict[str, Any]) -> None:
        """Отмечает элемент как успешно отремонтированный"""
        if repair_item in self.queue:
            self.queue.remove(repair_item)
            self.completed.append(repair_item)
            logger.info(f"✅ Ремонт завершен: {repair_item.url} (локаль: {repair_item.failing_locale})")
        else:
            logger.warning(f"⚠️ Попытка отметить несуществующий элемент как завершенный: {repair_item.url}")
    
    def mark_failed(self, repair_item: RepairItem, failure_reason: str) -> None:
        """Отмечает элемент как неудачно отремонтированный"""
        if repair_item in self.queue:
            self.queue.remove(repair_item)
            repair_item.error_details = failure_reason
            self.failed.append(repair_item)
            logger.error(f"❌ Ремонт не удался: {repair_item.url} (причина: {failure_reason})")
        else:
            logger.warning(f"⚠️ Попытка отметить несуществующий элемент как неудачный: {repair_item.url}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику очереди ремонта"""
        total_items = len(self.queue) + len(self.completed) + len(self.failed)
        
        # Подсчет по причинам
        reason_stats = {}
        for item in self.queue + self.completed + self.failed:
            reason = item.reason.value
            reason_stats[reason] = reason_stats.get(reason, 0) + 1
        
        return {
            'total_items': total_items,
            'pending_count': len(self.queue),
            'completed_count': len(self.completed),
            'failed_count': len(self.failed),
            'completion_rate': len(self.completed) / total_items if total_items > 0 else 0,
            'reason_distribution': reason_stats
        }
    
    def clear(self) -> None:
        """Очищает очередь ремонта"""
        self.queue.clear()
        self.completed.clear()
        self.failed.clear()
        logger.info("🧹 Очередь ремонта очищена")
    
    def has_pending_items(self) -> bool:
        """Проверяет, есть ли элементы в очереди"""
        return len(self.queue) > 0
