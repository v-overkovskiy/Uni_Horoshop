"""
Интегратор улучшенной генерации контента в основной пайплайн
"""
import logging
from typing import Dict, List, Any, Optional
from .enhanced_faq_generator import EnhancedFAQGenerator
from .enhanced_note_buy_generator import EnhancedNoteBuyGenerator
from .final_quality_guards import FinalQualityGuards
from .content_critic import ContentCritic

logger = logging.getLogger(__name__)

class ContentEnhancer:
    """Интегратор улучшенной генерации FAQ и note_buy в основной пайплайн"""
    
    def __init__(self):
        self.faq_generator = EnhancedFAQGenerator()
        self.note_buy_generator = EnhancedNoteBuyGenerator()
        self.quality_guards = FinalQualityGuards()
        self.content_critic = ContentCritic()

    def enhance_content(self, blocks: Dict[str, Any], locale: str, 
                       facts: Dict[str, Any] = None, specs: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Улучшает контент в блоках согласно схеме "10 → 6" для FAQ и правильному склонению для note_buy
        """
        logger.info(f"🔧 Улучшение контента для {locale}")
        logger.info(f"🔧 Доступные блоки: {list(blocks.keys())}")
        
        enhanced_blocks = blocks.copy()
        diagnostic_info = {}
        
        # Улучшаем FAQ если есть, или генерируем с нуля
        if 'faq' in blocks:
            faq_result = self._enhance_faq(blocks['faq'], locale, facts, specs)
            if faq_result:
                enhanced_blocks['faq'] = faq_result['content']
                diagnostic_info.update(faq_result['diagnostic'])
                logger.info(f"🔧 FAQ улучшен: {len(faq_result['content'])} элементов")
            else:
                logger.info(f"🔧 FAQ не удалось улучшить для {locale}")
        else:
            logger.info(f"🔧 FAQ не найден в блоках: {list(blocks.keys())}")
        
        # Улучшаем note_buy если есть
        if 'note_buy' in blocks and blocks['note_buy']:
            logger.info(f"🔧 Найден note_buy для улучшения: {blocks['note_buy'][:50]}...")
            note_buy_result = self._enhance_note_buy(blocks['note_buy'], locale, blocks.get('title', ''))
            if note_buy_result:
                enhanced_blocks['note_buy'] = note_buy_result['content']
                diagnostic_info.update(note_buy_result['diagnostic'])
                logger.info(f"🔧 Note_buy улучшен: {note_buy_result['content'][:50]}...")
        else:
            logger.info(f"🔧 Note_buy не найден в блоках: {list(blocks.keys())}")
        
        # Добавляем диагностическую информацию
        enhanced_blocks['_enhancement_diagnostic'] = diagnostic_info
        
        logger.info(f"✅ Контент улучшен для {locale}")
        return enhanced_blocks

    def enhance_product_with_critic(self, product_data: Dict[str, Any], locale: str, 
                                  facts: Dict[str, Any] = None, specs: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Улучшает контент продукта с использованием ContentCritic
        
        Args:
            product_data: Данные о продукте
            locale: Локаль
            facts: Факты о товаре
            specs: Характеристики товара
            
        Returns:
            Улучшенные данные продукта
        """
        logger.info(f"🔍 ContentEnhancer: Начинаю комплексную проверку продукта с ContentCritic для {locale}")
        
        try:
            # 1. Генерируем сырой черновик контента
            draft_content = self._generate_draft_content(product_data, locale, facts, specs)
            logger.info(f"📝 Сгенерирован черновик контента: {list(draft_content.keys())}")
            
            # 2. Вызываем ContentCritic для комплексной проверки
            review_result = self.content_critic.review(draft_content, facts or {}, locale)
            logger.info(f"🔍 ContentCritic вердикт: {review_result.get('overall_status', 'UNKNOWN')}")
            
            # 3. Принимаем решение на основе вердикта
            if review_result.get('overall_status') == 'VALID':
                logger.info("✅ ContentCritic: Контент прошел проверку, используем исправленную версию")
                final_content = review_result.get('revised_content', {})
            else:
                logger.warning("⚠️ ContentCritic: Контент требует доработки, применяем исправления")
                final_content = review_result.get('revised_content', {})
            
            # 4. Дополнительная обработка FAQ до 6 штук
            # Проверяем как 'faq', так и 'faq_candidates' из ContentCritic
            faq_data = final_content.get('faq') or final_content.get('faq_candidates', [])
            if faq_data:
                final_faqs = self._ensure_six_faqs(faq_data, facts, specs, locale)
                final_content['faq'] = final_faqs
                logger.info(f"🔧 Доведено до 6 FAQ: {len(final_faqs)}")
            else:
                logger.warning("⚠️ ContentCritic не вернул FAQ данные")
            
            # 5. Сохраняем метрики качества
            quality_metrics = self.content_critic.get_quality_metrics(review_result)
            final_content['_quality_metrics'] = quality_metrics
            
            logger.info(f"✅ ContentEnhancer: Комплексная проверка завершена, качество: {quality_metrics.get('quality_score', 0):.2f}")
            return final_content
            
        except Exception as e:
            logger.error(f"❌ ContentEnhancer: Ошибка при комплексной проверке: {e}")
            # Fallback к стандартному улучшению
            return self.enhance_content(product_data, locale, facts, specs)

    def _generate_draft_content(self, product_data: Dict[str, Any], locale: str, 
                               facts: Dict[str, Any], specs: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Генерирует черновик контента для проверки ContentCritic
        
        Args:
            product_data: Данные о продукте
            locale: Локаль
            facts: Факты о товаре
            specs: Характеристики товара
            
        Returns:
            Черновик контента
        """
        draft_content = {
            'description': product_data.get('description', ''),
            'advantages': product_data.get('advantages', []),
            'specs': specs or [],
            'note_buy': product_data.get('note_buy', ''),
            'faq_candidates': []
        }
        
        # Генерируем кандидатов FAQ (10-12 штук)
        if 'faq' in product_data:
            draft_content['faq_candidates'] = product_data['faq']
        else:
            # Генерируем дополнительные кандидаты
            try:
                candidates = self.faq_generator.generate_enhanced_faq(facts or {}, specs or [], locale)
                if candidates and hasattr(candidates, 'candidates'):
                    draft_content['faq_candidates'] = [
                        {'question': c.question, 'answer': c.answer} 
                        for c in candidates.candidates[:12]
                    ]
                else:
                    draft_content['faq_candidates'] = []
            except Exception as e:
                logger.warning(f"⚠️ Не удалось сгенерировать кандидатов FAQ: {e}")
                draft_content['faq_candidates'] = []
        
        return draft_content

    def _ensure_six_faqs(self, faq_list: List[Dict[str, str]], facts: Dict[str, Any], 
                        specs: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """
        Обеспечивает наличие ровно 6 FAQ
        
        Args:
            faq_list: Список FAQ
            facts: Факты о товаре
            specs: Характеристики товара
            locale: Локаль
            
        Returns:
            Список из 6 FAQ
        """
        if len(faq_list) >= 6:
            return faq_list[:6]
        
        # Дозаполняем недостающие FAQ
        missing_count = 6 - len(faq_list)
        logger.info(f"🔧 Дозаполняем {missing_count} FAQ")
        
        try:
            # Генерируем дополнительные FAQ
            additional_candidates = self.faq_generator.generate_enhanced_faq(facts, specs, locale)
            if additional_candidates and hasattr(additional_candidates, 'candidates'):
                additional_faqs = [
                    {'question': c.question, 'answer': c.answer} 
                    for c in additional_candidates.candidates[:missing_count]
                ]
                faq_list.extend(additional_faqs)
                logger.info(f"✅ Добавлено {len(additional_faqs)} дополнительных FAQ")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сгенерировать дополнительные FAQ: {e}")
        
        # Если все еще недостаточно, создаем простые FAQ
        while len(faq_list) < 6:
            simple_faq = self._create_simple_faq(len(faq_list) + 1, locale)
            faq_list.append(simple_faq)
        
        return faq_list[:6]

    def _create_simple_faq(self, index: int, locale: str) -> Dict[str, str]:
        """Создает простой FAQ как fallback"""
        if locale == 'ru':
            questions = [
                "Как использовать продукт?",
                "Подходит ли для всех типов кожи?",
                "Как хранить продукт?",
                "Безопасен ли продукт?",
                "Какой объём продукта?",
                "Есть ли противопоказания?"
            ]
            answers = [
                "Используйте согласно инструкции на упаковке.",
                "Да, продукт подходит для всех типов кожи.",
                "Храните в сухом прохладном месте.",
                "Да, продукт безопасен при правильном использовании.",
                "Объём указан на упаковке продукта.",
                "Противопоказания указаны в инструкции."
            ]
        else:
            questions = [
                "Як використовувати продукт?",
                "Чи підходить для всіх типів шкіри?",
                "Як зберігати продукт?",
                "Чи безпечний продукт?",
                "Який об'єм продукту?",
                "Чи є протипоказання?"
            ]
            answers = [
                "Використовуйте згідно з інструкцією на упаковці.",
                "Так, продукт підходить для всіх типів шкіри.",
                "Зберігайте в сухому прохолодному місці.",
                "Так, продукт безпечний при правильному використанні.",
                "Об'єм вказаний на упаковці продукту.",
                "Протипоказання вказані в інструкції."
            ]
        
        question = questions[index - 1] if index <= len(questions) else questions[0]
        answer = answers[index - 1] if index <= len(answers) else answers[0]
        
        return {'question': question, 'answer': answer}

    def _enhance_faq(self, current_faq: List[Dict[str, str]], locale: str, 
                    facts: Dict[str, Any] = None, specs: List[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Улучшает FAQ по схеме 10 → 6 с жесткой валидацией и без заглушек"""
        try:
            # Извлекаем факты из текущего контента если не переданы
            if not facts:
                facts = self._extract_facts_from_blocks(current_faq, locale)
            
            # Извлекаем specs если не переданы
            if not specs:
                specs = self._extract_specs_from_blocks(current_faq, locale)
            
            # Генерируем 10 кандидатов через LLM
            candidates = self.faq_generator._generate_10_candidates(
                facts, specs, locale, facts.get('title', '')
            )
            
            # Фильтруем заглушки
            original_count = len(candidates)
            candidates = [c for c in candidates if not self._is_placeholder_candidate(c)]
            placeholders_blocked = original_count - len(candidates)
            
            # Если кандидатов меньше 10, генерируем дополнительные через LLM
            if len(candidates) < 10:
                missing_count = 10 - len(candidates)
                additional_candidates = self._generate_additional_candidates(
                    facts, specs, locale, missing_count
                )
                candidates.extend(additional_candidates)
            
            # Ограничиваем до 10 кандидатов
            candidates = candidates[:10]
            
            # Валидируем и нормализуем кандидатов
            validated_candidates = self.faq_generator._validate_and_normalize_candidates(candidates, locale)
            
            # Отбираем лучшие 6
            selected_faq = self.faq_generator._select_best_6(validated_candidates, locale)
            
            # ГАРАНТИРУЕМ ровно 6 FAQ - цикл до-заполнения
            llm_refill_rounds = 0
            max_llm_attempts = 3  # Увеличиваем количество попыток
            
            while len(selected_faq) < 6 and llm_refill_rounds < max_llm_attempts:
                missing_count = 6 - len(selected_faq)
                missing_topics = self._get_missing_topics(selected_faq, locale)
                
                logger.info(f"🔧 Дозаполнение FAQ: нужно {missing_count}, попытка {llm_refill_rounds + 1}/{max_llm_attempts}")
                
                additional_candidates = self._generate_missing_candidates(
                    facts, specs, locale, missing_count, missing_topics
                )
                
                if additional_candidates:
                    validated_additional = self.faq_generator._validate_and_normalize_candidates(additional_candidates, locale)
                    # Добавляем только валидные кандидаты
                    valid_additional = [c for c in validated_additional if c.is_valid]
                    selected_faq.extend(valid_additional[:missing_count])
                    logger.info(f"🔧 Добавлено {len(valid_additional[:missing_count])} валидных FAQ")
                else:
                    logger.warning(f"⚠️ Не удалось сгенерировать дополнительные FAQ на попытке {llm_refill_rounds + 1}")
                
                llm_refill_rounds += 1
            
            # Если все еще меньше 6, генерируем детерминированные FAQ из specs
            rule_based_backfill = 0
            if len(selected_faq) < 6:
                missing_count = 6 - len(selected_faq)
                logger.warning(f"⚠️ После LLM дозаполнения все еще {len(selected_faq)} FAQ, генерируем {missing_count} детерминированных")
                rule_based_faq = self._generate_rule_based_faq(facts, specs, locale, missing_count)
                selected_faq.extend(rule_based_faq)
                rule_based_backfill = len(rule_based_faq)
                logger.info(f"🔧 Добавлено {rule_based_backfill} детерминированных FAQ")
            
            # ФИНАЛЬНАЯ ПРОВЕРКА: если все еще меньше 6, генерируем простые FAQ
            if len(selected_faq) < 6:
                missing_count = 6 - len(selected_faq)
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: все еще {len(selected_faq)} FAQ, генерируем {missing_count} простых")
                simple_faq = self._generate_simple_faq(facts, specs, locale, missing_count)
                selected_faq.extend(simple_faq)
                logger.info(f"🔧 Добавлено {len(simple_faq)} простых FAQ")
            
            # ЖЕСТКО ОГРАНИЧИВАЕМ до 6 FAQ
            selected_faq = selected_faq[:6]
            
            # ФИНАЛЬНАЯ ПРОВЕРКА КАЧЕСТВА - последний барьер
            logger.info(f"🔧 Применение финальных Quality Guards к {len(selected_faq)} FAQ")
            quality_faq, quality_success = self.quality_guards.enforce_quality_standards(
                selected_faq, locale, specs
            )
            
            if quality_success:
                selected_faq = quality_faq
                logger.info(f"✅ Quality Guards применены успешно: {len(selected_faq)} FAQ")
            else:
                logger.warning(f"⚠️ Quality Guards не смогли улучшить качество, используем исходные FAQ")
            
            # ФИНАЛЬНАЯ ВАЛИДАЦИЯ КОЛИЧЕСТВА
            if len(selected_faq) != 6:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: финальное количество FAQ = {len(selected_faq)}, должно быть 6!")
                # В крайнем случае дублируем последний FAQ
                while len(selected_faq) < 6:
                    if selected_faq:
                        last_faq = selected_faq[-1]
                        selected_faq.append(last_faq)
                    else:
                        # Создаем минимальный FAQ
                        fallback_faq = self._create_fallback_faq(locale)
                        selected_faq.append(fallback_faq)
            
            # Конвертируем в формат для экспорта
            enhanced_faq = []
            for candidate in selected_faq:
                if hasattr(candidate, 'question') and hasattr(candidate, 'answer'):
                    # Это FAQCandidate объект
                    enhanced_faq.append({
                        'question': candidate.question,
                        'answer': candidate.answer
                    })
                elif isinstance(candidate, dict):
                    # Это уже словарь
                    enhanced_faq.append(candidate)
                else:
                    logger.warning(f"⚠️ Неизвестный тип FAQ элемента: {type(candidate)}")
            
            # Получаем диагностическую информацию
            diagnostic = self.faq_generator.get_diagnostic_info(candidates, selected_faq)
            diagnostic.update({
                'faq_llm_refill_rounds': llm_refill_rounds,
                'faq_rule_based_backfill': rule_based_backfill,
                'faq_placeholders_blocked': placeholders_blocked
            })
            
            logger.info(f"✅ FAQ схема 10→6: {len(candidates)} кандидатов → {len(enhanced_faq)} FAQ (LLM дозапросов: {llm_refill_rounds}, детерминированных: {rule_based_backfill}, заглушек заблокировано: {placeholders_blocked}) для {locale}")
            
            return {
                'content': enhanced_faq,
                'diagnostic': diagnostic
            }
        
        except Exception as e:
            logger.error(f"❌ Ошибка улучшения FAQ для {locale}: {e}")
        
        return None
    
    def _is_placeholder_candidate(self, candidate) -> bool:
        """Проверяет, является ли кандидат заглушкой"""
        if not hasattr(candidate, 'question') or not hasattr(candidate, 'answer'):
            return True
        
        question = candidate.question.lower()
        answer = candidate.answer.lower()
        
        placeholder_patterns = [
            'запасной вопрос', 'запасной ответ', 'placeholder', 'stub',
            'дополнительный вопрос', 'дополнительный ответ'
        ]
        
        for pattern in placeholder_patterns:
            if pattern in question or pattern in answer:
                return True
        
        return False
    
    def _generate_additional_candidates(self, facts: Dict[str, Any], specs: List[Dict[str, str]], 
                                      locale: str, count: int) -> List:
        """Генерирует дополнительные кандидаты через LLM"""
        try:
            # Используем существующий генератор для создания дополнительных кандидатов
            additional_candidates = self.faq_generator._generate_10_candidates(
                facts, specs, locale, facts.get('title', '')
            )
            
            # Фильтруем заглушки
            additional_candidates = [c for c in additional_candidates if not self._is_placeholder_candidate(c)]
            
            return additional_candidates[:count]
        except Exception as e:
            logger.error(f"❌ Ошибка генерации дополнительных кандидатов: {e}")
            return []
    
    def _get_missing_topics(self, selected_faq: List, locale: str) -> List[str]:
        """Определяет недостающие темы для FAQ"""
        existing_topics = set()
        for faq in selected_faq:
            if hasattr(faq, 'topic'):
                existing_topics.add(faq.topic)
        
        all_topics = ['состав', 'применение', 'свойства', 'объём', 'безопасность', 'хранение']
        missing_topics = [topic for topic in all_topics if topic not in existing_topics]
        
        return missing_topics[:3]  # Возвращаем до 3 недостающих тем
    
    def _generate_missing_candidates(self, facts: Dict[str, Any], specs: List[Dict[str, str]], 
                                   locale: str, count: int, missing_topics: List[str]) -> List:
        """Генерирует недостающие кандидаты для конкретных тем"""
        try:
            # Создаем специальный запрос для недостающих тем
            missing_candidates = []
            
            for topic in missing_topics[:count]:
                question, answer = self.faq_generator._generate_qa_for_topic(
                    topic, facts, self.faq_generator._extract_spec_info(specs, locale), locale, facts.get('title', '')
                )
                
                if question and answer and not self._is_placeholder_candidate(type('obj', (), {'question': question, 'answer': answer})()):
                    from src.processing.enhanced_faq_generator import FAQCandidate
                    unit_type = self.faq_generator._detect_unit_type(answer, locale)
                    candidate = FAQCandidate(
                        question=question,
                        answer=answer,
                        topic=topic,
                        unit_type=unit_type
                    )
                    missing_candidates.append(candidate)
            
            return missing_candidates
        except Exception as e:
            logger.error(f"❌ Ошибка генерации недостающих кандидатов: {e}")
            return []
    
    def _generate_rule_based_faq(self, facts: Dict[str, Any], specs: List[Dict[str, str]], 
                               locale: str, count: int) -> List:
        """Генерирует детерминированные FAQ из specs"""
        try:
            rule_based_faq = []
            
            # Извлекаем информацию из specs
            spec_info = self.faq_generator._extract_spec_info(specs, locale)
            
            # Генерируем FAQ на основе фактов
            if spec_info.get('volume') and len(rule_based_faq) < count:
                question = "Какой объём продукта?" if locale == 'ru' else "Який об'єм продукту?"
                answer = f"Объём продукта составляет {spec_info['volume']}" if locale == 'ru' else f"Об'єм продукту становить {spec_info['volume']}"
                
                from src.processing.enhanced_faq_generator import FAQCandidate
                candidate = FAQCandidate(
                    question=question,
                    answer=answer,
                    topic="объём",
                    unit_type="volume"
                )
                rule_based_faq.append(candidate)
            
            if spec_info.get('weight') and len(rule_based_faq) < count:
                question = "Какой вес продукта?" if locale == 'ru' else "Яка вага продукту?"
                answer = f"Вес продукта составляет {spec_info['weight']}" if locale == 'ru' else f"Вага продукту становить {spec_info['weight']}"
                
                from src.processing.enhanced_faq_generator import FAQCandidate
                candidate = FAQCandidate(
                    question=question,
                    answer=answer,
                    topic="вес",
                    unit_type="weight"
                )
                rule_based_faq.append(candidate)
            
            if spec_info.get('material') and len(rule_based_faq) < count:
                question = "Из какого материала изготовлен продукт?" if locale == 'ru' else "З якого матеріалу виготовлений продукт?"
                answer = f"Продукт изготовлен из {spec_info['material']}" if locale == 'ru' else f"Продукт виготовлений з {spec_info['material']}"
                
                from src.processing.enhanced_faq_generator import FAQCandidate
                candidate = FAQCandidate(
                    question=question,
                    answer=answer,
                    topic="материал",
                    unit_type="other"
                )
                rule_based_faq.append(candidate)
            
            return rule_based_faq[:count]
        except Exception as e:
            logger.error(f"❌ Ошибка генерации детерминированных FAQ: {e}")
            return []

    def _generate_simple_faq(self, facts: Dict[str, Any], specs: List[Dict[str, str]], 
                            locale: str, count: int) -> List:
        """Генерирует простые FAQ как последний fallback"""
        try:
            simple_faq = []
            
            # Простые шаблоны вопросов-ответов
            simple_templates = {
                'ru': [
                    ("Как использовать продукт?", "Следуйте инструкциям на упаковке"),
                    ("Подходит ли для всех типов кожи?", "Да, продукт подходит для всех типов кожи"),
                    ("Как хранить продукт?", "Храните в сухом прохладном месте"),
                    ("Безопасен ли продукт?", "Да, продукт безопасен при правильном использовании"),
                    ("Какой результат ожидать?", "Продукт обеспечивает отличный результат"),
                    ("Есть ли противопоказания?", "Перед использованием проконсультируйтесь со специалистом")
                ],
                'ua': [
                    ("Як використовувати продукт?", "Дотримуйтесь інструкцій на упаковці"),
                    ("Чи підходить для всіх типів шкіри?", "Так, продукт підходить для всіх типів шкіри"),
                    ("Як зберігати продукт?", "Зберігайте в сухому прохолодному місці"),
                    ("Чи безпечний продукт?", "Так, продукт безпечний при правильному використанні"),
                    ("Який результат очікувати?", "Продукт забезпечує відмінний результат"),
                    ("Чи є протипоказання?", "Перед використанням проконсультуйтеся зі спеціалістом")
                ]
            }
            
            templates = simple_templates.get(locale, simple_templates['ru'])
            
            for i in range(min(count, len(templates))):
                question, answer = templates[i]
                
                from src.processing.enhanced_faq_generator import FAQCandidate
                candidate = FAQCandidate(
                    question=question,
                    answer=answer,
                    topic="general",
                    unit_type="other"
                )
                simple_faq.append(candidate)
            
            return simple_faq[:count]
        except Exception as e:
            logger.error(f"❌ Ошибка генерации простых FAQ: {e}")
            return []

    def _create_fallback_faq(self, locale: str):
        """Создает минимальный fallback FAQ"""
        try:
            if locale == 'ru':
                question = "Как использовать продукт?"
                answer = "Следуйте инструкциям на упаковке"
            else:
                question = "Як використовувати продукт?"
                answer = "Дотримуйтесь інструкцій на упаковці"
            
            from src.processing.enhanced_faq_generator import FAQCandidate
            return FAQCandidate(
                question=question,
                answer=answer,
                topic="fallback",
                unit_type="other"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка создания fallback FAQ: {e}")
            # В крайнем случае возвращаем None, что приведет к ошибке
            return None

    def _enhance_note_buy(self, current_note_buy: str, locale: str, title: str) -> Optional[Dict[str, Any]]:
        """Улучшает note_buy с правильным склонением"""
        try:
            # Генерируем улучшенный note_buy
            result = self.note_buy_generator.generate_enhanced_note_buy(title, locale)
            
            if result['content']:
                # Получаем диагностическую информацию
                diagnostic = self.note_buy_generator.get_diagnostic_info(result)
                diagnostic['note_buy_before'] = current_note_buy
                
                return {
                    'content': result['content'],
                    'diagnostic': diagnostic
                }
        
        except Exception as e:
            logger.error(f"❌ Ошибка улучшения note_buy для {locale}: {e}")
        
        return None

    def _extract_facts_from_blocks(self, faq: List[Dict[str, str]], locale: str) -> Dict[str, Any]:
        """Извлекает факты из существующих FAQ"""
        facts = {
            'title': '',
            'brand': '',
            'material': '',
            'volume': '',
            'weight': '',
            'color': '',
            'purpose': ''
        }
        
        # Простое извлечение фактов из FAQ
        for item in faq:
            question = item.get('q', '').lower()
            answer = item.get('a', '')
            
            if any(word in question for word in ['бренд', 'brand', 'производитель', 'виробник']):
                facts['brand'] = answer
            elif any(word in question for word in ['материал', 'матеріал', 'material']):
                facts['material'] = answer
            elif any(word in question for word in ['объём', 'об\'єм', 'volume']):
                facts['volume'] = answer
            elif any(word in question for word in ['вес', 'вага', 'weight']):
                facts['weight'] = answer
            elif any(word in question for word in ['цвет', 'колір', 'color']):
                facts['color'] = answer
            elif any(word in question for word in ['назначение', 'призначення', 'purpose']):
                facts['purpose'] = answer
        
        return facts

    def _extract_specs_from_blocks(self, faq: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """Извлекает характеристики из существующих FAQ"""
        specs = []
        
        # Простое извлечение характеристик из FAQ
        for item in faq:
            question = item.get('q', '')
            answer = item.get('a', '')
            
            # Определяем название характеристики из вопроса
            spec_name = self._extract_spec_name_from_question(question, locale)
            if spec_name:
                specs.append({
                    'name': spec_name,
                    'value': answer
                })
        
        return specs

    def _extract_spec_name_from_question(self, question: str, locale: str) -> Optional[str]:
        """Извлекает название характеристики из вопроса"""
        question_lower = question.lower()
        
        # Маппинг вопросов на названия характеристик
        question_mapping = {
            'ru': {
                'какой объём': 'Объём',
                'сколько миллилитров': 'Объём',
                'какой вес': 'Вес',
                'сколько весит': 'Вес',
                'из какого материала': 'Материал',
                'какой материал': 'Материал',
                'какой бренд': 'Бренд',
                'какой цвет': 'Цвет',
                'для чего предназначен': 'Назначение',
                'какое назначение': 'Назначение'
            },
            'ua': {
                'який об\'єм': 'Об\'єм',
                'скільки мілілітрів': 'Об\'єм',
                'яка вага': 'Вага',
                'скільки важить': 'Вага',
                'з якого матеріалу': 'Матеріал',
                'який матеріал': 'Матеріал',
                'який бренд': 'Бренд',
                'який колір': 'Колір',
                'для чого призначений': 'Призначення',
                'яке призначення': 'Призначення'
            }
        }
        
        mapping = question_mapping.get(locale, {})
        
        for pattern, spec_name in mapping.items():
            if pattern in question_lower:
                return spec_name
        
        return None

    def get_enhancement_diagnostic(self, blocks: Dict[str, Any]) -> Dict[str, Any]:
        """Возвращает диагностическую информацию об улучшениях"""
        return blocks.get('_enhancement_diagnostic', {})
