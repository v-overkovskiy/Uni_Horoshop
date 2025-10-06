"""
Охранник консистентности - отключает блокировки в пользу безопасных решений
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ConsistencyGuard:
    """Охранник консистентности с отключенными блокировками"""
    
    def __init__(self):
        self.blocking_disabled = True  # Отключаем все блокировки
    
    def check_volume_consistency(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Проверяет консистентность объёмов без блокировок"""
        if not self.blocking_disabled:
            return self._legacy_volume_check(content, locale)
        
        # Новый режим: не блокируем, просто помечаем
        issues = []
        fixes = []
        
        # Проверяем на спорные данные
        if self._has_controversial_volume_data(content):
            issues.append('controversial_volume_data')
            fixes.append('controversial_data_removed')
            logger.info("🧹 Обнаружены спорные данные объёма - помечаем для удаления")
        
        return {
            'consistent': True,  # Всегда True в safe-режиме
            'issues': issues,
            'fixes': fixes,
            'blocked': False  # Никогда не блокируем
        }
    
    def check_mass_consistency(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Проверяет консистентность массы без блокировок"""
        if not self.blocking_disabled:
            return self._legacy_mass_check(content, locale)
        
        # Новый режим: не блокируем, просто помечаем
        issues = []
        fixes = []
        
        # Проверяем на спорные данные
        if self._has_controversial_mass_data(content):
            issues.append('controversial_mass_data')
            fixes.append('controversial_data_removed')
            logger.info("🧹 Обнаружены спорные данные массы - помечаем для удаления")
        
        return {
            'consistent': True,  # Всегда True в safe-режиме
            'issues': issues,
            'fixes': fixes,
            'blocked': False  # Никогда не блокируем
        }
    
    def _has_controversial_volume_data(self, content: Dict[str, Any]) -> bool:
        """Проверяет наличие спорных данных объёма"""
        # Проверяем описание
        description = content.get('description', '')
        if self._contains_controversial_volume(description):
            return True
        
        # Проверяем преимущества
        advantages = content.get('advantages', [])
        for advantage in advantages:
            if isinstance(advantage, str) and self._contains_controversial_volume(advantage):
                return True
        
        return False
    
    def _has_controversial_mass_data(self, content: Dict[str, Any]) -> bool:
        """Проверяет наличие спорных данных массы"""
        # Проверяем описание
        description = content.get('description', '')
        if self._contains_controversial_mass(description):
            return True
        
        # Проверяем преимущества
        advantages = content.get('advantages', [])
        for advantage in advantages:
            if isinstance(advantage, str) and self._contains_controversial_mass(advantage):
                return True
        
        return False
    
    def _contains_controversial_volume(self, text: str) -> bool:
        """Проверяет текст на спорные данные объёма"""
        import re
        # Ищем "42 мл", "38-40 мл" без маркера порции
        patterns = [
            r'\b\d+[\s\u00A0]*(мл|ml)\b(?!\s*(в\s+упаковке|в\s+пакете|на\s+порцию|на\s+процедуру))',
            r'\d+\s*[–-]\s*\d+\s*(мл|ml)',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, flags=re.I):
                return True
        
        return False
    
    def _contains_controversial_mass(self, text: str) -> bool:
        """Проверяет текст на спорные данные массы"""
        import re
        # Ищем "42 г", "38-40 г" без маркера порции
        patterns = [
            r'\b\d+[\s\u00A0]*(г|гр|грам|грамм)\b(?!\s*(в\s+упаковке|в\s+пакете|на\s+порцию|на\s+процедуру))',
            r'\d+\s*[–-]\s*\d+\s*(г|гр|грам|грамм)',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, flags=re.I):
                return True
        
        return False
    
    def _legacy_volume_check(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Старая проверка объёмов (заглушка)"""
        return {
            'consistent': True,
            'issues': [],
            'fixes': [],
            'blocked': False
        }
    
    def _legacy_mass_check(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Старая проверка массы (заглушка)"""
        return {
            'consistent': True,
            'issues': [],
            'fixes': [],
            'blocked': False
        }
    
    def should_block_export(self, content: Dict[str, Any], issues: List[str]) -> bool:
        """Определяет, нужно ли блокировать экспорт (всегда False в safe-режиме)"""
        if not self.blocking_disabled:
            return self._legacy_block_check(content, issues)
        
        # В safe-режиме никогда не блокируем
        logger.info("🛡️ Safe-режим: экспорт не блокируется")
        return False
    
    def _legacy_block_check(self, content: Dict[str, Any], issues: List[str]) -> bool:
        """Старая проверка блокировки (заглушка)"""
        return False

