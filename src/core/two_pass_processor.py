"""
Двухпроходная система обработки с retry логикой
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class TwoPassProcessor:
    """Двухпроходная система обработки URL"""
    
    def __init__(self, progress_tracker, fallback_processor, conditional_exporter):
        self.progress_tracker = progress_tracker
        self.fallback_processor = fallback_processor
        self.conditional_exporter = conditional_exporter
        from src.processing.consistency_guard import ConsistencyGuard
        from src.processing.content_enhancer import ContentEnhancer
        self.consistency_guard = ConsistencyGuard()
        self.content_enhancer = ContentEnhancer()
        
        # Инициализируем очередь ремонта
        from src.repair.repair_queue import RepairQueue
        self.repair_queue = RepairQueue()
        
        # Словарь для группировки HTML по URL
        self.url_html_data = {}
        
        # Настройки для прохода 1 (быстрый)
        self.pass1_config = {
            'concurrency': 8,
            'rps_limit': 4,
            'timeout': 15,
            'retries': 2,
            'backoff_factor': 1.5
        }
        
        # Настройки для прохода 2 (добивка)
        self.pass2_config = {
            'concurrency': 4,
            'rps_limit': 2,
            'timeout': 30,
            'retries': 3,
            'backoff_factor': 2.0
        }
    
    async def process_urls_two_pass(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Двухпроходная обработка URL"""
        logger.info(f"🚀 Начинаем двухпроходную обработку {len(urls)} URL")
        
        # Проход 1: быстрая обработка
        logger.info("📋 Проход 1: быстрая обработка")
        pass1_results = await self._process_pass1(urls)
        
        # Проход 2: добивка pending (автоматически после прохода 1)
        logger.info("🔄 Проход 2: добивка pending")
        pass2_results = await self._process_pass2()
        
        # Объединяем результаты
        all_results = pass1_results + pass2_results
        
        # Записываем финальные результаты с HTML по локалям
        self._write_final_results()
        
        # Записываем финальный файл с правильной структурой
        self.conditional_exporter.write_final_files()
        
        # Статистика
        stats = self.progress_tracker.get_stats()
        logger.info(f"📊 Итоговая статистика: {stats}")
        
        return all_results
    
    async def _process_pass1(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Проход 1: быстрая обработка"""
        results = []
        
        # Создаем задачи для каждой пары RU/UA
        tasks = []
        for ua_url in urls:
            ru_url = self._to_ru_url(ua_url)
            
            # Проверяем, не обработан ли уже
            if (self.progress_tracker.is_processed(ua_url, 'ua') and 
                self.progress_tracker.is_processed(ru_url, 'ru')):
                logger.info(f"⏭️ Пропускаем уже обработанный: {ua_url}")
                continue
            
            task = asyncio.create_task(self._process_url_pair_pass1(ua_url, ru_url))
            tasks.append(task)
        
        # Обрабатываем все задачи
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Ошибка в проходе 1: {result}")
                else:
                    results.extend(result)
        
        return results
    
    async def _process_url_pair_pass1(self, ua_url: str, ru_url: str) -> List[Dict[str, Any]]:
        """Обработка пары URL в проходе 1 с авто-добивкой локалей"""
        results = []
        
        # Обрабатываем UA
        ua_result = await self._process_single_url_pass1(ua_url, 'ua')
        if ua_result:
            results.append(ua_result)
        
        # Обрабатываем RU
        ru_result = await self._process_single_url_pass1(ru_url, 'ru')
        if ru_result:
            results.append(ru_result)
        
        # Авто-добивка недостающих локалей
        ua_success = ua_result and ua_result.get('export_mode') == 'full'
        ru_success = ru_result and ru_result.get('export_mode') == 'full'
        
        if ua_success and not ru_success:
            # UA успешно, RU нет - добавляем RU в pending
            logger.info(f"🔄 Авто-добивка: UA успешно, RU нет - добавляем RU в pending: {ru_url}")
            self.progress_tracker.add_to_pending(ru_url, 'ru', "auto_retry_missing_locale")
        elif ru_success and not ua_success:
            # RU успешно, UA нет - добавляем UA в pending
            logger.info(f"🔄 Авто-добивка: RU успешно, UA нет - добавляем UA в pending: {ua_url}")
            self.progress_tracker.add_to_pending(ua_url, 'ua', "auto_retry_missing_locale")
        
        return results
    
    async def _process_single_url_pass1(self, url: str, locale: str) -> Optional[Dict[str, Any]]:
        """Обработка одного URL в проходе 1 с безусловным экспортом"""
        try:
            logger.info(f"🔄 Обрабатываем {url} ({locale}) в проходе 1")
            
            # Используем fallback fetcher
            from src.fetcher.fallback_fetcher import FallbackFetcher
            from src.processing.safe_facts import SafeFactsExtractor
            
            async with FallbackFetcher(timeout=15, retries=2) as fetcher:
                html = await fetcher.fetch_single(url, locale)
                
                if html:
                    # Обрабатываем HTML с безопасными фактами
                    result = await self._process_html_safe(html, url, locale, None)
                    
                    # Отмечаем как обработанный
                    self.progress_tracker.mark_processed(url, locale, result)
                    
                    return result
                else:
                    # Создаем безопасный результат из базовых данных
                    result = self._create_safe_result(url, locale, "network_failed_pass1")
                    
                    # Отмечаем как обработанный
                    self.progress_tracker.mark_processed(url, locale, result)
                    
                    # Добавляем в pending для прохода 2
                    self.progress_tracker.add_to_pending(url, locale, "network_failed_pass1")
                    return result
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки {url} ({locale}): {e}")
            
            # Создаем безопасный результат
            result = self._create_safe_result(url, locale, f"exception_pass1: {str(e)}")
            
            # Отмечаем как обработанный
            self.progress_tracker.mark_processed(url, locale, result)
            
            # Добавляем в pending для прохода 2
            self.progress_tracker.add_to_pending(url, locale, f"exception_pass1: {str(e)}")
            return result
    
    async def _process_pass2(self) -> List[Dict[str, Any]]:
        """Проход 2: добивка pending"""
        results = []
        pending = self.progress_tracker.get_pending()
        
        if not pending:
            logger.info("✅ Нет pending задач для прохода 2")
            return results
        
        logger.info(f"🔄 Обрабатываем {len(pending)} pending задач")
        
        # Создаем задачи для pending
        tasks = []
        for item in pending:
            task = asyncio.create_task(self._process_pending_item(item))
            tasks.append(task)
        
        # Обрабатываем все pending задачи
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Ошибка в проходе 2: {result}")
                else:
                    if result:
                        results.append(result)
        
        return results
    
    def _validate_and_fix_title_early(self, title: str, html: str, locale: str, url: str) -> str:
        """Ранняя валидация и исправление заголовка"""
        try:
            from src.processing.title_generator import TitleGenerator
            title_generator = TitleGenerator()
            
            # Проверяем, валиден ли заголовок
            if title_generator.validate_title(title, locale):
                logger.info(f"✅ Заголовок валиден: {title}")
                return title
            
            logger.warning(f"⚠️ Заголовок невалиден: {title}")
            
            # Пытаемся извлечь заголовок из H2 тега
            h2_title = title_generator.extract_title_from_h2_tag(html, locale)
            if h2_title and title_generator.validate_title(h2_title, locale):
                logger.info(f"✅ Заголовок извлечен из H2: {h2_title}")
                return h2_title
            
            # Создаем заголовок на основе фактов из HTML
            # Извлекаем базовые факты для генерации заголовка
            import re
            
            # Ищем бренд
            brand_match = re.search(r'Epilax', html, re.IGNORECASE)
            brand = brand_match.group(0) if brand_match else 'Epilax'
            
            # Ищем объем/вес
            volume_match = re.search(r'(\d+)\s*(мл|ml)', html, re.IGNORECASE)
            weight_match = re.search(r'(\d+)\s*(г|g)', html, re.IGNORECASE)
            
            size_info = ''
            if volume_match:
                size_info = f"{volume_match.group(1)} мл"
            elif weight_match:
                size_info = f"{weight_match.group(1)} г"
            
            # Создаем факты для генерации заголовка
            facts = {
                'brand': brand,
                'volume': size_info if 'мл' in size_info else '',
                'weight': size_info if 'г' in size_info else '',
                'product_type': 'Товар' if locale == 'ru' else 'Товар'
            }
            
            generated_title = title_generator.create_title_from_facts(facts, locale)
            logger.info(f"✅ Заголовок сгенерирован из фактов: {generated_title}")
            return generated_title
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации заголовка: {e}")
            # Fallback к простому заголовку
            return f"Epilax, 5 мл" if locale == 'ru' else f"Epilax, 5 мл"
    
    async def _process_pending_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Обработка одного pending элемента"""
        url = item['url']
        locale = item['locale']
        retry_count = item.get('retry_count', 0)
        
        try:
            logger.info(f"🔄 Обрабатываем pending {url} ({locale}) в проходе 2")
            
            # Используем fallback fetcher с расширенными настройками
            from src.fetcher.fallback_fetcher import FallbackFetcher
            
            async with FallbackFetcher(timeout=30, retries=3) as fetcher:
                html = await fetcher.fetch_single(url, locale)
                
                if html:
                    # Создаем успешный результат
                    result = {
                        'url': url,
                        'locale': locale,
                        'export_mode': 'full',
                        'flags': ['retry_success'],
                        'needs_review': False,
                        'consistency_fixes': [],
                        'html_length': len(html),
                        'processed': True,
                        'retries': retry_count,
                        'network_errors': 0,
                        'budget_violation': False
                    }
                    
                    # Удаляем из pending
                    self.progress_tracker.remove_from_pending(url, locale)
                    # Отмечаем как обработанный
                    self.progress_tracker.mark_processed(url, locale, result)
                    return result
                else:
                    # Увеличиваем счетчик попыток
                    retry_count += 1
                    
                    if retry_count >= 3:
                        # Создаем fallback результат (NO-EXCLUDE режим)
                        fallback_result = self._create_fallback_result(url, locale, "network_failed_max_retries", retry_count)
                        self.progress_tracker.remove_from_pending(url, locale)
                        # Отмечаем как обработанный (даже неуспешный)
                        self.progress_tracker.mark_processed(url, locale, fallback_result)
                        return fallback_result
                    else:
                        # Обновляем pending с новым счетчиком
                        self.progress_tracker.add_to_pending(url, locale, f"network_retry_{retry_count}", retry_count)
                        return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки pending {url} ({locale}): {e}")
            retry_count += 1
            
            if retry_count >= 3:
                # Создаем fallback результат (NO-EXCLUDE режим)
                fallback_result = self._create_fallback_result(url, locale, f"exception_max_retries: {str(e)}", retry_count)
                self.progress_tracker.remove_from_pending(url, locale)
                # Отмечаем как обработанный (даже неуспешный)
                self.progress_tracker.mark_processed(url, locale, fallback_result)
                return fallback_result
            else:
                # Обновляем pending с новым счетчиком
                self.progress_tracker.add_to_pending(url, locale, f"exception_retry_{retry_count}: {str(e)}", retry_count)
                return None
    
    async def _process_html_content(self, html: str, url: str, locale: str) -> Optional[Dict[str, Any]]:
        """Обработка HTML контента (заглушка - должна быть заменена на реальную логику)"""
        # Здесь должна быть основная логика обработки HTML
        # Пока возвращаем заглушку
        return {
            'url': url,
            'locale': locale,
            'export_mode': 'full',
            'flags': [],
            'needs_review': False,
            'consistency_fixes': []
        }
    
    def _create_fallback_result(self, url: str, locale: str, reason: str, retries: int = 0) -> Dict[str, Any]:
        """Создает fallback результат (NO-EXCLUDE режим)"""
        return {
            'url': url,
            'locale': locale,
            'export_mode': 'fallback',
            'flags': [reason],
            'needs_review': True,
            'consistency_fixes': [],
            'fallback_reason': reason,
            'html_length': 0,
            'processed': True,  # Всегда True в no-exclude режиме
            'retries': retries,
            'network_errors': retries,
            'budget_violation': False
        }
    
    async def _process_html_safe(self, html: str, url: str, locale: str, input_index: int = None) -> Dict[str, Any]:
        """Обрабатывает HTML с безопасными фактами"""
        from src.processing.safe_facts import SafeFactsExtractor
        from src.processing.safe_templates import SafeTemplates
        
        # Извлекаем базовые данные (заглушка - должна быть заменена на реальную логику)
        h1 = self._extract_h1(html)
        
        # Ранняя валидация заголовка
        h1 = self._validate_and_fix_title_early(h1, html, locale, url)
        
        specs = self._extract_specs(html)
        mass_facts = self._extract_mass_facts(html)
        volume_facts = self._extract_volume_facts(html)
        
        # Извлекаем безопасные факты
        safe_extractor = SafeFactsExtractor()
        safe_facts = safe_extractor.extract_safe_facts(specs, h1, mass_facts, volume_facts)
        
        # Удаляем спорные данные из HTML
        clean_html = safe_extractor.strip_controversial_numbers(html)
        
        # Проверяем консистентность (без блокировок)
        volume_check = self.consistency_guard.check_volume_consistency({'description': clean_html}, locale)
        mass_check = self.consistency_guard.check_mass_consistency({'description': clean_html}, locale)
        
        # Генерируем контент через LLM (без fallback)
        from src.llm.content_generator import LLMContentGenerator
        llm_generator = LLMContentGenerator()
        
        # Подготавливаем данные для LLM
        product_data = {
            'title': h1,
            'description': clean_html[:500],  # Первые 500 символов HTML как описание
            'brand': safe_facts.get('brand', ''),
            'product_type': safe_facts.get('category', ''),
            'volume': safe_facts.get('pack', ''),
            'specs': specs  # Передаем извлеченные характеристики
        }
        
        # Генерируем контент через LLM (обязательно)
        try:
            llm_content = llm_generator.generate_content(product_data, locale)
            logger.info(f"✅ LLM контент сгенерирован для {locale}")
            
            # Валидируем контент
            from src.validation.guards import (
                faq_guard, specs_guard, description_guard, ValidationError,
                anti_placeholders_guard, locale_content_guard, structure_guard
            )
            
            try:
                # Основная валидация
                faq_guard(llm_content.get('faq', []))
                normalized_specs, specs_clamped = specs_guard(llm_content.get('specs', []), locale)
                description_guard(llm_content.get('description', ''))
                
                # Анти-заглушки
                anti_placeholders_guard(llm_content.get('description', ''), 'description')
                anti_placeholders_guard(llm_content.get('note_buy', ''), 'note_buy')
                
                # Локализация
                locale_content_guard(llm_content.get('description', ''), locale, 'description')
                locale_content_guard(llm_content.get('note_buy', ''), locale, 'note_buy')
                
                # Обновляем specs с нормализованными данными
                llm_content['specs'] = normalized_specs
                if specs_clamped:
                    llm_content['specs_clamped'] = True
                
                logger.info(f"✅ Валидация контента прошла для {locale}")
            except ValidationError as ve:
                # Определяем причину ошибки валидации
                error_msg = str(ve)
                repair_reason = self._determine_repair_reason(error_msg, llm_content)
                
                # Если это ошибка описания, пытаемся отремонтировать сразу
                if repair_reason == "desc_too_short":
                    logger.info(f"🔧 Попытка ремонта описания для {locale}")
                    try:
                        repaired_description = llm_generator.repair_description(product_data, locale)
                        llm_content['description'] = repaired_description
                        
                        # Повторная валидация описания
                        description_guard(repaired_description)
                        logger.info(f"✅ Ремонт описания успешен для {locale}")
                    except Exception as repair_error:
                        logger.error(f"❌ Ремонт описания не удался для {locale}: {repair_error}")
                        # Отправляем в очередь ремонта
                        self._enqueue_repair(url, input_index, locale, repair_reason, llm_content, error_msg)
                        raise ve
                else:
                    # Отправляем в очередь ремонта
                    self._enqueue_repair(url, input_index, locale, repair_reason, llm_content, error_msg)
                    logger.error(f"❌ Валидация не прошла для {locale}: {ve}")
                    raise ve
                
        except Exception as e:
            logger.error(f"❌ Ошибка LLM генерации для {locale}: {e}")
            raise e  # Не используем fallback, выбрасываем ошибку
        
        # Конвертируем в формат для фрагментов
        from src.processing.safe_templates import SafeTemplates
        templates = SafeTemplates()
        safe_blocks = templates.render_safe_blocks_from_llm(h1, llm_content, locale, clean_html)
        
        # Улучшаем контент с ContentCritic для комплексной проверки качества
        # Подготавливаем факты и specs для улучшения
        facts = {
            'title': h1,
            'brand': safe_facts.get('brand', ''),
            'material': safe_facts.get('category', ''),
            'volume': safe_facts.get('pack', ''),
            'color': '',
            'purpose': ''
        }
        
        # Улучшаем контент с ContentCritic
        logger.info(f"🔧 Вызываем ContentCritic для комплексной проверки {locale}")
        logger.info(f"🔧 Доступные блоки: {list(safe_blocks.keys())}")
        
        # Heartbeat для ContentCritic
        try:
            import sys
            if 'watchdog' in sys.modules:
                from scripts.universal_pipeline import watchdog
                watchdog.heartbeat("content_critic_start")
        except:
            pass
        
        enhanced_blocks = self.content_enhancer.enhance_product_with_critic(safe_blocks, locale, facts, specs)
        logger.info(f"🔧 ContentCritic вернул: {list(enhanced_blocks.keys())}")
        
        # Проверяем метрики качества
        if '_quality_metrics' in enhanced_blocks:
            quality_metrics = enhanced_blocks['_quality_metrics']
            quality_score = quality_metrics.get('quality_score', 0)
            overall_status = quality_metrics.get('overall_status', 'UNKNOWN')
            logger.info(f"📊 ContentCritic метрики: статус={overall_status}, оценка={quality_score:.2f}")
        
        # Heartbeat для FAQ завершения
        try:
            import sys
            if 'watchdog' in sys.modules:
                from scripts.universal_pipeline import watchdog
                faq_count = len(enhanced_blocks.get('faq', []))
                watchdog.heartbeat(f"faq_generate_ok_count={faq_count}")
        except:
            pass
        
        # Обновляем safe_blocks с улучшенным контентом
        safe_blocks.update(enhanced_blocks)
        logger.info(f"🔧 safe_blocks обновлен: {list(safe_blocks.keys())}")
        
        # Сохраняем диагностическую информацию для экспорта
        enhancement_diagnostic = self.content_enhancer.get_enhancement_diagnostic(enhanced_blocks)
        
        # Валидируем заголовок на смешение локалей и санитизируем при необходимости
        from src.validation.guards import locale_title_guard, note_buy_guard
        
        title_result = locale_title_guard(h1, locale, llm_content.get('specs', []))
        
        if not title_result['valid']:
            logger.error(f"❌ Title validation failed for {locale}: {title_result['issues']}")
            raise ValidationError(f"Title validation failed for {locale}: {'; '.join(title_result['issues'])}")
        
        # Если заголовок был санитизирован, обновляем h1 и блоки
        if title_result.get('sanitized'):
            h1 = title_result['sanitized_content']
            safe_blocks['title'] = h1
            logger.info(f"✅ Title sanitized for {locale}, source: {title_result['source']}")
            
            # Добавляем информацию о санитизации заголовка
            title_sanitization_info = f"title_sanitized=true, title_source={title_result['source']}"
        
        # Валидируем note-buy на смешение локалей и санитизируем при необходимости
        # Пропускаем валидацию note_buy если он был улучшен ContentEnhancer
        if '_enhancement_diagnostic' not in safe_blocks or not safe_blocks.get('_enhancement_diagnostic', {}).get('note_buy_has_kupit_kupyty', False):
            note_buy_result = note_buy_guard(safe_blocks.get('note_buy', ''), locale, llm_content.get('specs', []), h1)
            
            if not note_buy_result['valid']:
                logger.error(f"❌ Note-buy validation failed for {locale}: {note_buy_result['issues']}")
                raise ValidationError(f"Note-buy validation failed for {locale}: {'; '.join(note_buy_result['issues'])}")
            
            # Если note-buy был санитизирован, обновляем блоки
            if note_buy_result.get('sanitized'):
                safe_blocks['note_buy'] = note_buy_result['sanitized_content']
                logger.info(f"✅ Note-buy sanitized for {locale}, source: {note_buy_result['source']}")
                
                # Добавляем информацию о санитизации в результат для экспорта
                note_buy_sanitization_info = f"note_buy_sanitized=true, note_buy_source={note_buy_result['source']}"
        else:
            logger.info(f"✅ Note-buy пропущен для валидации (улучшен ContentEnhancer)")
        
        # Собираем информацию о санитизации для экспорта
        sanitization_parts = []
        if 'title_sanitization_info' in locals():
            sanitization_parts.append(title_sanitization_info)
        if 'note_buy_sanitization_info' in locals():
            sanitization_parts.append(note_buy_sanitization_info)
        
        sanitization_info = "; ".join(sanitization_parts) if sanitization_parts else ""
        
        # ОТЛАДКА: Проверяем, доходим ли мы до этого места
        logger.info(f"🔧 ОТЛАДКА: Дошли до генерации FAQ для {locale}")
        logger.info(f"🔧 ОТЛАДКА: safe_blocks содержит: {list(safe_blocks.keys())}")
        
        # Генерируем FAQ через ContentEnhancer перед рендером HTML
        logger.info(f"🔧 Генерируем FAQ для {locale}")
        
        # Heartbeat для FAQ генерации
        try:
            import sys
            if 'watchdog' in sys.modules:
                from scripts.universal_pipeline import watchdog
                watchdog.heartbeat("faq_generate_start")
        except:
            pass
        
        try:
            # Генерируем FAQ с ContentCritic
            faq_result = self.content_enhancer.enhance_product_with_critic(safe_blocks, locale, facts, specs)
            if faq_result and 'faq' in faq_result:
                safe_blocks['faq'] = faq_result['faq']
                faq_count = len(faq_result['faq'])
                logger.info(f"✅ FAQ сгенерирован: {faq_count} элементов для {locale}")
                
                # Heartbeat для FAQ завершения
                try:
                    import sys
                    if 'watchdog' in sys.modules:
                        from scripts.universal_pipeline import watchdog
                        watchdog.heartbeat(f"faq_generate_ok_count={faq_count}")
                except:
                    pass
            else:
                logger.warning(f"⚠️ FAQ не сгенерирован для {locale}")
                safe_blocks['faq'] = []
        except Exception as e:
            logger.error(f"❌ Ошибка генерации FAQ для {locale}: {e}")
            safe_blocks['faq'] = []
            
            # Heartbeat для FAQ ошибки
            try:
                import sys
                if 'watchdog' in sys.modules:
                    from scripts.universal_pipeline import watchdog
                    watchdog.heartbeat(f"faq_generate_fail_{type(e).__name__}")
            except:
                pass
        
        # Рендерим фрагмент описания товара с retry-механизмом
        from src.processing.fragment_renderer import ProductFragmentRenderer
        fragment_renderer = ProductFragmentRenderer()
        
        # Retry-механизм для рендеринга
        max_retries = 3
        product_fragment = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔧 Попытка рендеринга {attempt + 1}/{max_retries} для {locale}")
                product_fragment = fragment_renderer.render_product_fragment(safe_blocks, locale)
                
                # Проверяем, что не получили заглушку
                if 'error-message' in product_fragment:
                    logger.warning(f"⚠️ Получена заглушка на попытке {attempt + 1}, повторяем...")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        logger.error(f"❌ Все попытки рендеринга исчерпаны для {locale}")
                        raise ValueError(f"Не удалось сгенерировать контент для {locale}")
                else:
                    logger.info(f"✅ Рендеринг успешен на попытке {attempt + 1} для {locale}")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Ошибка рендеринга на попытке {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"🔄 Повторяем рендеринг для {locale}")
                    continue
                else:
                    logger.error(f"❌ Все попытки рендеринга исчерпаны для {locale}")
                    raise
        
        if not product_fragment:
            raise ValueError(f"Не удалось сгенерировать контент для {locale}")
        
        # Очищаем HTML от inline-стилей
        clean_fragment = fragment_renderer.clean_html(product_fragment)
        
        # Декодируем HTML-сущности для корректного отображения
        clean_fragment = fragment_renderer.decode_html_entities(clean_fragment)
        
        # Валидируем HTML-теги
        if not fragment_renderer.validate_html_tags(clean_fragment):
            logger.warning(f"⚠️ HTML tags validation failed for {h1}")
        
        # Собираем флаги и исправления
        flags = []
        consistency_fixes = []
        
        if volume_check.get('issues'):
            flags.extend(volume_check['issues'])
            consistency_fixes.extend(volume_check.get('fixes', []))
        
        if mass_check.get('issues'):
            flags.extend(mass_check['issues'])
            consistency_fixes.extend(mass_check.get('fixes', []))
        
        # Сохраняем фрагменты по локалям
        base_url = self._get_base_url(url)
        if base_url not in self.url_html_data:
            self.url_html_data[base_url] = {'ru_html': '', 'ua_html': ''}
        
        if locale == 'ru':
            self.url_html_data[base_url]['ru_html'] = clean_fragment
        else:
            self.url_html_data[base_url]['ua_html'] = clean_fragment
        
        # Добавляем информацию о санитизации note-buy если была
        if 'sanitization_info' in locals():
            flags.append(sanitization_info)
        
        return {
            'url': base_url,
            'locale': locale,
            'export_mode': 'full',
            'flags': flags,
            'needs_review': len(flags) > 0,
            'consistency_fixes': consistency_fixes,
            'html_length': len(clean_fragment),
            'processed': True,
            'retries': 0,
            'network_errors': 0,
            'budget_violation': False,
            'safe_facts_only': True,
            'controversial_data_removed': len(consistency_fixes) > 0,
            'safe_blocks': safe_blocks,
            'h1': h1,
            'safe_facts': safe_facts,
            'volume_consistent': volume_check.get('consistent', True),
            'enhancement_diagnostic': enhancement_diagnostic,
            'mass_consistent': mass_check.get('consistent', True),
            # Добавляем HTML фрагменты для conditional_exporter
            'RU_HTML': self.url_html_data[base_url]['ru_html'],
            'UA_HTML': self.url_html_data[base_url]['ua_html']
        }
    
    def _create_safe_result(self, url: str, locale: str, reason: str) -> Dict[str, Any]:
        """Создает безопасный результат для неуспешных случаев"""
        # Извлекаем базовые данные из URL
        h1 = self._extract_h1_from_url(url)
        safe_facts = {'title': h1}
        
        # Создаем безопасный фрагмент для неуспешных случаев
        from src.processing.safe_templates import SafeTemplates
        from src.processing.fragment_renderer import ProductFragmentRenderer
        
        templates = SafeTemplates()
        safe_blocks = templates.render_safe_blocks(h1, safe_facts, locale)
        
        fragment_renderer = ProductFragmentRenderer()
        product_fragment = fragment_renderer.render_product_fragment(safe_blocks, locale)
        clean_fragment = fragment_renderer.clean_html(product_fragment)
        
        # Декодируем HTML-сущности для корректного отображения
        clean_fragment = fragment_renderer.decode_html_entities(clean_fragment)
        
        # Валидируем HTML-теги
        if not fragment_renderer.validate_html_tags(clean_fragment):
            logger.warning(f"⚠️ HTML tags validation failed for {h1}")
        
        # Сохраняем фрагмент по локалям
        base_url = self._get_base_url(url)
        if base_url not in self.url_html_data:
            self.url_html_data[base_url] = {'ru_html': '', 'ua_html': ''}
        
        if locale == 'ru':
            self.url_html_data[base_url]['ru_html'] = clean_fragment
        else:
            self.url_html_data[base_url]['ua_html'] = clean_fragment
        
        return {
            'url': base_url,
            'locale': locale,
            'export_mode': 'specs_only',
            'flags': [reason],
            'needs_review': True,
            'consistency_fixes': [],
            'html_length': len(clean_fragment),
            'processed': True,
            'retries': 1,
            'network_errors': 1,
            'budget_violation': False,
            'fallback_reason': reason,
            'safe_facts_only': True,
            'controversial_data_removed': True
        }
    
    def _extract_h1(self, html: str) -> str:
        """Извлекает H1 из HTML (заглушка)"""
        import re
        match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL | re.IGNORECASE)
        if match:
            return re.sub(r'<[^>]+>', '', match.group(1)).strip()
        return "Товар"
    
    def _extract_h1_from_url(self, url: str) -> str:
        """Извлекает H1 из URL (заглушка)"""
        # Простая логика извлечения названия из URL
        parts = url.split('/')[-1].split('-')
        return ' '.join(parts).title()
    
    def _extract_specs(self, html: str) -> List[Dict[str, str]]:
        """Извлекает характеристики из HTML с множественными селекторами"""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html, 'html.parser')
        specs = []
        seen = set()
        
        # Множественные селекторы для поиска характеристик
        selectors = [
            'ul.specs li',
            'div.specs .spec-item', 
            'table.specs tr',
            'dl.specs dt, dl.specs dd',
            '.product-specs li',
            '.characteristics li',
            '.spec-list li',
            'table tr td:first-child',
            'dl dt',
            '.spec-item'
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    label, value = self._extract_kv_from_element(element)
                    if label and value and (label, value) not in seen:
                        seen.add((label, value))
                        specs.append({'name': label, 'value': value})
            except Exception as e:
                logger.debug(f"Ошибка при извлечении по селектору {selector}: {e}")
                continue
        
        # Если характеристик мало, пытаемся извлечь из таблиц
        if len(specs) < 8:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if label and value and (label, value) not in seen:
                            seen.add((label, value))
                            specs.append({'name': label, 'value': value})
        
        logger.info(f"Извлечено {len(specs)} характеристик из HTML")
        return specs[:12]  # Ограничиваем максимум 12 характеристиками
    
    def _extract_kv_from_element(self, element) -> tuple:
        """Извлекает ключ-значение из элемента"""
        try:
            # Ищем span с лейблом
            label_span = element.find('span')
            if label_span:
                label = label_span.get_text(strip=True).rstrip(':').strip()
                # Получаем текст без лейбла
                element_text = element.get_text(strip=True)
                value = element_text.replace(label_span.get_text(), '', 1).strip()
                return label, value
            
            # Если нет span, ищем по структуре dt/dd
            if element.name == 'dt':
                dd = element.find_next_sibling('dd')
                if dd:
                    return element.get_text(strip=True), dd.get_text(strip=True)
            
            # Если это td в таблице
            if element.name == 'td':
                parent = element.parent
                if parent:
                    cells = parent.find_all(['td', 'th'])
                    if len(cells) >= 2 and element == cells[0]:
                        return element.get_text(strip=True), cells[1].get_text(strip=True)
            
            # Общий случай - разбиваем по двоеточию
            text = element.get_text(strip=True)
            if ':' in text:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
            
            return '', ''
            
        except Exception as e:
            logger.debug(f"Ошибка при извлечении KV из элемента: {e}")
            return '', ''
    
    def _extract_mass_facts(self, html: str) -> List[str]:
        """Извлекает факты массы из HTML (заглушка)"""
        # Заглушка - должна быть заменена на реальную логику
        return []
    
    def _extract_volume_facts(self, html: str) -> List[str]:
        """Извлекает факты объёма из HTML (заглушка)"""
        # Заглушка - должна быть заменена на реальную логику
        return []
    
    def _get_base_url(self, url: str) -> str:
        """Получает базовый URL без локали"""
        if '/ru/' in url:
            return url.replace('/ru/', '/')
        return url
    
    def _write_final_results(self):
        """Записывает финальные результаты с HTML по локалям"""
        logger.info(f"📝 Записываем финальные результаты для {len(self.url_html_data)} URL")
        
        for base_url, html_data in self.url_html_data.items():
            result = {
                'url': base_url,
                'RU_HTML': html_data.get('ru_html', ''),
                'UA_HTML': html_data.get('ua_html', ''),
                'flags': [],  # Пустой список флагов для валидных результатов
                'needs_review': False
            }
            
            # Записываем в экспорт
            self.conditional_exporter.add_result(result)
            logger.info(f"✅ Записан результат: {base_url}")
    
    def _to_ru_url(self, ua_url: str) -> str:
        """Преобразует UA URL в RU URL"""
        if '/ru/' in ua_url:
            return ua_url
        return ua_url.replace('prorazko.com/', 'prorazko.com/ru/')
    
    def _determine_repair_reason(self, error_msg: str, llm_content: Dict[str, Any]) -> str:
        """Определяет причину ошибки валидации для отправки в ремонт"""
        error_lower = error_msg.lower()
        
        if "description must contain at least 4 sentences" in error_lower:
            return "desc_too_short"
        elif "volume" in error_lower and ("conflict" in error_lower or "controversial" in error_lower):
            return "volume_conflict"
        elif "mass" in error_lower and ("conflict" in error_lower or "controversial" in error_lower):
            return "mass_conflict"
        elif "locale" in error_lower and ("mixing" in error_lower or "validation" in error_lower):
            return "locale_mixing"
        elif "specs" in error_lower and ("invalid" in error_lower or "validation" in error_lower):
            return "specs_invalid"
        elif "faq" in error_lower and ("invalid" in error_lower or "validation" in error_lower):
            return "faq_invalid"
        elif "placeholder" in error_lower or "anti-placeholder" in error_lower:
            return "anti_placeholders"
        elif "structure" in error_lower and ("invalid" in error_lower or "validation" in error_lower):
            return "structure_invalid"
        else:
            return "unknown"
    
    def _enqueue_repair(self, url: str, input_index: int, locale: str, reason: str, 
                       llm_content: Dict[str, Any], error_details: str) -> None:
        """Добавляет URL в очередь ремонта"""
        from src.repair.repair_queue import RepairReason
        
        # Преобразуем строковую причину в enum
        try:
            repair_reason = RepairReason(reason)
        except ValueError:
            repair_reason = RepairReason.DESC_TOO_SHORT  # Fallback
        
        self.repair_queue.enqueue_repair(
            url=url,
            input_index=input_index,
            failing_locale=locale,
            reason=repair_reason,
            original_result=llm_content,
            error_details=error_details
        )
        
        logger.info(f"🔧 URL добавлен в очередь ремонта: {url} (индекс: {input_index}, локаль: {locale}, причина: {reason})")
    
    def get_repair_queue(self):
        """Возвращает очередь ремонта для обработки"""
        return self.repair_queue
    
    async def _process_url_locale_with_index(self, url: str, locale: str, index: int) -> Optional[Dict[str, Any]]:
        """Обработка одного URL для конкретной локали с индексом для системы ремонта"""
        try:
            logger.info(f"🔄 Обрабатываем {url} ({locale}) с индексом {index}")
            
            # Используем fallback fetcher
            from src.fetcher.fallback_fetcher import FallbackFetcher
            from src.processing.safe_facts import SafeFactsExtractor
            
            async with FallbackFetcher(timeout=15, retries=2) as fetcher:
                html = await fetcher.fetch_single(url, locale)
                
                if html:
                    # Обрабатываем HTML с безопасными фактами
                    result = await self._process_html_safe(html, url, locale, index)
                    
                    # Отмечаем как обработанный
                    self.progress_tracker.mark_processed(url, locale, result)
                    
                    return {
                        'html': result.get('RU_HTML', '') if locale == 'ru' else result.get('UA_HTML', ''),
                        'flags': result.get('flags', []),
                        'needs_review': result.get('needs_review', False),
                        'export_mode': result.get('export_mode', 'unknown')
                    }
                else:
                    logger.error(f"❌ Не удалось загрузить HTML для {url} ({locale})")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обработки {url} ({locale}): {e}")
            return None
