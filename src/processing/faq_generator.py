"""
Усиленный генератор FAQ с использованием полного контекста из UnifiedParser
"""
import json
import logging
from typing import List, Dict, Any, Optional
import re
from src.llm.smart_llm_client import SmartLLMClient

logger = logging.getLogger(__name__)

class FaqGenerator:
    """
    Генератор вдумчивых FAQ, использующий весь контекст товара.
    Делает отдельный, целенаправленный LLM-запрос для создания качественных вопросов.
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client or SmartLLMClient()
        self.fallback_questions = [
            "Для чего предназначен этот товар?",
            "Как правильно использовать продукт?",
            "Какие есть противопоказания?",
            "Как хранить товар?",
            "Подходит ли для чувствительной кожи?"
        ]
    
    async def generate(self, product_data: Dict[str, Any], locale: str = 'ru', num_questions: int = 6) -> List[Dict[str, str]]:
        """
        Генерирует вдумчивые FAQ, используя весь контекст товара.
        ВСЕГДА генерирует на русском языке для максимального качества.
        
        Args:
            product_data: Полные данные о товаре из UnifiedParser
            locale: Локаль (игнорируется, всегда генерирует на русском)
            num_questions: Количество вопросов для генерации
            
        Returns:
            List[Dict[str, str]]: Список FAQ с вопросами и ответами на русском языке
        """
        try:
            logger.info(f"🔧 Генерация FAQ для {locale} с {num_questions} вопросами")
            
            # ✅ ПРОВЕРКА ФОРМАТА ДАННЫХ
            if not isinstance(product_data, dict):
                logger.error(f"❌ product_data должен быть dict, получен {type(product_data)}")
                
                # Если получили список характеристик - конвертируем в dict
                if isinstance(product_data, list):
                    logger.info(f"🔄 Конвертирую список характеристик в словарь")
                    product_data_dict = {}
                    for item in product_data:
                        if isinstance(item, dict):
                            if 'label' in item and 'value' in item:
                                product_data_dict[item['label']] = item['value']
                            elif 'key' in item and 'value' in item:
                                product_data_dict[item['key']] = item['value']
                    product_data = product_data_dict
                    logger.info(f"✅ Конвертировано в словарь: {len(product_data)} характеристик")
                else:
                    # Если формат вообще непонятный - прерываем с ошибкой
                    raise ValueError(f"Неподдерживаемый формат product_data: {type(product_data)}")
            
            # Собираем полный контекст для LLM
            context = self._build_context(product_data)
            
            # Создаем промпт для генерации качественных вопросов
            prompt = self._create_prompt(context, locale, num_questions)
            
            # ✅ Smart Routing: Передаём контекст для маршрутизации
            context = {
                'title': product_data.get('title', ''),
                'locale': locale,
                'type': 'faq'
            }
            
            # Используем SmartLLMClient с умной маршрутизацией и retry при null ответах
            for attempt in range(3):
                try:
                    system_prompt = "Ты эксперт по созданию качественных FAQ для товаров. Генерируй только JSON без дополнительного текста."
                    full_prompt = f"{system_prompt}\n\n{prompt}"
                    
                    response_text = await self.llm.generate(
                        prompt=full_prompt,
                        context=context,
                        max_tokens=1500,
                        temperature=0.7,
                        validate_content=True,  # ✅ ВКЛЮЧИТЬ ВАЛИДАЦИЮ
                        locale=locale  # ✅ Для валидации
                    )
                    
                    logger.info(f"🔍 DEBUG: LLM ответ для FAQ (попытка {attempt+1}): {response_text[:500]}...")
                    faq_list = self._parse_llm_response(response_text)
                    
                    # Проверка: нет ли null ответов
                    null_count = sum(1 for item in faq_list if not item.get('answer') or item.get('answer') == 'null')
                    
                    if null_count == 0 and faq_list and len(faq_list) >= 3:
                        logger.info(f"✅ LLM сгенерировал {len(faq_list)} качественных FAQ без null")
                        return self._post_process_faq(faq_list, locale)
                    
                    elif null_count < 3 and faq_list and len(faq_list) >= 3:
                        # Если null мало - заменяем placeholder
                        logger.warning(f"⚠️ {null_count} FAQ с null ответами, используем placeholder")
                        for item in faq_list:
                            if not item.get('answer') or item.get('answer') == 'null':
                                item['answer'] = (
                                    "Информация уточняется." 
                                    if locale == 'ru' 
                                    else "Інформація уточнюється."
                                )
                        logger.info(f"✅ FAQ исправлен с placeholder: {len(faq_list)} вопросов")
                        return self._post_process_faq(faq_list, locale)
                    
                    else:
                        # Если много null или мало FAQ - повторяем генерацию
                        logger.error(f"❌ Слишком много null ({null_count}) или мало FAQ ({len(faq_list) if faq_list else 0}), повтор {attempt+1}/3")
                        if attempt < 2:  # Не последняя попытка
                            continue
                        else:
                            # Последняя попытка - используем fallback
                            raise ValueError(f"Не удалось сгенерировать качественные FAQ после {attempt+1} попыток")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка LLM для FAQ (попытка {attempt+1}): {e}")
                    if attempt == 2:  # Последняя попытка
                        raise ValueError(f"Ошибка LLM генерации FAQ для {locale} после 3 попыток: {e}")
                    continue
            
            # Все попытки провалены
            raise ValueError(f"Не удалось сгенерировать FAQ после 3 попыток")
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка генерации FAQ: {e}")
            raise e  # Пробрасываем ошибку вместо возврата пустого списка
    
    def _build_context(self, data: Dict[str, Any]) -> str:
        """Собирает полный контекст товара для LLM"""
        context_parts = []
        
        # Название товара
        title = data.get('title', '') or data.get('title_ru', '') or data.get('title_ua', '')
        if title:
            context_parts.append(f"**Название:** {title}")
        
        # Описание
        description = data.get('description', '') or data.get('description_ru', '') or data.get('description_ua', '')
        if description:
            context_parts.append(f"**Описание:** {description}")
        
        # Характеристики
        specs = data.get('specs', {})
        if specs:
            if isinstance(specs, dict):
                specs_text = ', '.join([f'{k}: {v}' for k, v in specs.items()])
            else:
                specs_text = str(specs)
            context_parts.append(f"**Характеристики:** {specs_text}")
        
        # Состав набора
        bundle = data.get('bundle', []) or data.get('bundle_components', [])
        if bundle:
            bundle_text = ', '.join(bundle) if isinstance(bundle, list) else str(bundle)
            context_parts.append(f"**Состав набора:** {bundle_text}")
        
        # Дополнительная информация
        volume = data.get('volume', '')
        if volume:
            context_parts.append(f"**Объём:** {volume}")
        
        purpose = data.get('purpose', '')
        if purpose:
            context_parts.append(f"**Назначение:** {purpose}")
        
        return '\n'.join(context_parts)
    
    def _create_prompt(self, context: str, locale: str, num_questions: int) -> str:
        """Создает промпт для LLM"""
        if locale == 'ua':
            return f"""
