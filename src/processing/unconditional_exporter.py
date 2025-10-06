"""
Безусловный экспорт - каждая карточка попадает в итог
"""
import logging
import pandas as pd
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class UnconditionalExporter:
    """Экспорт с гарантией 100% покрытия"""
    
    def __init__(self, output_file: str = "descriptions.xlsx"):
        self.output_file = output_file
        self.results = []
    
    def add_result(self, result: Dict[str, Any]):
        """Добавляет результат (поштучная запись)"""
        # Нормализуем результат
        normalized = self._normalize_result(result)
        self.results.append(normalized)
        
        # Сразу записываем в файл
        self._append_to_file(normalized)
        
        logger.info(f"✅ Добавлен результат: {result.get('url', 'unknown')}")
    
    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализует результат для записи - только 3 поля"""
        return {
            'URL': result.get('url', ''),
            'RU_HTML': result.get('ru_html', ''),
            'UA_HTML': result.get('ua_html', '')
        }
    
    def _append_to_file(self, row: Dict[str, Any]):
        """Добавляет строку в файл (поштучная запись)"""
        try:
            # Проверяем, существует ли файл
            if os.path.exists(self.output_file):
                # Читаем существующий файл
                df_existing = pd.read_excel(self.output_file)
                # Добавляем новую строку
                df_new = pd.DataFrame([row])
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                # Создаем новый файл
                df_combined = pd.DataFrame([row])
            
            # Сохраняем (перезаписываем)
            df_combined.to_excel(self.output_file, index=False)
            logger.debug(f"📝 Строка записана в {self.output_file}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка записи в файл: {e}")
            # Только если файл заблокирован, создаем резервный
            if "Permission denied" in str(e) or "in use" in str(e).lower():
                backup_file = f"descriptions_backup_{int(datetime.now().timestamp())}.xlsx"
                try:
                    df_backup = pd.DataFrame([row])
                    df_backup.to_excel(backup_file, index=False)
                    logger.info(f"📋 Создан резервный файл (файл заблокирован): {backup_file}")
                except Exception as backup_e:
                    logger.error(f"❌ Ошибка создания резервного файла: {backup_e}")
            else:
                logger.error(f"❌ Критическая ошибка записи: {e}")
    
    def write_final_file(self):
        """Записывает финальный файл с правильной структурой - только Excel"""
        try:
            if not self.results:
                logger.warning("⚠️ Нет результатов для записи")
                return
            
            # Создаем DataFrame из всех результатов
            df = pd.DataFrame(self.results)
            
            # Сохраняем только в Excel (перезаписываем)
            df.to_excel(self.output_file, index=False)
            logger.info(f"✅ Финальный файл записан: {self.output_file}")
            logger.info(f"📊 Записано {len(df)} строк с колонками: {list(df.columns)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка записи финального файла: {e}")
            # Только если файл заблокирован, создаем резервный
            if "Permission denied" in str(e) or "in use" in str(e).lower():
                backup_file = f"descriptions_final_backup_{int(datetime.now().timestamp())}.xlsx"
                try:
                    df = pd.DataFrame(self.results)
                    df.to_excel(backup_file, index=False)
                    logger.info(f"📋 Создан резервный файл (файл заблокирован): {backup_file}")
                except Exception as backup_e:
                    logger.error(f"❌ Ошибка создания резервного файла: {backup_e}")
            else:
                logger.error(f"❌ Критическая ошибка записи финального файла: {e}")
    
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику экспорта - только Excel"""
        if not self.results:
            return {
                'total_rows': 0,
                'ru_html_count': 0,
                'ua_html_count': 0,
                'avg_ru_html_length': 0,
                'avg_ua_html_length': 0
            }
        
        df = pd.DataFrame(self.results)
        
        # Подсчитываем статистику HTML фрагментов
        ru_html_lengths = df['RU_HTML'].str.len()
        ua_html_lengths = df['UA_HTML'].str.len()
        
        return {
            'total_rows': len(df),
            'ru_html_count': (df['RU_HTML'] != '').sum(),
            'ua_html_count': (df['UA_HTML'] != '').sum(),
            'avg_ru_html_length': ru_html_lengths.mean(),
            'avg_ua_html_length': ua_html_lengths.mean(),
            'total_ru_html_length': ru_html_lengths.sum(),
            'total_ua_html_length': ua_html_lengths.sum()
        }
    
    def create_safe_result(self, url: str, locale: str, h1: str, 
                          facts: Dict[str, Any], reason: str = "safe_fallback") -> Dict[str, Any]:
        """Создает безопасный результат для неуспешных случаев"""
        from src.processing.safe_templates import SafeTemplates
        
        templates = SafeTemplates()
        safe_blocks = templates.render_safe_blocks(h1, facts, locale)
        
        return {
            'url': url,
            'locale': locale,
            'export_mode': 'safe_full',
            'flags': [reason],
            'needs_review': True,
            'consistency_fixes': [],
            'html_length': 0,  # Без HTML контента
            'processed': True,
            'retries': 0,
            'network_errors': 1,
            'budget_violation': False,
            'fallback_reason': reason,
            'safe_facts_only': True,
            'controversial_data_removed': True,
            'safe_blocks': safe_blocks
        }
    
    def create_specs_only_result(self, url: str, locale: str, h1: str, 
                                facts: Dict[str, Any], reason: str = "network_failed") -> Dict[str, Any]:
        """Создает результат только с характеристиками"""
        from src.processing.safe_templates import SafeTemplates
        
        templates = SafeTemplates()
        safe_blocks = templates.render_safe_blocks(h1, facts, locale)
        
        return {
            'url': url,
            'locale': locale,
            'export_mode': 'specs_only',
            'flags': [reason],
            'needs_review': True,
            'consistency_fixes': [],
            'html_length': 0,
            'processed': True,
            'retries': 1,
            'network_errors': 1,
            'budget_violation': False,
            'fallback_reason': reason,
            'safe_facts_only': True,
            'controversial_data_removed': True,
            'safe_blocks': safe_blocks
        }
