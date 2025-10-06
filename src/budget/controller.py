"""
Контроллер бюджета LLM вызовов
"""
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BudgetStats:
    """Статистика бюджета"""
    total_calls: int = 0
    calls_per_locale: Dict[str, int] = None
    repair_calls: int = 0
    blocked_items: int = 0
    
    def __post_init__(self):
        if self.calls_per_locale is None:
            self.calls_per_locale = {'ru': 0, 'ua': 0}

class BudgetController:
    """Контроллер бюджета LLM вызовов"""
    
    def __init__(self, 
                 max_calls_per_item: int = 3,
                 max_calls_per_locale: int = 1,
                 max_repair_calls: int = 1):
        self.max_calls_per_item = max_calls_per_item
        self.max_calls_per_locale = max_calls_per_locale
        self.max_repair_calls = max_repair_calls
        
        # Трекинг по товарам
        self.item_budgets: Dict[str, BudgetStats] = {}
        
        # Общая статистика
        self.total_calls = 0
        self.total_blocked = 0
    
    def can_make_call(self, item_id: str, call_type: str, locale: str = None) -> bool:
        """Проверка возможности сделать LLM вызов"""
        if item_id not in self.item_budgets:
            self.item_budgets[item_id] = BudgetStats()
        
        stats = self.item_budgets[item_id]
        
        # Проверяем общий лимит на товар
        if stats.total_calls >= self.max_calls_per_item:
            logger.warning(f"Превышен лимит вызовов для товара {item_id}: {stats.total_calls}/{self.max_calls_per_item}")
            return False
        
        # Проверяем лимит на локаль
        if call_type == 'generate' and locale:
            if stats.calls_per_locale.get(locale, 0) >= self.max_calls_per_locale:
                return False
        
        # Проверяем лимит ремонтов
        if call_type == 'repair':
            if stats.repair_calls >= self.max_repair_calls:
                logger.warning(f"Превышен лимит ремонтов для товара {item_id}: {stats.repair_calls}/{self.max_repair_calls}")
                return False
        
        return True
    
    def record_call(self, item_id: str, call_type: str, locale: str = None) -> bool:
        """Запись LLM вызова"""
        if not self.can_make_call(item_id, call_type, locale):
            return False
        
        if item_id not in self.item_budgets:
            self.item_budgets[item_id] = BudgetStats()
        
        stats = self.item_budgets[item_id]
        
        # Увеличиваем счетчики
        stats.total_calls += 1
        self.total_calls += 1
        
        if call_type == 'generate' and locale:
            stats.calls_per_locale[locale] = stats.calls_per_locale.get(locale, 0) + 1
            # Проверяем превышение лимита после увеличения
            if stats.calls_per_locale[locale] > self.max_calls_per_locale:
                logger.warning(f"Превышен лимит вызовов для локали {locale} товара {item_id}: {stats.calls_per_locale[locale]}/{self.max_calls_per_locale}")
        elif call_type == 'repair':
            stats.repair_calls += 1
        
        logger.info(f"LLM вызов записан: {item_id} {call_type} {locale} (всего: {stats.total_calls})")
        return True
    
    def block_item(self, item_id: str, reason: str):
        """Блокировка товара"""
        if item_id not in self.item_budgets:
            self.item_budgets[item_id] = BudgetStats()
        
        self.item_budgets[item_id].blocked_items += 1
        self.total_blocked += 1
        
        logger.warning(f"Товар заблокирован: {item_id} - {reason}")
    
    def get_stats(self, item_id: str = None) -> Dict:
        """Получение статистики"""
        if item_id:
            if item_id in self.item_budgets:
                stats = self.item_budgets[item_id]
                return {
                    'item_id': item_id,
                    'total_calls': stats.total_calls,
                    'calls_per_locale': stats.calls_per_locale,
                    'repair_calls': stats.repair_calls,
                    'blocked_items': stats.blocked_items,
                    'can_generate_ru': self.can_make_call(item_id, 'generate', 'ru'),
                    'can_generate_ua': self.can_make_call(item_id, 'generate', 'ua'),
                    'can_repair': self.can_make_call(item_id, 'repair')
                }
            else:
                return {'item_id': item_id, 'total_calls': 0, 'calls_per_locale': {'ru': 0, 'ua': 0}, 'repair_calls': 0, 'blocked_items': 0}
        else:
            # Общая статистика
            return {
                'total_items': len(self.item_budgets),
                'total_calls': self.total_calls,
                'total_blocked': self.total_blocked,
                'avg_calls_per_item': self.total_calls / len(self.item_budgets) if self.item_budgets else 0
            }
    
    def reset_item(self, item_id: str):
        """Сброс бюджета для товара"""
        if item_id in self.item_budgets:
            del self.item_budgets[item_id]
            logger.info(f"Бюджет сброшен для товара {item_id}")
    
    def reset_all(self):
        """Сброс всего бюджета"""
        self.item_budgets.clear()
        self.total_calls = 0
        self.total_blocked = 0
        logger.info("Весь бюджет сброшен")
    
    def get_remaining_calls(self, item_id: str, call_type: str, locale: str = None) -> int:
        """Получение оставшихся вызовов"""
        if item_id not in self.item_budgets:
            return self.max_calls_per_item
        
        stats = self.item_budgets[item_id]
        
        if call_type == 'generate' and locale:
            return self.max_calls_per_locale - stats.calls_per_locale.get(locale, 0)
        elif call_type == 'repair':
            return self.max_repair_calls - stats.repair_calls
        else:
            return self.max_calls_per_item - stats.total_calls
