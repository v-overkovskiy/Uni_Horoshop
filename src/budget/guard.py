"""
BudgetGuard - жёсткий контроль бюджета LLM вызовов
"""
import logging
from typing import Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BudgetViolation:
    """Нарушение бюджета"""
    item_id: str
    locale: str
    expected_calls: int
    actual_calls: int
    violation_type: str

class BudgetError(Exception):
    """Ошибка бюджета"""
    pass

class BudgetGuard:
    """Жёсткий контроль бюджета LLM вызовов"""
    
    def __init__(self, mandatory_calls_per_locale: int = 1):
        self.mandatory_calls_per_locale = mandatory_calls_per_locale
        self.calls_log: Dict[Tuple[str, str], int] = {}  # {(canonical_slug, locale): count}
        self.violations: List[BudgetViolation] = []
    
    def record_call(self, canonical_slug: str, locale: str) -> bool:
        """Записать вызов LLM"""
        key = (canonical_slug, locale)
        self.calls_log[key] = self.calls_log.get(key, 0) + 1
        logger.debug(f"Записан вызов LLM для {canonical_slug} {locale} (всего: {self.calls_log[key]})")
        return True
    
    def tick(self, slug: str, locale: str):
        """Увеличить счётчик вызовов для slug+locale"""
        key = (slug, locale)
        n = self.calls_log.get(key, 0) + 1
        self.calls_log[key] = n
        if n > self.mandatory_calls_per_locale:
            raise BudgetError(f"Exceeded {locale} for {slug}: {n}>{self.mandatory_calls_per_locale}")
    
    def assert_required(self, slug: str):
        """Проверить, что для slug есть ровно 1 вызов на ru и ua"""
        for loc in ("ru", "ua"):
            n = self.calls_log.get((slug, loc), 0)
            if n != self.mandatory_calls_per_locale:
                raise BudgetError(f"Expected {self.mandatory_calls_per_locale} {loc} calls for {slug}, got {n}")
    
    def validate_item(self, canonical_slug: str) -> bool:
        """Валидация бюджета для товара"""
        is_valid = True
        
        # Проверяем RU
        ru_key = (canonical_slug, 'ru')
        ru_calls = self.calls_log.get(ru_key, 0)
        if ru_calls != self.mandatory_calls_per_locale:
            violation = BudgetViolation(
                item_id=canonical_slug,
                locale='ru',
                expected_calls=self.mandatory_calls_per_locale,
                actual_calls=ru_calls,
                violation_type='incorrect_call_count'
            )
            self.violations.append(violation)
            logger.error(f"Нарушение бюджета RU для {canonical_slug}: ожидалось {self.mandatory_calls_per_locale}, получено {ru_calls}")
            is_valid = False
        
        # Проверяем UA
        ua_key = (canonical_slug, 'ua')
        ua_calls = self.calls_log.get(ua_key, 0)
        if ua_calls != self.mandatory_calls_per_locale:
            violation = BudgetViolation(
                item_id=canonical_slug,
                locale='ua',
                expected_calls=self.mandatory_calls_per_locale,
                actual_calls=ua_calls,
                violation_type='incorrect_call_count'
            )
            self.violations.append(violation)
            logger.error(f"Нарушение бюджета UA для {canonical_slug}: ожидалось {self.mandatory_calls_per_locale}, получено {ua_calls}")
            is_valid = False
        
        return is_valid
    
    def validate_all(self) -> Dict[str, Any]:
        """Валидация всех товаров"""
        # Получаем уникальные slug
        unique_slugs = set()
        for (slug, locale) in self.calls_log.keys():
            unique_slugs.add(slug)
        
        total_items = len(unique_slugs)
        valid_items = 0
        failed_items = []
        
        for slug in unique_slugs:
            if self.validate_item(slug):
                valid_items += 1
            else:
                failed_items.append(slug)
        
        return {
            'total_items': total_items,
            'valid_items': valid_items,
            'failed_items': failed_items,
            'violations': self.violations,
            'success_rate': valid_items / total_items if total_items > 0 else 0
        }
    
    def get_stats(self, canonical_slug: str) -> Dict[str, Any]:
        """Получить статистику для товара"""
        ru_key = (canonical_slug, 'ru')
        ua_key = (canonical_slug, 'ua')
        
        ru_calls = self.calls_log.get(ru_key, 0)
        ua_calls = self.calls_log.get(ua_key, 0)
        total_calls = ru_calls + ua_calls
        
        is_valid = (ru_calls == self.mandatory_calls_per_locale and 
                   ua_calls == self.mandatory_calls_per_locale)
        
        return {
            'ru': ru_calls,
            'ua': ua_calls,
            'total': total_calls,
            'valid': is_valid,
            'expected_per_locale': self.mandatory_calls_per_locale
        }
    
    def reset(self):
        """Сброс лога вызовов"""
        self.calls_log.clear()
        self.violations.clear()
        logger.info("BudgetGuard сброшен")
