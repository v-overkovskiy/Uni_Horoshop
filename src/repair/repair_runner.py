"""
Repair Runner - обработчик очереди ремонта
"""
import logging
from typing import Dict, List, Any, Optional
from src.repair.repair_queue import RepairQueue, RepairItem, RepairReason
from src.repair.sanity_fixer import SanityFixer

logger = logging.getLogger(__name__)

class RepairRunner:
    """Обработчик очереди ремонта"""
    
    def __init__(self, conditional_exporter):
        self.conditional_exporter = conditional_exporter
        self.sanity_fixer = SanityFixer()
        
        # Статистика
        self.repair_stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'sanity_fixes_applied': 0,
            'llm_specs_localized_count': 0,
            'deterministic_specs_drop_count': 0,
            'reasons': {}
        }
    
    def run_repairs(self, repair_queue: RepairQueue) -> Dict[str, Any]:
        """
        Запускает обработку очереди ремонта
        
        Args:
            repair_queue: Очередь ремонта
            
        Returns:
            Статистика обработки
        """
        if not repair_queue.has_pending_items():
            logger.info("🔧 Нет элементов в очереди ремонта")
            return self.repair_stats
        
        pending_items = repair_queue.get_pending_items()
        initial_queue_length = len(pending_items)
        logger.info(f"🔧 Запуск обработки очереди ремонта: {initial_queue_length} элементов")
        
        # Фиксируем исходную длину очереди для финальной проверки
        self.initial_queue_length = initial_queue_length
        
        for item in pending_items:
            try:
                self._process_repair_item(item, repair_queue)
                self.repair_stats['processed'] += 1
            except Exception as e:
                logger.error(f"❌ Ошибка при обработке элемента ремонта {item.url}: {e}")
                repair_queue.mark_failed(item, str(e))
                self.repair_stats['failed'] += 1
        
        # Обновляем статистику причин
        self._update_reason_stats(repair_queue)
        
        logger.info(f"✅ Обработка очереди ремонта завершена: {self.repair_stats}")
        
        # Проверяем, что все элементы были обработаны
        self._validate_repair_completion(repair_queue)
        
        return self.repair_stats
    
    def _process_repair_item(self, item: RepairItem, repair_queue: RepairQueue) -> None:
        """Обрабатывает отдельный элемент ремонта"""
        logger.info(f"🔧 Обработка ремонта: {item.url} (локаль: {item.failing_locale}, причина: {item.reason.value})")
        
        # Применяем соответствующий фикс
        if item.reason == RepairReason.DESC_TOO_SHORT:
            repaired_result = self._fix_description(item)
        elif item.reason == RepairReason.VOLUME_CONFLICT:
            repaired_result = self._fix_volume_conflict(item)
        elif item.reason == RepairReason.MASS_CONFLICT:
            repaired_result = self._fix_mass_conflict(item)
        elif item.reason == RepairReason.LOCALE_MIXING:
            repaired_result = self._fix_locale_mixing(item)
        else:
            # Для других причин пытаемся применить базовый фикс
            repaired_result = self._fix_generic(item)
        
        # Всегда учитываем применение sanity-фиксов независимо от успеха
        if repaired_result.get('sanity_fix_applied'):
            self.repair_stats['sanity_fixes_applied'] += 1
        
        # Отслеживаем новые метрики независимо от успеха
        if repaired_result.get('llm_specs_localized'):
            self.repair_stats['llm_specs_localized_count'] += 1
        if repaired_result.get('deterministic_specs_dropped'):
            self.repair_stats['deterministic_specs_drop_count'] += 1
        
        if repaired_result['success']:
            # Валидируем результат
            if self._validate_repaired_result(repaired_result, item):
                # Обновляем результат в экспортере
                self._update_exporter_result(item, repaired_result)
                repair_queue.mark_completed(item, repaired_result)
                self.repair_stats['successful'] += 1
                
                logger.info(f"✅ Ремонт успешен: {item.url} (локаль: {item.failing_locale})")
            else:
                logger.error(f"❌ Отремонтированный результат не прошел валидацию: {item.url}")
                repair_queue.mark_failed(item, "validation_failed_after_repair")
                self.repair_stats['failed'] += 1
        else:
            logger.error(f"❌ Ремонт не удался: {item.url} - {repaired_result.get('reason', 'unknown')}")
            repair_queue.mark_failed(item, repaired_result.get('reason', 'unknown'))
            self.repair_stats['failed'] += 1
    
    def _fix_description(self, item: RepairItem) -> Dict[str, Any]:
        """Применяет цикл до-ремонта для описаний с повторными LLM-дозапросами"""
        logger.info(f"🔧 Запуск цикла до-ремонта для {item.failing_locale}")
        
        original_content = item.original_result
        current_content = original_content.copy()
        previous_attempts = []
        
        # Сохраняем все важные поля, которые не должны теряться при ремонте
        preserved_fields = {
            'title': current_content.get('title', ''),  # ← Добавляем сохранение заголовка
            'note_buy': current_content.get('note_buy', ''),
            'faq': current_content.get('faq', []),
            'specs': current_content.get('specs', []),
            'advantages': current_content.get('advantages', []),
            'steps': current_content.get('steps', [])
        }
        
        # Для UA делаем до 4 попыток (2 LLM + 2 sanity-фикс), для RU - до 3
        max_attempts = 4 if item.failing_locale == 'ua' else 3
        
        # Цикл до max_attempts попыток LLM + sanity-фикс
        for attempt in range(max_attempts):
            logger.info(f"🔧 Попытка {attempt + 1}/{max_attempts} цикла до-ремонта")
            
            current_description = current_content.get('description', '')
            current_sentences = self.sanity_fixer._count_sentences(current_description)
            current_chars = len(current_description.strip())
            
            logger.info(f"🔍 Текущее состояние: {current_sentences} предложений, {current_chars} символов")
            
            # Проверяем, соответствует ли описание требованиям
            if current_sentences >= 5 and current_chars >= 450:
                logger.info(f"✅ Описание соответствует требованиям после попытки {attempt + 1}")
                break
            
            # Если это первая попытка или предыдущие LLM-попытки не удались
            if attempt == 0 or len(previous_attempts) > 0:
                # Попытка LLM-генерации с строгим промптом
                logger.info(f"🔧 LLM-генерация с строгим промптом (попытка {attempt + 1})")
                
                product_data = {
                    'url': item.url,
                    'title': current_content.get('title', ''),
                    'specs': current_content.get('specs', [])
                }
                
                llm_result = self.sanity_fixer.generate_strict_description_with_llm(
                    product_data, item.failing_locale, previous_attempts
                )
                
                if llm_result['success']:
                    logger.info(f"✅ LLM-генерация успешна: {llm_result['sentences']} предложений, {llm_result['chars']} символов")
                    current_content['description'] = llm_result['description']
                    previous_attempts.append(llm_result['description'])
                    continue
                else:
                    logger.warning(f"⚠️ LLM-генерация не удалась: {llm_result.get('reason', 'unknown')}")
                    if llm_result.get('description'):
                        previous_attempts.append(llm_result['description'])
            
            # Применяем sanity-фикс для добавления предложений
            logger.info(f"🔧 Применение sanity-фикса (попытка {attempt + 1})")
            
            # Сначала гарантируем минимальное количество предложений
            sentences_result = self.sanity_fixer.ensure_min_sentences(
                current_description, item.failing_locale, target=5
            )
            
            if sentences_result['success']:
                current_content['description'] = sentences_result['fixed_description']
                current_description = sentences_result['fixed_description']
            
            # Затем гарантируем минимальную длину
            chars_result = self.sanity_fixer.ensure_min_chars(
                current_description, item.failing_locale, target=450
            )
            
            if chars_result['success']:
                current_content['description'] = chars_result['fixed_description']
        
        # Нормализуем заголовок если он пуст/короткий (для UA и RU)
        current_content = self.sanity_fixer.normalize_title(
            current_content, item.failing_locale, {'url': item.url}
        )
        
        # ВОССТАНАВЛИВАЕМ сохраненные поля, которые могли быть потеряны при ремонте
        for field_name, field_value in preserved_fields.items():
            if field_name not in current_content or not current_content[field_name]:
                if field_value:  # Только если сохраненное значение не пустое
                    current_content[field_name] = field_value
                    logger.info(f"🔧 Восстановлено поле {field_name} после ремонта")
        
        # Если note_buy все еще пустой, генерируем его заново
        if not current_content.get('note_buy') or len(current_content.get('note_buy', '').strip()) < 20:
            logger.warning(f"⚠️ Note_buy пустой или слишком короткий после ремонта, генерируем заново")
            try:
                from src.processing.enhanced_note_buy_generator import EnhancedNoteBuyGenerator
                note_buy_generator = EnhancedNoteBuyGenerator()
                note_buy_result = note_buy_generator.generate_enhanced_note_buy(
                    current_content.get('title', ''), item.failing_locale
                )
                if note_buy_result['content']:
                    current_content['note_buy'] = note_buy_result['content']
                    logger.info(f"✅ Note_buy сгенерирован заново: {note_buy_result['content'][:50]}...")
            except Exception as e:
                logger.error(f"❌ Ошибка генерации note_buy: {e}")
        
        # Финальная проверка
        final_description = current_content.get('description', '')
        final_sentences = self.sanity_fixer._count_sentences(final_description)
        final_chars = len(final_description.strip())
        final_title = current_content.get('title', '')
        final_note_buy = current_content.get('note_buy', '')
        
        logger.info(f"🔍 Финальное состояние: {final_sentences} предложений, {final_chars} символов, заголовок: {len(final_title)} символов, note_buy: {len(final_note_buy)} символов")
        
        # Проверяем успешность
        if final_sentences >= 5 and final_chars >= 450 and len(final_title.strip()) >= 10 and len(final_note_buy.strip()) >= 20:
            logger.info(f"✅ Цикл до-ремонта успешен")
            current_content['sanity_fix_applied'] = True
            current_content['sanity_fix_details'] = {
                'attempts_made': len(previous_attempts) + 1,
                'final_sentences': final_sentences,
                'final_chars': final_chars,
                'reason': 'desc_too_short_cycle'
            }
            
            return {
                'success': True,
                'repaired_content': current_content,
                'sanity_fix_applied': True,
                'fix_type': 'description_repair_cycle',
                'attempts_made': len(previous_attempts) + 1
            }
        else:
            logger.error(f"❌ Цикл до-ремонта не достиг цели: {final_sentences} предложений, {final_chars} символов")
            return {
                'success': False,
                'reason': 'repair_cycle_failed',
                'fix_type': 'description_repair_cycle',
                'attempts_made': len(previous_attempts) + 1,
                'final_state': {
                    'sentences': final_sentences,
                    'chars': final_chars,
                    'title_length': len(final_title.strip())
                }
            }
    
    def _fix_volume_conflict(self, item: RepairItem) -> Dict[str, Any]:
        """Фиксит конфликт объемных данных"""
        # Для volume_conflict применяем sanity-фикс описания
        # так как конфликт обычно возникает после удаления спорных чисел
        return self._fix_description(item)
    
    def _fix_mass_conflict(self, item: RepairItem) -> Dict[str, Any]:
        """Фиксит конфликт массовых данных"""
        # Аналогично volume_conflict
        return self._fix_description(item)
    
    def _fix_locale_mixing(self, item: RepairItem) -> Dict[str, Any]:
        """Фиксит смешение локалей"""
        logger.info(f"🔧 Применение детерминированной нормализации для locale_mixing в {item.failing_locale}")
        
        # Используем детерминированную нормализацию вместо LLM
        specs = item.original_result.get('specs', [])
        if specs:
            normalize_result = self.sanity_fixer.deterministic_specs_normalize(specs, item.failing_locale)
            
            if normalize_result['success']:
                logger.info(f"✅ Детерминированная нормализация ключей успешна")
                repaired_content = item.original_result.copy()
                repaired_content['specs'] = normalize_result['normalized_specs']
                
                # Применяем сервисный фикс для очистителей если нужно
                url = item.url.lower()
                is_service_product = any(word in url for word in ['ochysnyk', 'ochistitel', 'cleaner'])
                
                if is_service_product and item.failing_locale == 'ru':
                    product_data = {'url': item.url, 'title': item.original_result.get('title', '')}
                    repaired_content = self.sanity_fixer.apply_service_product_fix(
                        repaired_content, item.failing_locale, product_data
                    )
                
                return {
                    'success': True,
                    'repaired_content': repaired_content,
                    'sanity_fix_applied': True,
                    'fix_type': 'deterministic_specs_normalize',
                    'deterministic_specs_normalized': True,
                    'fixed_count': normalize_result.get('fixed_count', 0),
                    'dropped_count': normalize_result.get('dropped_count', 0)
                }
            else:
                logger.warning(f"⚠️ Детерминированная нормализация не удалась: {normalize_result['reason']}")
        
        # Fallback: детерминированный дроп конфликтных ключей
        logger.info(f"🔧 Применение детерминированного fallback")
        repaired_content = item.original_result.copy()
        repaired_content['specs'] = self.sanity_fixer.deterministic_specs_drop(
            specs, item.failing_locale
        )
        
        # Применяем сервисный фикс для очистителей если нужно
        url = item.url.lower()
        is_service_product = any(word in url for word in ['ochysnyk', 'ochistitel', 'cleaner'])
        
        if is_service_product and item.failing_locale == 'ru':
            product_data = {'url': item.url, 'title': item.original_result.get('title', '')}
            repaired_content = self.sanity_fixer.apply_service_product_fix(
                repaired_content, item.failing_locale, product_data
            )
        
        return {
            'success': True,
            'repaired_content': repaired_content,
            'sanity_fix_applied': True,
            'fix_type': 'deterministic_specs_drop',
            'deterministic_specs_dropped': True
        }
    
    def _fix_generic(self, item: RepairItem) -> Dict[str, Any]:
        """Применяет общий фикс для неизвестных причин"""
        # Пытаемся применить sanity-фикс как универсальное решение
        return self._fix_description(item)
    
    def _validate_repaired_result(self, repaired_result: Dict[str, Any], item: RepairItem) -> bool:
        """Валидирует отремонтированный результат"""
        try:
            repaired_content = repaired_result['repaired_content']
            
            # Проверяем все компоненты через guards
            from src.validation.guards import (
                description_guard, specs_guard, locale_title_guard, 
                faq_guard, anti_placeholders_guard, note_buy_guard
            )
            
            # Валидация описания
            description = repaired_content.get('description', '')
            if not description or len(description.strip()) < 100:
                logger.warning(f"⚠️ Отремонтированное описание слишком короткое: {len(description)} символов")
                return False
            
            # Проверяем количество предложений
            sentences = self.sanity_fixer._count_sentences(description)
            if sentences < 4:
                logger.warning(f"⚠️ Отремонтированное описание содержит недостаточно предложений: {sentences}")
                return False
            
            # Валидация характеристик
            specs = repaired_content.get('specs', [])
            if not specs or len(specs) < 3:
                logger.warning(f"⚠️ Недостаточно характеристик: {len(specs)}")
                return False
            
            # Валидация заголовка
            title = repaired_content.get('title', '')
            if not title or len(title.strip()) < 10:
                logger.warning(f"⚠️ Заголовок слишком короткий: {len(title)} символов")
                return False
            
            # Валидация note_buy
            note_buy = repaired_content.get('note_buy', '')
            if not note_buy or len(note_buy.strip()) < 20:
                logger.warning(f"⚠️ Note_buy слишком короткий: {len(note_buy)} символов")
                return False
            
            # Валидация note_buy через guard
            try:
                note_buy_guard(note_buy, item.failing_locale)
            except Exception as e:
                logger.warning(f"⚠️ Note_buy не прошел валидацию: {e}")
                return False
            
            # Валидация FAQ
            faq = repaired_content.get('faq', [])
            if not faq or len(faq) < 4:
                logger.warning(f"⚠️ Недостаточно FAQ: {len(faq)}")
                return False
            
            # Дополнительная проверка для сервисных товаров
            if repaired_result.get('fix_type') == 'service_product_fix':
                # Проверяем, что заголовок содержит правильную формулировку для очистителя
                if 'очиститель' not in title.lower() and 'очисник' not in title.lower():
                    logger.warning(f"⚠️ Заголовок не содержит ключевых слов для очистителя: {title}")
                    return False
            
            logger.info(f"✅ Отремонтированный результат прошел все проверки валидации: {sentences} предложений, {len(description)} символов")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации отремонтированного результата: {e}")
            return False
    
    def _update_exporter_result(self, item: RepairItem, repaired_result: Dict[str, Any]) -> None:
        """Обновляет результат в экспортере"""
        try:
            repaired_content = repaired_result['repaired_content']
            
            # Создаем обновленный результат
            updated_result = {
                'url': item.url,
                'input_index': item.input_index,
                'failing_locale': item.failing_locale,
                'repair_applied': True,
                'repair_reason': item.reason.value,
                'sanity_fix_applied': repaired_result.get('sanity_fix_applied', False),
                'repaired_content': repaired_content
            }
            
            # Добавляем информацию о ремонте в Issues
            if item.failing_locale == 'ru':
                issues_key = 'RU_Issues'
            else:
                issues_key = 'UA_Issues'
            
            # Определяем тип ремонта для Issues
            fix_type = repaired_result.get('fix_type', '')
            repair_info_parts = []
            
            if fix_type == 'llm_specs_localization':
                repair_info_parts.append("repair: specs_localized_llm")
            elif fix_type == 'deterministic_specs_drop':
                repair_info_parts.append("repair: specs_dropped_deterministic")
            elif fix_type == 'service_product_fix':
                repair_info_parts.append("repair: title_sanitized_safe_constructor")
            else:
                repair_info_parts.append("repair: sanity_fix(desc_len<4 after number_sanitize)")
            
            # Комбинируем несколько типов ремонта если нужно
            repair_info = " + ".join(repair_info_parts)
            updated_result[issues_key] = repair_info
            
            # Пересобираем HTML фрагмент с отремонтированными данными
            from src.processing.fragment_renderer import ProductFragmentRenderer
            fragment_renderer = ProductFragmentRenderer()
            
            # Создаем safe_blocks с отремонтированными данными
            safe_blocks = {
                'title': repaired_content.get('title', ''),
                'description': repaired_content.get('description', ''),
                'specs': repaired_content.get('specs', []),
                'note_buy': repaired_content.get('note_buy', ''),
                'faq': repaired_content.get('faq', []),
                'faq_data': repaired_content.get('faq', [])
            }
            
            # Убеждаемся, что specs - это список словарей
            if safe_blocks['specs'] and isinstance(safe_blocks['specs'][0], list):
                # Если specs содержит списки, преобразуем в словари
                fixed_specs = []
                for spec in safe_blocks['specs']:
                    if isinstance(spec, list) and len(spec) >= 2:
                        fixed_specs.append({'name': spec[0], 'value': spec[1]})
                    elif isinstance(spec, dict):
                        fixed_specs.append(spec)
                safe_blocks['specs'] = fixed_specs
            
            repaired_html = fragment_renderer.render_product_fragment(safe_blocks, item.failing_locale)
            
            # Очищаем HTML от inline-стилей, но сохраняем JSON-LD
            repaired_html = fragment_renderer.clean_html(repaired_html)
            
            # Обновляем результат в экспортере
            self.conditional_exporter.upsert_repair_result(
                input_index=item.input_index,
                repaired_result={
                    'failing_locale': item.failing_locale,
                    'repaired_html': repaired_html,
                    'issues': repair_info,
                    'repair_reason': item.reason.value
                }
            )
            
            logger.info(f"📝 Результат обновлен в экспортере для {item.url} (локаль: {item.failing_locale})")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления результата в экспортере: {e}")
    
    def _update_reason_stats(self, repair_queue: RepairQueue) -> None:
        """Обновляет статистику по причинам"""
        stats = repair_queue.get_stats()
        self.repair_stats['reasons'] = stats.get('reason_distribution', {})
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику ремонта"""
        total_processed = self.repair_stats['processed']
        success_rate = self.repair_stats['successful'] / total_processed if total_processed > 0 else 0
        sanity_fix_rate = self.repair_stats['sanity_fixes_applied'] / total_processed if total_processed > 0 else 0
        
        llm_localization_rate = self.repair_stats['llm_specs_localized_count'] / total_processed if total_processed > 0 else 0
        deterministic_drop_rate = self.repair_stats['deterministic_specs_drop_count'] / total_processed if total_processed > 0 else 0
        
        return {
            'repair_processed_count': self.repair_stats['processed'],
            'repair_successful_count': self.repair_stats['successful'],
            'repair_failed_count': self.repair_stats['failed'],
            'repair_success_rate': f"{success_rate:.1%}",
            'sanity_fix_applied_count': self.repair_stats['sanity_fixes_applied'],
            'sanity_fix_rate': f"{sanity_fix_rate:.1%}",
            'llm_specs_localized_count': self.repair_stats['llm_specs_localized_count'],
            'llm_localization_rate': f"{llm_localization_rate:.1%}",
            'deterministic_specs_drop_count': self.repair_stats['deterministic_specs_drop_count'],
            'deterministic_drop_rate': f"{deterministic_drop_rate:.1%}",
            'repair_reason_distribution': self.repair_stats['reasons']
        }

    def _validate_repair_completion(self, repair_queue: RepairQueue) -> None:
        """Проверяет, что все элементы в очереди ремонта были обработаны"""
        processed = self.repair_stats['processed']
        initial_length = getattr(self, 'initial_queue_length', 0)
        
        logger.info(f"🔍 Проверка завершения ремонта: обработано {processed} из {initial_length}")
        
        if processed != initial_length:
            logger.warning(f"⚠️ Не все элементы очереди ремонта были обработаны: {processed}/{initial_length}")
            
            # Проверяем, есть ли еще элементы в очереди
            pending_items = repair_queue.get_pending_items()
            if pending_items:
                logger.warning(f"⚠️ В очереди осталось {len(pending_items)} элементов")
                for item in pending_items:
                    logger.warning(f"⚠️ Необработанный элемент: {item.url} ({item.failing_locale})")
            else:
                logger.info("✅ Все элементы очереди ремонта обработаны")
        else:
            logger.info("✅ Все элементы очереди ремонта успешно обработаны")