На основі наданої інформації про товар, згенеруй {num_questions} вдумливих та корисних питань для FAQ.

**Контекст товару:**
{context}

**Вимоги до питань:**
1. **Глибина:** Питання повинні бути змістовними (наприклад, "Як довго триває ефект?", "Що робити при подразненні?", "Як правильно використовувати?").
2. **Релевантність:** Питання повинні бути безпосередньо пов'язані з типом товару (депіляція, догляд за шкірою тощо).
3. **Форматування:** Кожне питання повинно починатися з великої літери та закінчуватися знаком питання.
4. **Різноманітність:** Не генеруй прості питання, відповіді на які вже є в характеристиках (наприклад, "Який об'єм?").

**КРИТИЧНО ВАЖЛИВО:**
- КОЖНЕ питання ОБОВ'ЯЗКОВО повинно мати повну, розгорнуту відповідь
- НІКОЛИ не використовуй null, порожні рядки або placeholder у відповідях
- Якщо не впевнений у відповіді - використовуй загальну інформацію про тип товару
- Відповіді повинні бути конкретними та корисними (мінімум 2-3 речення)

**Формат виводу:**
Поверни список у форматі JSON, де кожен елемент — це об'єкт з ключами "question" та "answer".
Приклад: [{{"question": "Як довго триває ефект?", "answer": "Ефект може тривати від 3 до 6 тижнів залежно від індивідуальних особливостей та типу волосся. При регулярному використанні волосся стає тоншим та росте повільніше."}}, ...]

Генеруй тільки JSON, без додаткових коментарів.
"""
        else:
            return f"""
На основе предоставленной информации о товаре, сгенерируй {num_questions} вдумчивых и полезных вопросов для FAQ.

**Контекст товара:**
{context}

**Требования к вопросам:**
1. **Глубина:** Вопросы должны быть содержательными и практичными (например, "Как долго держится эффект?", "Что делать при раздражении?", "Как правильно использовать?", "Какие есть противопоказания?").
2. **Релевантность:** Вопросы должны быть напрямую связаны с типом товара и его применением (депиляция, уход за кожей и т.д.).
3. **Форматирование:** Каждый вопрос должен начинаться с большой буквы и заканчиваться вопросительным знаком.
4. **Разнообразие:** НЕ генерируй простые вопросы о характеристиках (объём, вес, состав) - они уже есть в описании. Фокусируйся на практическом применении, эффектах, безопасности, совместимости.
5. **Качество:** Каждый вопрос должен требовать развернутого ответа, основанного на фактах о товаре.

