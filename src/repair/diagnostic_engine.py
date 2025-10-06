"""
Диагностический движок для выявления первого падающего guard per-locale
"""
import logging
from typing import Dict, List, Any, Tuple, Optional
from src.validation.guards import (
    faq_guard, specs_guard, description_guard, ValidationError,
    anti_placeholders_guard, locale_content_guard, structure_guard
)
from src.validation.locale_validator import LocaleValidator

logger = logging.getLogger(__name__)

class DiagnosticEngine:
    """Движок диагностики для выявления проблем в контенте"""
    
    def __init__(self):
        self.locale_validator = LocaleValidator()
    
    def diagnose_content(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """
        Диагностирует контент и возвращает первый падающий guard
        Возвращает: {
            'status': 'valid'|'failed',
            'first_failing_guard': 'GUARD_NAME',
            'error_message': 'описание ошибки',
            'suggested_fix': 'рекомендация по исправлению'
        }
        """
        try:
            # 1. STRUCTURE GUARD - проверяем базовую структуру
            try:
                structure_guard(content, locale)
                logger.debug(f"✅ STRUCTURE guard passed for {locale}")
            except ValidationError as e:
                return self._create_diagnosis('STRUCTURE', str(e), f"Проверить наличие h2.prod-title, note-buy, FAQ=6, specs≥3")
            
            # 2. FAQ GUARD - проверяем FAQ
            try:
                faq_guard(content.get('faq', []))
                logger.debug(f"✅ FAQ guard passed for {locale}")
            except ValidationError as e:
                return self._create_diagnosis('FAQ', str(e), f"Сгенерировать ровно 6 Q&A для {locale}")
            
            # 3. SPECS GUARD - проверяем характеристики
            try:
                specs_guard(content.get('specs', []), locale)
                logger.debug(f"✅ SPECS guard passed for {locale}")
            except ValidationError as e:
                return self._create_diagnosis('SPECS_RANGE', str(e), f"Сгенерировать 3-8 характеристик для {locale}")
            
            # 4. DESCRIPTION GUARD - проверяем описание
            try:
                description_guard(content.get('description', ''))
                logger.debug(f"✅ DESCRIPTION guard passed for {locale}")
            except ValidationError as e:
                return self._create_diagnosis('DESCRIPTION', str(e), f"Сгенерировать описание 2×3 предложения для {locale}")
            
            # 5. ANTI-PLACEHOLDERS GUARD - проверяем заглушки
            try:
                anti_placeholders_guard(content.get('description', ''), 'description')
                anti_placeholders_guard(content.get('note_buy', ''), 'note_buy')
                logger.debug(f"✅ ANTI-PLACEHOLDERS guard passed for {locale}")
            except ValidationError as e:
                return self._create_diagnosis('PLACEHOLDER', str(e), f"Убрать заглушки и сгенерировать реальный контент для {locale}")
            
            # 6. LOCALE GUARD - проверяем смешение локалей
            try:
                locale_content_guard(content.get('description', ''), locale, 'description')
                locale_content_guard(content.get('note_buy', ''), locale, 'note_buy')
                logger.debug(f"✅ LOCALE guard passed for {locale}")
            except ValidationError as e:
                return self._create_diagnosis('LOCALE', str(e), f"Исправить смешение локалей в {locale} контенте")
            
            # Все проверки прошли
            return self._create_diagnosis('VALID', '', '')
            
        except Exception as e:
            return self._create_diagnosis('UNKNOWN', str(e), f"Неизвестная ошибка при диагностике {locale}")
    
    def _create_diagnosis(self, guard_name: str, error_message: str, suggested_fix: str) -> Dict[str, Any]:
        """Создает результат диагностики"""
        return {
            'status': 'failed' if guard_name != 'VALID' else 'valid',
            'first_failing_guard': guard_name,
            'error_message': error_message,
            'suggested_fix': suggested_fix
        }
    
    def batch_diagnose_repair_report(self, repair_report_path: str) -> Dict[str, Any]:
        """
        Диагностирует все записи из repair_report
        Возвращает сводку по проблемам
        """
        import pandas as pd
        
        try:
            df = pd.read_excel(repair_report_path)
            logger.info(f"📋 Загружен repair_report: {len(df)} записей")
            
            diagnosis_summary = {
                'total_records': len(df),
                'guards_failing': {},
                'locales_failing': {'ru': 0, 'ua': 0},
                'recommendations': []
            }
            
            for index, row in df.iterrows():
                url = row.get('url', '')
                ru_valid = row.get('ru_valid', False)
                ua_valid = row.get('ua_valid', False)
                
                logger.info(f"🔍 Диагностика {index + 1}: {url}")
                
                if not ru_valid:
                    diagnosis_summary['locales_failing']['ru'] += 1
                    logger.warning(f"   ❌ RU локаль провалена")
                
                if not ua_valid:
                    diagnosis_summary['locales_failing']['ua'] += 1
                    logger.warning(f"   ❌ UA локаль провалена")
            
            # Общие рекомендации
            if diagnosis_summary['locales_failing']['ru'] > 0:
                diagnosis_summary['recommendations'].append("Ремонт RU локали: проверить парсинг и генерацию контента")
            if diagnosis_summary['locales_failing']['ua'] > 0:
                diagnosis_summary['recommendations'].append("Ремонт UA локали: проверить разделение локалей и генерацию")
            
            return diagnosis_summary
            
        except Exception as e:
            logger.error(f"❌ Ошибка диагностики repair_report: {e}")
            return {'error': str(e)}

