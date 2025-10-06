"""
Условный экспортер - записывает только успешно валидированные результаты
"""
import os
import pandas as pd
import logging
import re
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ConditionalExporter:
    """Экспортер, который записывает только валидные результаты"""
    
    def __init__(self, output_file: str = "descriptions.xlsx", mode: str = "paired_always"):
        self.output_file = output_file
        self.results = []
        self.repair_report = []
        self.mode = mode  # "paired_always" или "strict"
        
        # Буфер для упорядоченного хранения результатов по индексам
        self.ordered_buffer = {}  # Map<index, RowData>
        self.input_urls = []  # Сохраняем исходный порядок URL
        self.input_count = 0
        
        # Метрики для автоматических проверок
        self.specs_clamped_count = 0  # Количество усеченных карточек
        self.total_specs_processed = 0  # Общее количество обработанных характеристик
        self.specs_priority_violations = 0  # Нарушения приоритета
        
        # Метрики для note-buy и заголовков
        self.note_buy_sanitized_count = 0  # Количество санитизированных note-buy
        self.note_buy_source_stats = {'original': 0, 'safe_constructor': 0, 'failed_sanitization': 0}
        self.title_sanitized_count = 0  # Количество санитизированных заголовков
        self.title_source_stats = {'original': 0, 'safe_constructor': 0, 'failed_sanitization': 0}
        
        # Метрики для системы ремонта
        self.repair_enqueued_count = 0  # Количество URL отправленных в ремонт
        self.repair_completed_count = 0  # Количество успешно отремонтированных URL
        self.repair_failed_count = 0  # Количество неудачно отремонтированных URL
        self.sanity_fix_applied_count = 0  # Количество примененных sanity-фиксов
        self.repair_reason_stats = {}  # Статистика по причинам ремонта
        # Нейтральные слова, которые не должны блокировать валидацию
        self.neutral_whitelist = {
            'ru': ['результат', 'максимум', 'минимум', 'оптимум', 'продукт', 'материал'],
            'ua': ['результат', 'максимум', 'мінімум', 'оптимум', 'продукт', 'матеріал']
        }
    
    def initialize_with_urls(self, urls: List[str]) -> None:
        """Инициализирует экспортер с входными URL для обеспечения порядка"""
        self.input_urls = urls.copy()
        self.input_count = len(urls)
        self.ordered_buffer = {}
        logger.info(f"📋 Инициализирован экспортер с {self.input_count} URL")
    
    def add_result_by_index(self, result: Dict[str, Any], index: int) -> None:
        """Добавляет результат по индексу для обеспечения строгого порядка"""
        if index < 1 or index > self.input_count:
            logger.error(f"❌ Недопустимый индекс {index}, ожидается 1-{self.input_count}")
            return
        
        # Проверяем валидность локалей
        ru_valid = self._is_locale_valid(result, 'ru')
        ua_valid = self._is_locale_valid(result, 'ua')
        
        # Нормализуем пробелы в значениях
        normalized_result = self._normalize_spaces_in_values(result)
        
        if self.mode == "paired_always":
            # Режим "всегда пара" - всегда добавляем строку, даже если одна локаль проблемная
            if ru_valid and ua_valid:
                # Обе локали валидны - добавляем как есть
                row_data = self._create_row_data(normalized_result, ru_valid, ua_valid)
                self.ordered_buffer[index] = row_data
                logger.info(f"✅ Добавлен валидный результат по индексу {index}: {result.get('url', 'unknown')}")
            else:
                # Есть проблемы - пытаемся санитизировать
                sanitized_result = self._sanitize_result(normalized_result, ru_valid, ua_valid)
                if sanitized_result:
                    row_data = self._create_row_data(sanitized_result, ru_valid, ua_valid)
                    self.ordered_buffer[index] = row_data
                    logger.info(f"🔧 Добавлен санитизированный результат по индексу {index}: {result.get('url', 'unknown')}")
                else:
                    # Санитизация не помогла - добавляем частичный результат
                    partial_result = self._create_partial_result(normalized_result, ru_valid, ua_valid)
                    row_data = self._create_row_data(partial_result, ru_valid, ua_valid)
                    self.ordered_buffer[index] = row_data
                    logger.warning(f"⚠️ Добавлен частичный результат по индексу {index}: {result.get('url', 'unknown')}")
                
                # Также добавляем в repair_report для дальнейшего анализа
                self._add_to_repair_report(normalized_result, ru_valid, ua_valid)
        else:
            # Строгий режим - только полностью валидные результаты
            if ru_valid and ua_valid:
                row_data = self._create_row_data(normalized_result, ru_valid, ua_valid)
                self.ordered_buffer[index] = row_data
                logger.info(f"✅ Добавлен валидный результат по индексу {index}: {result.get('url', 'unknown')}")
            else:
                self._add_to_repair_report(normalized_result, ru_valid, ua_valid)
    
    def add_result(self, result: Dict[str, Any]) -> None:
        """Добавляет результат с учетом режима экспорта"""
        # Проверяем валидность локалей
        ru_valid = self._is_locale_valid(result, 'ru')
        ua_valid = self._is_locale_valid(result, 'ua')
        
        if self.mode == "paired_always":
            # Режим "всегда пара" - всегда добавляем строку, даже если одна локаль проблемная
            if ru_valid and ua_valid:
                # Обе локали валидны - добавляем как есть
                normalized_result = self._normalize_result(result)
                self.results.append(normalized_result)
                logger.info(f"✅ Добавлен валидный результат: {result.get('url', 'unknown')}")
            else:
                # Есть проблемы - пытаемся санитизировать
                sanitized_result = self._sanitize_result(result, ru_valid, ua_valid)
                if sanitized_result:
                    normalized_result = self._normalize_result(sanitized_result)
                    self.results.append(normalized_result)
                    logger.info(f"🔧 Добавлен санитизированный результат: {result.get('url', 'unknown')}")
                else:
                    # Санитизация не помогла - добавляем частичный результат
                    partial_result = self._create_partial_result(result, ru_valid, ua_valid)
                    normalized_result = self._normalize_result(partial_result)
                    self.results.append(normalized_result)
                    logger.warning(f"⚠️ Добавлен частичный результат: {result.get('url', 'unknown')}")
                
                # Также добавляем в repair_report для дальнейшего анализа
                self._add_to_repair_report(result, ru_valid, ua_valid)
        else:
            # Строгий режим - только полностью валидные результаты
            if ru_valid and ua_valid:
                normalized_result = self._normalize_result(result)
                self.results.append(normalized_result)
                logger.info(f"✅ Добавлен валидный результат: {result.get('url', 'unknown')}")
            else:
                self._add_to_repair_report(result, ru_valid, ua_valid)
    
    def _is_locale_valid(self, result: Dict[str, Any], locale: str) -> bool:
        """Проверяет, валидна ли локаль"""
        # Проверяем флаги ошибок
        flags = result.get('flags', [])
        
        # Если есть ошибки валидации для этой локали - невалидна
        for flag in flags:
            if f'Locale mixing detected in specs ({locale})' in flag:
                return False
            if f'LLM вернул обрезанный JSON для {locale}' in flag:
                return False
            if f'ValidationError' in flag and locale in flag:
                return False
        
        # Проверяем наличие HTML контента
        html_key = f'{locale.upper()}_HTML'
        html_content = result.get(html_key, '')
        
        if not html_content or html_content.strip() == '':
            return False
        
        # Проверяем, что HTML содержит основные блоки
        if '<h2 class="prod-title">' not in html_content:
            return False
        
        return True
    
    def _sanitize_result(self, result: Dict[str, Any], ru_valid: bool, ua_valid: bool) -> Dict[str, Any]:
        """Пытается санитизировать проблемный результат"""
        sanitized = result.copy()
        
        # Если UA невалидна - пытаемся санитизировать
        if not ua_valid:
            ua_html = result.get('UA_HTML', '')
            if ua_html:
                sanitized_ua = self._sanitize_html_content(ua_html, 'ua')
                if sanitized_ua != ua_html:
                    sanitized['UA_HTML'] = sanitized_ua
                    logger.info(f"🔧 Санитизирован UA HTML для {result.get('url', 'unknown')}")
        
        # Если RU невалидна - пытаемся санитизировать
        if not ru_valid:
            ru_html = result.get('RU_HTML', '')
            if ru_html:
                sanitized_ru = self._sanitize_html_content(ru_html, 'ru')
                if sanitized_ru != ru_html:
                    sanitized['RU_HTML'] = sanitized_ru
                    logger.info(f"🔧 Санитизирован RU HTML для {result.get('url', 'unknown')}")
        
        # Проверяем, помогла ли санитизация
        ru_valid_after = self._is_locale_valid(sanitized, 'ru')
        ua_valid_after = self._is_locale_valid(sanitized, 'ua')
        
        if ru_valid_after and ua_valid_after:
            return sanitized
        else:
            return None
    
    def _sanitize_html_content(self, html_content: str, locale: str) -> str:
        """Санитизирует HTML контент, удаляя проблемные слова"""
        if not html_content:
            return html_content
        
        # Получаем список нейтральных слов для этой локали
        neutral_words = self.neutral_whitelist.get(locale, [])
        
        # Паттерны для поиска проблемных слов в описании
        description_patterns = [
            r'<p class="description">(.*?)</p>',
            r'<div class="description">(.*?)</div>'
        ]
        
        sanitized = html_content
        
        for pattern in description_patterns:
            def replace_description(match):
                description = match.group(1)
                # Заменяем проблемные слова на нейтральные
                for word in neutral_words:
                    # Ищем слово в разных падежах
                    word_pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
                    description = word_pattern.sub(word, description)
                return f'<p class="description">{description}</p>'
            
            sanitized = re.sub(pattern, replace_description, sanitized, flags=re.DOTALL)
        
        return sanitized
    
    def _create_partial_result(self, result: Dict[str, Any], ru_valid: bool, ua_valid: bool) -> Dict[str, Any]:
        """Создает частичный результат с валидными блоками"""
        partial = result.copy()
        
        # Если UA невалидна - оставляем только валидные блоки
        if not ua_valid:
            ua_html = result.get('UA_HTML', '')
            if ua_html:
                # Извлекаем валидные блоки (note-buy, specs, FAQ, hero)
                valid_blocks = self._extract_valid_blocks(ua_html)
                partial['UA_HTML'] = valid_blocks
                logger.info(f"🔧 Создан частичный UA HTML для {result.get('url', 'unknown')}")
        
        # Если RU невалидна - оставляем только валидные блоки
        if not ru_valid:
            ru_html = result.get('RU_HTML', '')
            if ru_html:
                # Извлекаем валидные блоки (note-buy, specs, FAQ, hero)
                valid_blocks = self._extract_valid_blocks(ru_html)
                partial['RU_HTML'] = valid_blocks
                logger.info(f"🔧 Создан частичный RU HTML для {result.get('url', 'unknown')}")
        
        return partial
    
    def _extract_valid_blocks(self, html_content: str) -> str:
        """Извлекает только валидные блоки из HTML"""
        if not html_content:
            return html_content
        
        valid_blocks = []
        
        # Извлекаем note-buy
        note_buy_match = re.search(r'<p class="note-buy">(.*?)</p>', html_content, re.DOTALL)
        if note_buy_match:
            valid_blocks.append(note_buy_match.group(0))
        
        # Извлекаем specs
        specs_match = re.search(r'<ul class="specs">(.*?)</ul>', html_content, re.DOTALL)
        if specs_match:
            valid_blocks.append(specs_match.group(0))
        
        # Извлекаем FAQ
        faq_match = re.search(r'<div class="faq">(.*?)</div>', html_content, re.DOTALL)
        if faq_match:
            valid_blocks.append(faq_match.group(0))
        
        # Извлекаем hero
        hero_match = re.search(r'<figure class="hero">(.*?)</figure>', html_content, re.DOTALL)
        if hero_match:
            valid_blocks.append(hero_match.group(0))
        
        # Собираем результат
        if valid_blocks:
            return '\n'.join(valid_blocks)
        else:
            return html_content
    
    def _add_to_repair_report(self, result: Dict[str, Any], ru_valid: bool, ua_valid: bool) -> None:
        """Добавляет проблемный результат в repair_report"""
        repair_entry = {
            'url': result.get('url', 'unknown'),
            'ru_valid': ru_valid,
            'ua_valid': ua_valid,
            'flags': result.get('flags', []),
            'export_mode': self._determine_export_mode(result),
            'needs_review': result.get('needs_review', True),
            'timestamp': datetime.now().isoformat()
        }
        
        self.repair_report.append(repair_entry)

    def _determine_export_mode(self, result: Dict[str, Any]) -> str:
        """Определяет режим экспорта на основе результата"""
        # Проверяем, был ли применен ремонт
        if result.get('repair_applied', False):
            return 'repair'
        
        # Проверяем, есть ли элементы в repair_report (значит был ремонт)
        if hasattr(self, 'repair_report') and self.repair_report:
            # Проверяем, есть ли текущий URL в repair_report
            current_url = result.get('url', '')
            for repair_item in self.repair_report:
                if repair_item.get('url') == current_url:
                    return 'repair'
        
        # Проверяем режим из результата
        export_mode = result.get('export_mode', '')
        if export_mode in ['full', 'fallback', 'specs_only', 'safe_full']:
            return export_mode
        
        # Определяем по валидности - используем правильные ключи
        ru_valid = result.get('RU_Valid', False)
        ua_valid = result.get('UA_Valid', False)
        
        if ru_valid and ua_valid:
            return 'normal'
        elif ru_valid or ua_valid:
            return 'partial'
        else:
            return 'failed'
    
    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализует результат для экспорта"""
        # Определяем валидность локалей
        ru_valid = self._is_locale_valid(result, 'ru')
        ua_valid = self._is_locale_valid(result, 'ua')
        
        # Определяем проблемы
        ru_issues = []
        ua_issues = []
        
        flags = result.get('flags', [])
        for flag in flags:
            if 'ru' in flag.lower() and 'validation' in flag.lower():
                ru_issues.append(flag)
            elif 'ua' in flag.lower() and 'validation' in flag.lower():
                ua_issues.append(flag)
        
        # Добавляем диагностические поля
        diagnostic_fields = self._extract_diagnostic_fields(result, ru_valid, ua_valid)
        
        # Базовые поля
        base_fields = {
            'URL': result.get('url', ''),
            'RU_HTML': result.get('RU_HTML', ''),
            'UA_HTML': result.get('UA_HTML', ''),
            'RU_Valid': ru_valid,
            'UA_Valid': ua_valid,
            'RU_Issues': '; '.join(ru_issues) if ru_issues else '',
            'UA_Issues': '; '.join(ua_issues) if ua_issues else ''
        }
        
        # Объединяем базовые поля с диагностическими
        return {**base_fields, **diagnostic_fields}
    
    def _extract_diagnostic_fields(self, result: Dict[str, Any], ru_valid: bool, ua_valid: bool) -> Dict[str, Any]:
        """Извлекает диагностические поля для прозрачности ремонта"""
        diagnostic = {}
        
        # Источники заголовков
        diagnostic['source_title_ru_snapshot'] = result.get('source_title_ru_snapshot', '')
        diagnostic['source_title_ua_snapshot'] = result.get('source_title_ua_snapshot', '')
        
        # H2 диагностика
        ru_html = result.get('RU_HTML', '')
        ua_html = result.get('UA_HTML', '')
        
        # Извлекаем h2 из HTML
        ru_h2 = self._extract_h2_from_html(ru_html)
        ua_h2 = self._extract_h2_from_html(ua_html)
        
        diagnostic['h2_ru_before'] = ru_h2
        diagnostic['h2_ru_after'] = ru_h2  # После ремонта будет обновлено
        diagnostic['h2_ru_source'] = self._determine_h2_source(ru_h2, result, 'ru')
        diagnostic['h2_ua_before'] = ua_h2
        diagnostic['h2_ua_after'] = ua_h2
        
        # Статус RU HTML
        diagnostic['ru_html_empty'] = not ru_html or len(ru_html.strip()) < 10
        diagnostic['ru_h2_len'] = len(ru_h2) if ru_h2 else 0
        diagnostic['ru_description_paragraphs'] = self._count_description_paragraphs(ru_html)
        diagnostic['ru_description_chars'] = self._count_description_chars(ru_html)
        
        # Locale-mixing диагностика
        diagnostic['ru_locale_mixing_detected'] = self._detect_locale_mixing(ru_html, 'ru')
        diagnostic['ru_mixing_reason'] = self._get_mixing_reason(ru_html, 'ru')
        diagnostic['ru_has_ua_letters'] = self._has_ua_letters(ru_html)
        diagnostic['ru_mixing_tokens'] = self._extract_mixing_tokens(ru_html, 'ru')
        diagnostic['ru_whitelist_hit'] = self._check_whitelist_hit(ru_html, 'ru')
        
        # Specs диагностика
        ru_specs = self._extract_specs_from_html(ru_html)
        ua_specs = self._extract_specs_from_html(ua_html)
        
        diagnostic['specs_count_ru'] = len(ru_specs)
        diagnostic['specs_keys_ru'] = [spec.get('name', '') for spec in ru_specs]
        diagnostic['specs_conflicts_dropped'] = self._get_dropped_conflicts(ru_specs, 'ru')
        diagnostic['specs_fixed_labels'] = self._get_fixed_labels(ru_specs, 'ru')
        
        # Валидации перед экспортом
        diagnostic['faq_jsonld_valid_ru'] = self._validate_faq_jsonld(ru_html)
        diagnostic['note_buy_status_ru'] = self._get_note_buy_status(ru_html)
        diagnostic['product_photo_present_ru'] = self._has_product_photo(ru_html)
        diagnostic['export_mode_final'] = self._determine_export_mode(result)
        diagnostic['repair_scope'] = self._get_repair_scope(result)
        diagnostic['repair_actions_applied'] = self._get_repair_actions(result)
        diagnostic['repair_failure_reason'] = self._get_repair_failure_reason(result)
        
        # Диагностика улучшенной генерации FAQ и note_buy
        enhancement_diagnostic = result.get('enhancement_diagnostic', {})
        diagnostic.update(self._extract_enhancement_diagnostic(enhancement_diagnostic, ru_html, ua_html))
        
        return diagnostic
    
    def _extract_enhancement_diagnostic(self, enhancement_diagnostic: Dict[str, Any], ru_html: str, ua_html: str) -> Dict[str, Any]:
        """Извлекает диагностическую информацию об улучшениях FAQ и note_buy"""
        diagnostic = {}
        
        # FAQ диагностика
        diagnostic['faq_q_lowercase_count'] = enhancement_diagnostic.get('faq_q_lowercase_count', 0)
        diagnostic['faq_unit_mismatch_count'] = enhancement_diagnostic.get('faq_unit_mismatch_count', 0)
        diagnostic['faq_weight_stub_count'] = enhancement_diagnostic.get('faq_weight_stub_count', 0)
        diagnostic['faq_first_slot_repaired'] = enhancement_diagnostic.get('faq_first_slot_repaired', False)
        diagnostic['faq_repaired'] = enhancement_diagnostic.get('faq_repaired', False)
        diagnostic['faq_repair_actions'] = str(enhancement_diagnostic.get('faq_repair_actions', []))
        diagnostic['faq_candidates_total'] = enhancement_diagnostic.get('faq_candidates_total', 0)
        diagnostic['faq_selected_count'] = enhancement_diagnostic.get('faq_selected_count', 0)
        diagnostic['faq_topics_covered'] = enhancement_diagnostic.get('topics_covered', 0)
        
        # Note-buy диагностика
        diagnostic['note_buy_has_kupit_kupyty'] = enhancement_diagnostic.get('note_buy_has_kupit_kupyty', False)
        diagnostic['note_buy_declined'] = enhancement_diagnostic.get('note_buy_declined', False)
        diagnostic['note_buy_single_strong'] = enhancement_diagnostic.get('note_buy_single_strong', False)
        diagnostic['note_buy_range_from'] = enhancement_diagnostic.get('note_buy_range_from', '')
        diagnostic['note_buy_range_to'] = enhancement_diagnostic.get('note_buy_range_to', '')
        diagnostic['note_buy_first_char_lowered'] = enhancement_diagnostic.get('note_buy_first_char_lowered', False)
        diagnostic['note_buy_before'] = enhancement_diagnostic.get('note_buy_before', '')
        diagnostic['note_buy_after'] = enhancement_diagnostic.get('note_buy_after', '')
        
        # Склонение диагностика
        declension_debug = enhancement_diagnostic.get('declension_debug', {})
        diagnostic['declension_debug_first_adj'] = declension_debug.get('first_adj', '')
        diagnostic['declension_debug_first_noun'] = declension_debug.get('first_noun', '')
        diagnostic['declension_debug_rules_applied'] = str(declension_debug.get('rules_applied', []))
        
        # Lowercase диагностика
        lowercase_debug = enhancement_diagnostic.get('lowercase_debug', {})
        diagnostic['lowercase_debug_position'] = lowercase_debug.get('position', -1)
        diagnostic['lowercase_debug_original_char'] = lowercase_debug.get('original_char', '')
        diagnostic['lowercase_debug_lowercased_char'] = lowercase_debug.get('lowercased_char', '')
        
        return diagnostic
    
    def _extract_h2_from_html(self, html: str) -> str:
        """Извлекает h2 заголовок из HTML"""
        if not html:
            return ''
        
        import re
        h2_match = re.search(r'<h2[^>]*class="prod-title"[^>]*>(.*?)</h2>', html, re.DOTALL)
        if h2_match:
            return h2_match.group(1).strip()
        return ''
    
    def _determine_h2_source(self, h2: str, result: Dict[str, Any], locale: str) -> str:
        """Определяет источник h2 заголовка"""
        if not h2:
            return 'none'
        
        ru_snapshot = result.get('source_title_ru_snapshot', '')
        ua_snapshot = result.get('source_title_ua_snapshot', '')
        
        if h2 == ru_snapshot:
            return 'ru_snapshot'
        elif h2 == ua_snapshot:
            return 'ua_fallback'
        else:
            return 'generated'
    
    def _count_description_paragraphs(self, html: str) -> int:
        """Считает количество абзацев в описании"""
        if not html:
            return 0
        
        import re
        # Ищем абзацы в секции описания
        description_match = re.search(r'<h2[^>]*>Описание</h2>(.*?)(?=<h2|$)', html, re.DOTALL)
        if description_match:
            p_matches = re.findall(r'<p[^>]*>(.*?)</p>', description_match.group(1), re.DOTALL)
            return len([p for p in p_matches if p.strip()])
        return 0
    
    def _count_description_chars(self, html: str) -> int:
        """Считает количество символов в описании"""
        if not html:
            return 0
        
        import re
        # Ищем текст в секции описания
        description_match = re.search(r'<h2[^>]*>Описание</h2>(.*?)(?=<h2|$)', html, re.DOTALL)
        if description_match:
            # Убираем HTML теги и считаем символы
            text = re.sub(r'<[^>]+>', '', description_match.group(1))
            return len(text.strip())
        return 0
    
    def _detect_locale_mixing(self, html: str, locale: str) -> bool:
        """Детектирует смешение локалей в HTML"""
        if not html:
            return False
        
        if locale == 'ru':
            # Ищем UA-буквы с границами слов
            import re
            ua_letters_pattern = r'\b[іїєґІЇЄҐ]\w*\b'
            return bool(re.search(ua_letters_pattern, html))
        return False
    
    def _get_mixing_reason(self, html: str, locale: str) -> str:
        """Определяет причину смешения локалей"""
        if not html:
            return ''
        
        if locale == 'ru':
            import re
            if re.search(r'\b[іїєґІЇЄҐ]\w*\b', html):
                return 'ua_letters'
            elif re.search(r'\b(гарячий|обличчя|область застосування)\b', html, re.IGNORECASE):
                return 'ua_tokens'
        return ''
    
    def _has_ua_letters(self, html: str) -> bool:
        """Проверяет наличие UA-букв в HTML"""
        if not html:
            return False
        
        import re
        return bool(re.search(r'[іїєґІЇЄҐ]', html))
    
    def _extract_mixing_tokens(self, html: str, locale: str) -> str:
        """Извлекает токены смешения локалей"""
        if not html:
            return ''
        
        import re
        if locale == 'ru':
            ua_tokens = re.findall(r'\b[іїєґІЇЄҐ]\w*\b', html)
            return ', '.join(ua_tokens[:5])  # Первые 5 токенов
        return ''
    
    def _check_whitelist_hit(self, html: str, locale: str) -> bool:
        """Проверяет попадание в whitelist"""
        if not html:
            return False
        
        whitelist_words = ['классификация', 'класс', 'клас']
        for word in whitelist_words:
            if word.lower() in html.lower():
                return True
        return False
    
    def _extract_specs_from_html(self, html: str) -> List[Dict[str, str]]:
        """Извлекает характеристики из HTML"""
        if not html:
            return []
        
        import re
        specs = []
        specs_match = re.search(r'<ul class="specs">(.*?)</ul>', html, re.DOTALL)
        if specs_match:
            li_matches = re.findall(r'<li[^>]*>(.*?)</li>', specs_match.group(1), re.DOTALL)
            for li in li_matches:
                # Извлекаем name и value
                span_match = re.search(r'<span[^>]*class="spec-label"[^>]*>(.*?):</span>\s*(.*)', li, re.DOTALL)
                if span_match:
                    specs.append({
                        'name': span_match.group(1).strip(),
                        'value': span_match.group(2).strip()
                    })
        return specs
    
    def _get_dropped_conflicts(self, specs: List[Dict[str, str]], locale: str) -> str:
        """Получает список удаленных конфликтных ключей"""
        if not specs:
            return ''
        
        conflict_patterns = {
            'ru': ['гарячий', 'обличчя', 'область застосування'],
            'ua': ['горячий', 'лице', 'область применения']
        }
        
        patterns = conflict_patterns.get(locale, [])
        dropped = []
        for spec in specs:
            name = spec.get('name', '').lower()
            for pattern in patterns:
                if pattern in name:
                    dropped.append(spec.get('name', ''))
                    break
        
        return ', '.join(dropped)
    
    def _get_fixed_labels(self, specs: List[Dict[str, str]], locale: str) -> str:
        """Получает список исправленных лейблов"""
        # Это будет заполняться в repair_runner при применении нормализации
        return ''
    
    def _validate_faq_jsonld(self, html: str) -> bool:
        """Проверяет валидность FAQ JSON-LD"""
        if not html:
            return False
        
        import re
        script_match = re.search(r'<script[^>]*data-prorazko="faq"[^>]*>(.*?)</script>', html, re.DOTALL)
        if script_match:
            try:
                import json
                json.loads(script_match.group(1))
                return True
            except:
                return False
        return False
    
    def _get_note_buy_status(self, html: str) -> str:
        """Получает статус note-buy"""
        if not html:
            return 'missing'
        
        import re
        note_buy_match = re.search(r'<p class="note-buy">(.*?)</p>', html, re.DOTALL)
        if note_buy_match:
            content = note_buy_match.group(1).strip()
            if content and content != '<strong>купить </strong>' and content != '<strong>купити </strong>':
                return 'normalized'
            else:
                return 'original'
        return 'missing'
    
    def _has_product_photo(self, html: str) -> bool:
        """Проверяет наличие фото товара"""
        if not html:
            return False
        
        import re
        return bool(re.search(r'<img[^>]*src="[^"]*"[^>]*>', html))
    
    def _get_repair_scope(self, result: Dict[str, Any]) -> str:
        """Получает область ремонта"""
        flags = result.get('flags', [])
        if any('repair' in flag.lower() for flag in flags):
            return 'repair_applied'
        return 'main_flow'
    
    def _get_repair_actions(self, result: Dict[str, Any]) -> str:
        """Получает примененные действия ремонта"""
        flags = result.get('flags', [])
        repair_actions = [flag for flag in flags if 'repair' in flag.lower()]
        return '; '.join(repair_actions) if repair_actions else ''
    
    def _get_repair_failure_reason(self, result: Dict[str, Any]) -> str:
        """Получает причину неудачи ремонта"""
        flags = result.get('flags', [])
        failure_flags = [flag for flag in flags if 'failed' in flag.lower() or 'error' in flag.lower()]
        return '; '.join(failure_flags) if failure_flags else ''
    
    def _normalize_spaces_in_values(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализует пробелы в значениях, сохраняя исходные слова и язык"""
        normalized = result.copy()
        
        # Нормализуем пробелы в HTML контенте
        for locale in ['ru', 'ua']:
            html_key = f'{locale.upper()}_HTML'
            if html_key in normalized:
                html_content = normalized[html_key]
                if html_content:
                    # Нормализуем пробелы в значениях характеристик
                    normalized_html = self._normalize_html_spaces(html_content)
                    if normalized_html != html_content:
                        normalized[html_key] = normalized_html
                        logger.debug(f"🔧 Нормализованы пробелы в {html_key}")
        
        return normalized
    
    def _normalize_html_spaces(self, html_content: str) -> str:
        """Нормализует пробелы в HTML контенте для единообразия"""
        if not html_content:
            return html_content
        
        # Нормализуем пробелы в значениях характеристик
        def normalize_spec_value(match):
            name = match.group(1).strip()
            value = match.group(2).strip()
            
            # Единообразие пробелов в values: split/trim/join через «, »
            if ',' in value:
                tokens = [token.strip() for token in value.split(',') if token.strip()]
                value = ', '.join(tokens)  # Стандартный разделитель с пробелом
            
            # Убираем лишние пробелы в name
            name = ' '.join(name.split())
            
            return f'<li><span class="spec-label">{name}:</span> {value}</li>'
        
        # Паттерн для характеристик: <li><span class="spec-label">Name:</span> Value</li>
        pattern = r'<li><span class="spec-label">([^:]+):</span>\s*([^<]+)</li>'
        normalized = re.sub(pattern, normalize_spec_value, html_content, flags=re.DOTALL)
        
        return normalized
    
    def _create_row_data(self, result: Dict[str, Any], ru_valid: bool, ua_valid: bool) -> Dict[str, Any]:
        """Создает данные строки для упорядоченного экспорта"""
        # Определяем проблемы
        ru_issues = []
        ua_issues = []
        
        flags = result.get('flags', [])
        for flag in flags:
            if 'ru' in flag.lower() and 'validation' in flag.lower():
                ru_issues.append(flag)
            elif 'ua' in flag.lower() and 'validation' in flag.lower():
                ua_issues.append(flag)
        
        # АВТОМАТИЧЕСКИЕ ПРОВЕРКИ И МЕТРИКИ
        self._update_specs_metrics(result)
        self._update_note_buy_metrics(result)
        self._update_title_metrics(result)
        
        # Создаем хеш исходного контента для отслеживания
        source_hash = self._calculate_source_hash(result)
        
        return {
            'URL': result.get('url', ''),
            'RU_HTML': result.get('RU_HTML', ''),
            'UA_HTML': result.get('UA_HTML', ''),
            'RU_Valid': ru_valid,
            'UA_Valid': ua_valid,
            'RU_Issues': '; '.join(ru_issues) if ru_issues else '',
            'UA_Issues': '; '.join(ua_issues) if ua_issues else '',
            'Source_Hash': source_hash,
            'Preserved_Tokens': self._extract_preserved_tokens(result)
        }
    
    def _calculate_source_hash(self, result: Dict[str, Any]) -> str:
        """Вычисляет хеш исходного контента для отслеживания"""
        import hashlib
        content = f"{result.get('url', '')}{result.get('RU_HTML', '')}{result.get('UA_HTML', '')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
    
    def _extract_preserved_tokens(self, result: Dict[str, Any]) -> str:
        """Извлекает сохраненные токены для мониторинга"""
        tokens = []
        for locale in ['ru', 'ua']:
            html_key = f'{locale.upper()}_HTML'
            html_content = result.get(html_key, '')
            if html_content:
                # Извлекаем уникальные слова из HTML
                words = re.findall(r'\b[а-яёіїєґ]+\b', html_content.lower())
                tokens.extend(set(words))
        return ', '.join(sorted(set(tokens))[:10])  # Первые 10 уникальных слов
    
    def _update_specs_metrics(self, result: Dict[str, Any]) -> None:
        """Обновляет метрики для автоматических проверок характеристик"""
        for locale in ['ru', 'ua']:
            html_key = f'{locale.upper()}_HTML'
            html_content = result.get(html_key, '')
            
            if html_content:
                # Подсчитываем количество характеристик
                specs_count = self._count_specs_in_html(html_content)
                self.total_specs_processed += specs_count
                
                # Проверяем инвариант specs_count ∈ [3,8]
                if not (3 <= specs_count <= 8):
                    logger.warning(f"❌ Нарушение инварианта specs_count: {specs_count} не в диапазоне [3,8] для {locale}")
                else:
                    logger.debug(f"✅ Инвариант specs_count соблюден: {specs_count} ∈ [3,8] для {locale}")
                
                # Проверяем приоритет при усечении до 8
                if specs_count == 8:
                    self._check_specs_priority(html_content, locale)
                
                # Отслеживаем усеченные карточки (если было 8, вероятно усечено)
                if specs_count == 8:
                    self.specs_clamped_count += 1

    def _update_note_buy_metrics(self, result: Dict[str, Any]) -> None:
        """Обновляет метрики для note-buy"""
        flags = result.get('flags', [])
        
        for flag in flags:
            # Разбиваем sanitization_info на части
            sanitization_parts = flag.split(';') if ';' in flag else [flag]
            
            for part in sanitization_parts:
                part = part.strip()
                
                # Проверяем флаги санитизации note-buy
                if 'note_buy_sanitized=true' in part:
                    self.note_buy_sanitized_count += 1
                
                # Обновляем статистику источников
                if 'note_buy_source=original' in part:
                    self.note_buy_source_stats['original'] += 1
                elif 'note_buy_source=safe_constructor' in part:
                    self.note_buy_source_stats['safe_constructor'] += 1
                elif 'note_buy_source=failed_sanitization' in part:
                    self.note_buy_source_stats['failed_sanitization'] += 1

    def _update_title_metrics(self, result: Dict[str, Any]) -> None:
        """Обновляет метрики для заголовков"""
        flags = result.get('flags', [])
        
        for flag in flags:
            # Разбиваем sanitization_info на части
            sanitization_parts = flag.split(';') if ';' in flag else [flag]
            
            for part in sanitization_parts:
                part = part.strip()
                
                # Проверяем флаги санитизации заголовков
                if 'title_sanitized=true' in part:
                    self.title_sanitized_count += 1
                
                # Обновляем статистику источников
                if 'title_source=original' in part:
                    self.title_source_stats['original'] += 1
                elif 'title_source=safe_constructor' in part:
                    self.title_source_stats['safe_constructor'] += 1
                elif 'title_source=failed_sanitization' in part:
                    self.title_source_stats['failed_sanitization'] += 1
    
    def _count_specs_in_html(self, html_content: str) -> int:
        """Подсчитывает количество характеристик в HTML"""
        import re
        specs_match = re.search(r'<ul class="specs">(.*?)</ul>', html_content, re.DOTALL)
        if specs_match:
            return len(re.findall(r'<li>', specs_match.group(1)))
        return 0
    
    def _check_specs_priority(self, html_content: str, locale: str) -> None:
        """Проверяет приоритет характеристик при усечении до 8"""
        import re
        
        # Извлекаем названия характеристик
        specs_match = re.search(r'<ul class="specs">(.*?)</ul>', html_content, re.DOTALL)
        if not specs_match:
            return
        
        spec_names = []
        li_matches = re.findall(r'<li>.*?<span class="spec-label">([^:]+):</span>', specs_match.group(1))
        
        # Приоритетные ключи
        priority_keys = [
            'бренд', 'brand', 'тип', 'type', 'объем', 'об\'єм', 'вес', 'вага', 'материал', 'матеріал',
            'температура', 'зоны', 'зони', 'область', 'серия', 'серія', 'класс', 'клас', 'цвет', 'колір'
        ]
        
        # Проверяем наличие приоритетных ключей
        found_priorities = []
        for name in li_matches:
            name_lower = name.lower().strip()
            for priority in priority_keys:
                if priority in name_lower:
                    found_priorities.append(name)
                    break
        
        # Если найдено меньше 4 приоритетных ключей, считаем нарушением
        if len(found_priorities) < 4:
            self.specs_priority_violations += 1
            logger.warning(f"⚠️ Низкий приоритет характеристик для {locale}: найдено {len(found_priorities)} из {len(priority_keys)} приоритетных ключей")
    
    def _get_available_filename(self, base_filename: str) -> str:
        """Находит доступное имя файла, добавляя номер если файл заблокирован"""
        if not os.path.exists(base_filename):
            return base_filename
        
        # Пробуем записать в файл, чтобы проверить блокировку
        try:
            with open(base_filename, 'a'):
                pass
            return base_filename
        except (PermissionError, OSError):
            # Файл заблокирован - ищем доступное имя с номером
            pass
        
        # Извлекаем имя и расширение
        name, ext = os.path.splitext(base_filename)
        counter = 2
        
        while True:
            new_filename = f"{name}_{counter}{ext}"
            if not os.path.exists(new_filename):
                return new_filename
            
            # Проверяем, не заблокирован ли файл с номером
            try:
                with open(new_filename, 'a'):
                    pass
                return new_filename
            except (PermissionError, OSError):
                counter += 1
                continue
    
    def write_final_files(self) -> Dict[str, Any]:
        """Записывает финальные файлы с проверкой порядка"""
        stats = {
            'valid_results': len(self.ordered_buffer),
            'repair_items': len(self.repair_report),
            'total_processed': len(self.ordered_buffer) + len(self.repair_report),
            'input_count': self.input_count,
            'output_rows': len(self.ordered_buffer),
            'paired_always': self.mode == "paired_always",
            'order_mismatch_count': 0
        }
        
        # Записываем основной файл с упорядоченными результатами
        if self.ordered_buffer:
            actual_output_file = self._get_available_filename(self.output_file)
            try:
                # Создаем упорядоченный DataFrame
                ordered_data = []
                for i in range(1, self.input_count + 1):
                    if i in self.ordered_buffer:
                        row_data = self.ordered_buffer[i].copy()
                        row_data['InputIndex'] = i
                        # Добавляем Export_Mode
                        export_mode = self._determine_export_mode(row_data)
                        row_data['Export_Mode'] = export_mode
                        ordered_data.append(row_data)
                    else:
                        # Создаем пустую строку для пропущенных индексов
                        empty_row = {
                            'URL': self.input_urls[i-1] if i <= len(self.input_urls) else f'missing_{i}',
                            'RU_HTML': '',
                            'UA_HTML': '',
                            'RU_Valid': False,
                            'UA_Valid': False,
                            'RU_Issues': 'Missing data',
                            'UA_Issues': 'Missing data',
                            'Source_Hash': '',
                            'Preserved_Tokens': '',
                            'Export_Mode': 'failed',
                            'InputIndex': i
                        }
                        ordered_data.append(empty_row)
                
                df = pd.DataFrame(ordered_data)
                df.to_excel(actual_output_file, index=False)
                
                # Проверяем порядок после записи
                order_mismatch_count = self._verify_order(df)
                stats['order_mismatch_count'] = order_mismatch_count
                
                if order_mismatch_count > 0:
                    logger.critical(f"❌ Нарушение порядка: {order_mismatch_count} несоответствий")
                    # Переписываем файл в правильном порядке
                    self._rewrite_with_correct_order(actual_output_file, df)
                else:
                    logger.info(f"✅ Основной файл записан: {actual_output_file} ({len(ordered_data)} строк)")
                
                stats['main_file'] = actual_output_file
            except Exception as e:
                logger.error(f"❌ Ошибка записи основного файла: {e}")
                stats['main_file_error'] = str(e)
        else:
            logger.warning("⚠️ Нет результатов для записи")
            stats['main_file'] = None
        
        # Записываем repair_report
        if self.repair_report:
            try:
                repair_file = f"repair_report_{int(datetime.now().timestamp())}.xlsx"
                df_repair = pd.DataFrame(self.repair_report)
                df_repair.to_excel(repair_file, index=False)
                logger.info(f"📋 Repair report записан: {repair_file} ({len(self.repair_report)} строк)")
                stats['repair_file'] = repair_file
            except Exception as e:
                logger.error(f"❌ Ошибка записи repair_report: {e}")
                stats['repair_file_error'] = str(e)
        else:
            logger.info("✅ Нет проблемных результатов для repair_report")
            stats['repair_file'] = None
        
        return stats
    
    def update_repair_metrics(self, repair_stats: Dict[str, Any]) -> None:
        """Обновляет метрики ремонта"""
        self.repair_enqueued_count = repair_stats.get('repair_enqueued_count', 0)
        self.repair_completed_count = repair_stats.get('repair_completed_count', 0)
        self.repair_failed_count = repair_stats.get('repair_failed_count', 0)
        self.sanity_fix_applied_count = repair_stats.get('sanity_fix_applied_count', 0)
        self.repair_reason_stats = repair_stats.get('repair_reason_stats', {})
        
        logger.info(f"📊 Метрики ремонта обновлены: {self.repair_completed_count} завершено, {self.repair_failed_count} неудачно")
    
    def upsert_repair_result(self, input_index: int, repaired_result: Dict[str, Any]) -> None:
        """Обновляет результат после ремонта"""
        if input_index in self.ordered_buffer:
            # Обновляем существующий результат
            original_row = self.ordered_buffer[input_index]
            
            # Обновляем только проблемную локаль
            failing_locale = repaired_result.get('failing_locale')
            if failing_locale == 'ru':
                original_row['RU_HTML'] = repaired_result.get('repaired_html', '')
                original_row['RU_Valid'] = True
                original_row['RU_Issues'] = repaired_result.get('issues', '')
            elif failing_locale == 'ua':
                original_row['UA_HTML'] = repaired_result.get('repaired_html', '')
                original_row['UA_Valid'] = True
                original_row['UA_Issues'] = repaired_result.get('issues', '')
            
            # Добавляем информацию о ремонте
            original_row['Repair_Applied'] = True
            original_row['Repair_Reason'] = repaired_result.get('repair_reason', '')
            
            logger.info(f"✅ Результат обновлен после ремонта: индекс {input_index}, локаль {failing_locale}")
        else:
            logger.warning(f"⚠️ Не найден результат для обновления: индекс {input_index}")
    
    def _verify_order(self, df: pd.DataFrame) -> int:
        """Проверяет порядок URL в DataFrame"""
        mismatches = 0
        for i, row in df.iterrows():
            expected_url = self.input_urls[i] if i < len(self.input_urls) else f'missing_{i+1}'
            actual_url = row.get('URL', '')
            if actual_url != expected_url:
                logger.critical(f"❌ Несоответствие порядка в строке {i+1}: ожидался '{expected_url}', получен '{actual_url}'")
                mismatches += 1
        return mismatches
    
    def _rewrite_with_correct_order(self, filename: str, df: pd.DataFrame) -> None:
        """Переписывает файл в правильном порядке"""
        try:
            # Создаем правильный порядок
            correct_data = []
            for i in range(len(self.input_urls)):
                # Ищем строку с нужным URL
                matching_rows = df[df['URL'] == self.input_urls[i]]
                if not matching_rows.empty:
                    correct_data.append(matching_rows.iloc[0].to_dict())
                else:
                    # Создаем пустую строку
                    empty_row = {
                        'URL': self.input_urls[i],
                        'RU_HTML': '',
                        'UA_HTML': '',
                        'RU_Valid': False,
                        'UA_Valid': False,
                        'RU_Issues': 'Missing data',
                        'UA_Issues': 'Missing data',
                        'Source_Hash': '',
                        'Preserved_Tokens': '',
                        'InputIndex': i + 1
                    }
                    correct_data.append(empty_row)
            
            # Переписываем файл
            correct_df = pd.DataFrame(correct_data)
            correct_df.to_excel(filename, index=False)
            logger.info(f"✅ Файл переписан в правильном порядке: {filename}")
        except Exception as e:
            logger.error(f"❌ Ошибка перезаписи файла: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику экспорта"""
        total_locales = len(self.ordered_buffer) * 2  # RU + UA для каждой строки
        specs_clamped_rate = (self.specs_clamped_count / total_locales * 100) if total_locales > 0 else 0
        note_buy_sanitized_rate = (self.note_buy_sanitized_count / total_locales * 100) if total_locales > 0 else 0
        title_sanitized_rate = (self.title_sanitized_count / total_locales * 100) if total_locales > 0 else 0
        
        return {
            'valid_results': len(self.ordered_buffer),
            'repair_items': len(self.repair_report),
            'total_processed': len(self.ordered_buffer) + len(self.repair_report),
            'input_count': self.input_count,
            'output_rows': len(self.ordered_buffer),
            'paired_always': self.mode == "paired_always",
            'success_rate': len(self.ordered_buffer) / self.input_count if self.input_count > 0 else 0,
            # Новые метрики для автоматических проверок
            'specs_clamped_count': self.specs_clamped_count,
            'specs_clamped_rate': f"{specs_clamped_rate:.1f}%",
            'total_specs_processed': self.total_specs_processed,
            'specs_priority_violations': self.specs_priority_violations,
            'avg_specs_per_locale': self.total_specs_processed / total_locales if total_locales > 0 else 0,
            # Метрики для note-buy
            'note_buy_sanitized_count': self.note_buy_sanitized_count,
            'note_buy_sanitized_rate': f"{note_buy_sanitized_rate:.1f}%",
            'note_buy_source_stats': self.note_buy_source_stats,
            # Метрики для заголовков
            'title_sanitized_count': self.title_sanitized_count,
            'title_sanitized_rate': f"{title_sanitized_rate:.1f}%",
            'title_source_stats': self.title_source_stats,
            # Метрики для системы ремонта
            'repair_enqueued_count': self.repair_enqueued_count,
            'repair_completed_count': self.repair_completed_count,
            'repair_failed_count': self.repair_failed_count,
            'sanity_fix_applied_count': self.sanity_fix_applied_count,
            'repair_reason_stats': self.repair_reason_stats
        }