**КРИТИЧЕСКИ ВАЖНО:**
- КАЖДЫЙ вопрос ОБЯЗАТЕЛЬНО должен иметь полный, развёрнутый ответ
- НИКОГДА не используй null, пустые строки или placeholder в ответах
- Если не уверен в ответе - используй общую информацию о типе товара
- Ответы должны быть конкретными и полезными (минимум 2-3 предложения)

**Формат вывода:**
Верни список в формате JSON, где каждый элемент — это объект с ключами "question" и "answer".
Пример: [{{"question": "Как долго держится эффект?", "answer": "Эффект может держаться от 3 до 6 недель в зависимости от индивидуальных особенностей и типа волос. При регулярном использовании волосы становятся тоньше и растут медленнее."}}, ...]

Генерируй только JSON, без дополнительных комментариев.
"""
    
    def _parse_llm_response(self, response: str) -> List[Dict[str, str]]:
        """Парсит ответ LLM и извлекает FAQ"""
        try:
            # Очищаем ответ от возможных артефактов
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            
            # Парсим JSON
            parsed_response = json.loads(response)
            
            # Проверяем разные форматы ответа
            if isinstance(parsed_response, list):
                return parsed_response
            elif isinstance(parsed_response, dict):
                # Ищем FAQ в разных возможных ключах
                for key in ['faqs', 'faq', 'questions', 'items']:
                    if key in parsed_response and isinstance(parsed_response[key], list):
                        return parsed_response[key]
                # Если не нашли FAQ в ключах, возвращаем пустой список
                logger.warning(f"⚠️ LLM вернул объект без FAQ: {list(parsed_response.keys())}")
                return []
            else:
                logger.warning("⚠️ LLM вернул не список и не объект FAQ")
                return []
                
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Ошибка парсинга JSON от LLM: {e}")
            # Пытаемся извлечь FAQ вручную
            return self._extract_faq_from_text(response)
        except Exception as e:
            logger.error(f"❌ Ошибка обработки ответа LLM: {e}")
            return []
    
    def _extract_faq_from_text(self, text: str) -> List[Dict[str, str]]:
        """Извлекает FAQ из текста, если JSON не удалось распарсить"""
        faq_list = []
        
        # Ищем пары вопрос-ответ в тексте
        lines = text.split('\n')
        current_question = None
        current_answer = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Если строка заканчивается на ?, это вопрос
            if line.endswith('?'):
                if current_question and current_answer:
                    faq_list.append({
                        'question': current_question,
                        'answer': current_answer
                    })
                current_question = line
                current_answer = None
            # Иначе это может быть ответ
            elif current_question and not current_answer:
                current_answer = line
            elif current_question and current_answer:
                current_answer += ' ' + line
        
        # Добавляем последнюю пару
        if current_question and current_answer:
            faq_list.append({
                'question': current_question,
                'answer': current_answer
            })
        
        return faq_list
    
    def _post_process_faq(self, faq_list: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """Пост-обработка FAQ: исправляет форматирование"""
        processed = []
        
        for item in faq_list:
            if not isinstance(item, dict) or 'question' not in item or 'answer' not in item:
                continue
                
            question = str(item['question']).strip()
            answer = str(item['answer']).strip()
            
            if not question or not answer:
                continue
            
            # Исправляем форматирование вопроса
            question = question.capitalize()
            if not question.endswith('?'):
                question += '?'
            
            # Очищаем ответ
            answer = answer.strip()
            if answer:
                processed.append({
                    'question': question,
                    'answer': answer
                })
        
        return processed
    
    def _generate_hybrid_faq(self, product_data: Dict[str, Any], locale: str, num_questions: int) -> List[Dict[str, str]]:
        """❌ ЗАПРЕЩЕНО: Никаких заглушек! Только ошибка или LLM генерация"""
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать fallback FAQ с заглушками!")
        logger.error(f"❌ Это нарушение строгих правил - НИКАКИХ заглушек не должно быть!")
        
        # ВОЗВРАЩАЕМ ПУСТОЙ СПИСОК ВМЕСТО ЗАГЛУШЕК
        return []
    
    def _generate_answer_for_question(self, question: str, specs: Dict, bundle: List, locale: str) -> str:
        """❌ ЗАПРЕЩЕНО: Этот метод содержит заглушки и больше не используется"""
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать метод с заглушками!")
        raise ValueError("Использование заглушек запрещено!")
    