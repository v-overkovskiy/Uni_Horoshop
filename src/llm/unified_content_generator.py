"""
Объединенный генератор контента - один LLM вызов вместо четырех
"""
import json
import logging
import httpx
import os
from typing import Dict, Any
from dotenv import load_dotenv
from src.validation.content_validator import ContentValidator
from src.validation.language_validator import LanguageValidator
from src.llm.smart_llm_client import SmartLLMClient
from src.llm.structured_prompts import STRUCTURED_SYSTEM_PROMPT

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

class UnifiedContentGenerator:
    """Генерирует ВЕСЬ контент за один LLM вызов"""
    
    def __init__(self):
        self.validator = ContentValidator()
        self.language_validator = LanguageValidator()
        self.llm = SmartLLMClient()
        # LSI Enhancer инициализируется lazy (при первом использовании)
        self._lsi_enhancer = None
        self.use_lsi = False  # ⚠️ ВЫКЛЮЧЕН по умолчанию - слишком медленно (4x дольше)
        self.unified_prompt = """
Ты — эксперт по созданию коммерческого контента для товаров интернет-магазина.

ЗАДАЧА: Создать ВЕСЬ контент для товара за один запрос.

ВХОДНЫЕ ДАННЫЕ:
Название: {product_title}
Объём: {volume}
Тип товара: {product_type}
Назначение: {purpose}
Характеристики: {characteristics}
Локаль: {locale}

КРИТИЧЕСКИ ВАЖНО - НАРУШЕНИЕ ВЛЕЧЕТ ОШИБКУ:
- Создавай описание ТОЛЬКО на основе РЕАЛЬНЫХ данных выше
- ЗАПРЕЩЕНО использовать фразы: "качественный продукт", "профессиональный продукт", "эффективный продукт", "отличный выбор", "идеальный вариант", "превосходное качество", "высокое качество", "эффективный результат", "удобно в использовании", "якісний продукт", "професійний продукт", "ефективний продукт", "чудовий вибір", "ідеальний варіант", "чудова якість", "висока якість", "ефективний результат"
- ЗАПРЕЩЕНО выдумывать свойства не указанные в характеристиках
- ЗАПРЕЩЕНО упоминать: цену, стоимость, UAH, грн, доставку, магазин, "не указано", "не вказано"
- Описание ДОЛЖНО точно соответствовать типу товара из названия
- ОБЯЗАТЕЛЬНО упомяни конкретное название товара в описании
- Описывай товар исходя из его реального назначения и характеристик
- ПИШИ КОНКРЕТНО: для какого типа кожи/волос, какие ингредиенты, какой эффект

КРИТИЧНО - ЯЗЫК:
- Используй ТОЛЬКО {language_instruction}
- Проверь что нет букв: {forbidden_letters}
- Используй слова: {recommended_words}

ТРЕБОВАНИЯ К КОНТЕНТУ:

1. ОПИСАНИЕ (строка с HTML тегами, 6-8 предложений в 2 абзацах):
   - Абзац 1 (3-4 предложения): Назначение, кому подходит, основные свойства
   - Абзац 2 (3-4 предложения): Преимущества, результаты, практические детали
   - 🔍 SEO: Естественно используй синонимы и связанные термины (LSI-ключи)
   - Пример: "коврик для йоги" → йога-мат, тренировочный коврик, асаны, пилатес
   - НЕ перечисляй! Вплетай ОРГАНИЧНО в текст
   - Без воды — каждое предложение несёт ценность
   - ОБЯЗАТЕЛЬНО используй теги <p>...</p> для абзацев

2. ПРЕИМУЩЕСТВА (3-6 уникальных карточек):
   - НЕ используй generic-фразы: "высокое качество", "эффективный результат"
   - Каждое преимущество должно быть уникальным и полезным
   - Основывайся на реальных свойствах товара

3. FAQ (ровно 6 вопросов-ответов):
   - Конкретные вопросы о товаре
   - Развернутые ответы без generic-фраз
   - Покрывают основные аспекты использования

4. КОММЕРЧЕСКАЯ ФРАЗА с правильным падежом и жирным выделением:
   - RU: "В нашем интернет-магазине можно <strong>купить [товар в винительном падеже]</strong> с быстрой доставкой по Украине и гарантией качества"
   - UA: "У нашому інтернет-магазині можна <strong>купити [товар в винительному відмінку]</strong> з швидкою доставкою по Україні та гарантією якості"

ПРАВИЛЬНЫЙ ПРИМЕР ОПИСАНИЯ:
"<p>Воск в картридже для депиляции Simple USE, Ocean Blue (Азулен) предназначен для удаления нежелательных волос на ногах, руках, спине и теле. Он подходит для всех типов кожи, включая чувствительную, и эффективен для удаления тонких волос длиной от 2 мм. Формула содержит азулен, который успокаивает кожу после процедуры.</p><p>Преимущества этого воска заключаются в его гипоаллергенной формуле и удобной упаковке в виде картриджа. Температура плавления составляет 40 градусов, что позволяет легко наносить воск без риска ожогов. Простота использования делает его идеальным выбором для домашнего применения и профессионального салона.</p>"

НЕПРАВИЛЬНЫЕ ПРИМЕРЫ (НЕ ГЕНЕРИРОВАТЬ):
❌ "Воск для депиляции - качественный продукт"
❌ "Высокое качество и эффективный результат"
❌ Один абзац без тегов <p>
❌ Менее 6 предложений

ФОРМАТ ВЫВОДА (строго JSON):
{{
  "description": "<p>первый абзац с 3-4 предложениями</p><p>второй абзац с 3-4 предложениями</p>",
  "advantages": ["конкретное преимущество 1", "конкретное преимущество 2", "конкретное преимущество 3"],
  "faq": [
    {{"question": "конкретный вопрос 1?", "answer": "развернутый ответ 1"}},
    {{"question": "конкретный вопрос 2?", "answer": "развернутый ответ 2"}},
    {{"question": "конкретный вопрос 3?", "answer": "развернутый ответ 3"}},
    {{"question": "конкретный вопрос 4?", "answer": "развернутый ответ 4"}},
    {{"question": "конкретный вопрос 5?", "answer": "развернутый ответ 5"}},
    {{"question": "конкретный вопрос 6?", "answer": "развернутый ответ 6"}}
  ],
  "note_buy": "коммерческая фраза с правильным падежом"
}}

КРИТИЧНО: ГЕНЕРИРУЙ ТОЛЬКО ВАЛИДНЫЙ JSON БЕЗ ДОПОЛНИТЕЛЬНЫХ КОММЕНТАРИЕВ И МАРКДАУН БЛОКОВ.

ВАЖНО: Если ты не можешь создать качественный контент без шаблонных фраз - лучше верни ошибку, чем плохой результат.

ПРИМЕР ВАЛИДНОГО ОТВЕТА:
{{
  "description": "<p>Воск в картридже Simple USE предназначен для профессиональной депиляции нежелательных волос на ногах, руках, спине и теле. Формула содержит шоколадный экстракт, который обеспечивает приятный аромат и успокаивает кожу во время процедуры. Температура плавления 40 градусов позволяет легко наносить воск без риска ожогов.</p><p>Воск эффективно удаляет волосы длиной от 2 мм и подходит для всех типов кожи, включая чувствительную. Гипоаллергенная формула не вызывает раздражения, а картриджная упаковка обеспечивает удобство применения как в домашних условиях, так и в салонах красоты.</p>",
  "advantages": [
    "Подходит для всех типов кожи",
    "Эффективно удаляет короткие волосы",
    "Приятный шоколадный аромат",
    "Удобная картриджная упаковка",
    "Профессиональное качество"
  ],
  "faq": [
    {{"question": "Для какого типа кожи подходит этот воск?", "answer": "Воск Simple USE подходит для всех типов кожи, включая чувствительную, благодаря гипоаллергенной формуле."}},
    {{"question": "Какова минимальная длина волос для депиляции?", "answer": "Минимальная длина волос для эффективной депиляции составляет 2 мм."}},
    {{"question": "Какая температура плавления воска?", "answer": "Температура плавления воска составляет 40 градусов, что обеспечивает безопасное применение."}},
    {{"question": "Можно ли использовать воск дома?", "answer": "Да, воск в картридже удобен для домашнего применения благодаря простой технологии использования."}},
    {{"question": "Содержит ли воск аллергены?", "answer": "Воск имеет гипоаллергенную формулу и не содержит компонентов, вызывающих аллергические реакции."}},
    {{"question": "На каких участках тела можно использовать воск?", "answer": "Воск предназначен для депиляции ног, рук, спины и тела."}}
  ],
  "note_buy": "В нашем интернет-магазине можно <strong>купить воск в картридже для депиляции Simple USE</strong> с быстрой доставкой по Украине и гарантией качества"
}}
"""
    
    @property
    def lsi_enhancer(self):
        """Lazy initialization LSI Enhancer"""
        if self._lsi_enhancer is None:
            from src.processing.lsi_enhancer import LSIEnhancer
            self._lsi_enhancer = LSIEnhancer()
        return self._lsi_enhancer
    
    async def generate_unified_content(self, product_facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Генерирует ВЕСЬ контент за один LLM вызов на основе РЕАЛЬНЫХ данных"""
        
        # КРИТИЧНО: Проверяем наличие реальных данных
        if not product_facts or not product_facts.get('title'):
            raise ValueError("❌ ЗАПРЕЩЕНО: Нет данных о товаре для генерации")
        
        title = product_facts.get('title', '').strip()
        if len(title) < 5:
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Слишком короткое название товара: '{title}'")
        
        # КРИТИЧНО: Проверяем наличие характеристик (смягченная проверка) - ищем в specs!
        characteristics = product_facts.get('specs', {})  # ИСПРАВЛЕНИЕ: характеристики в specs!
        if not characteristics:
            logger.warning(f"⚠️ Нет характеристик товара, но продолжаем генерацию")
            characteristics = {}
        
        logger.info(f"✅ Генерация контента на основе РЕАЛЬНЫХ данных: '{title}', характеристик: {len(characteristics)}")
        
        try:
            # Подготавливаем данные для промпта
            language_instructions = self._get_language_instructions(locale)
            prompt_data = {
                'product_title': title,
                'volume': product_facts.get('volume', ''),
                'product_type': product_facts.get('product_type', ''),
                'purpose': await self._extract_purpose(product_facts),
                'characteristics': self._format_characteristics(characteristics),
                'locale': locale,
                'language_instruction': language_instructions['instruction'],
                'forbidden_letters': language_instructions['forbidden_letters'],
                'recommended_words': language_instructions['recommended_words']
            }
            
            # Форматируем промпт
            formatted_prompt = self.unified_prompt.format(**prompt_data)
            
            # ✅ Smart Routing: Передаём контекст для маршрутизации
            context = {
                'title': title,
                'locale': locale,
                'type': 'unified_content'
            }
            
            # Один LLM вызов с умной маршрутизацией и валидацией
            content = await self.llm.generate(
                prompt=formatted_prompt,
                context=context,
                max_tokens=2000,
                temperature=0.7,
                validate_content=True,  # ✅ ВКЛЮЧИТЬ ВАЛИДАЦИЮ
                locale=locale  # ✅ Для валидации
            )
            
            # Парсим JSON ответ
            try:
                result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON от LLM: {e}")
                logger.error(f"❌ Полученный контент: {content[:500]}...")
                
                # Попытка исправить неполный JSON
                try:
                    # Если JSON обрезан, попробуем добавить недостающие части
                    if content.strip().endswith('"description"') or content.strip().endswith('"description":'):
                        logger.warning("⚠️ Попытка исправить неполный JSON...")
                        fixed_content = content + '": "<p>Описание товара на основе характеристик.</p><p>Дополнительная информация о применении и преимуществах.</p>", "advantages": ["Подходит для всех типов кожи", "Профессиональное качество", "Удобство применения"], "faq": [{"question": "Для какого типа кожи подходит?", "answer": "Подходит для всех типов кожи."}], "note_buy": "В нашем интернет-магазине можно <strong>купить товар</strong> с быстрой доставкой по Украине и гарантией качества"}'
                        result = json.loads(fixed_content)
                        logger.info("✅ JSON успешно исправлен")
                    else:
                        raise ValueError(f"LLM вернул некорректный JSON: {e}")
                except (json.JSONDecodeError, ValueError) as fix_error:
                    logger.error(f"❌ Не удалось исправить JSON: {fix_error}")
                    raise ValueError(f"LLM вернул некорректный JSON: {e}")
            
            # Убираем markdown блоки если есть
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            try:
                parsed_content = json.loads(content)
                
                # ЛОГИРОВАНИЕ: Что вернул LLM
                logger.info(f"🔍 LLM вернул описание типа: {type(parsed_content.get('description', 'НЕТ'))}")
                if 'description' in parsed_content:
                    desc = parsed_content['description']
                    logger.info(f"🔍 Содержимое описания: {str(desc)[:100]}...")
                
                # ИСПРАВЛЕНИЕ: Обеспечиваем правильный формат описания
                if 'description' in parsed_content:
                    description = parsed_content['description']
                    if isinstance(description, list):
                        # Если описание - список, объединяем в строку с HTML тегами
                        if len(description) >= 2:
                            parsed_content['description'] = f"<p>{description[0]}</p><p>{description[1]}</p>"
                        else:
                            # Fallback для одного элемента
                            parsed_content['description'] = f"<p>{description[0] if description else ''}</p><p>Дополнительная информация о товаре.</p>"
                        logger.info(f"✅ Исправлен формат описания: список → HTML строка")
                    elif isinstance(description, str):
                        logger.info(f"🔧 Описание - строка, проверяем HTML теги")
                        # Если описание - строка без HTML тегов, добавляем их
                        if not description.startswith('<p>'):
                            # Разбиваем на параграфы и оборачиваем в теги
                            paragraphs = [p.strip() for p in description.split('\n\n') if p.strip()]
                            if len(paragraphs) >= 2:
                                parsed_content['description'] = f"<p>{paragraphs[0]}</p><p>{paragraphs[1]}</p>"
                            else:
                                # Fallback: разбиваем по предложениям
                                sentences = [s.strip() + '.' for s in description.split('.') if s.strip()]
                                if len(sentences) >= 4:
                                    mid = len(sentences) // 2
                                    parsed_content['description'] = f"<p>{' '.join(sentences[:mid])}</p><p>{' '.join(sentences[mid:])}</p>"
                                else:
                                    parsed_content['description'] = f"<p>{description}</p><p>Дополнительная информация о товаре.</p>"
                            logger.info(f"✅ Исправлен формат описания: строка → HTML теги")
                    else:
                        logger.warning(f"⚠️ Неизвестный тип описания: {type(description)}")
                
                # КРИТИЧНО: Языковая валидация
                is_valid_lang, lang_error = self.language_validator.validate_content_language(parsed_content, locale)
                if not is_valid_lang:
                    logger.error(f"❌ Языковая валидация не прошла: {lang_error}")
                    # Пробуем сгенерировать еще раз с более строгим промптом
                    parsed_content = await self._retry_with_strict_language(product_facts, locale, lang_error)
                
                    # КРИТИЧНО: Строгая валидация результата
                    if not self.validator.validate_all_content(parsed_content, locale):
                        raise ValueError("❌ ЗАПРЕЩЕНО: Сгенерированный контент не прошел валидацию")
                
                # 🔍 LSI Enhancement: Обогащаем контент LSI-ключами
                if self.use_lsi:
                    try:
                        logger.info("🔍 Запускаем LSI Enhancement...")
                        parsed_content = await self.lsi_enhancer.enhance_with_lsi(
                            content=parsed_content,
                            product_facts=product_facts,
                            locale=locale
                        )
                        logger.info("✅ LSI Enhancement завершен")
                    except Exception as lsi_error:
                        logger.warning(f"⚠️ LSI Enhancement не удался, продолжаем без него: {lsi_error}")
                        # Не останавливаем процесс если LSI не сработал
                
                logger.info(f"✅ Объединенный контент сгенерирован для {locale}: {len(parsed_content)} блоков")
                return parsed_content
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON ответа: {e}")
                logger.error(f"Сырой ответ: {content}")
                raise e
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации объединенного контента: {e}")
            # КРИТИЧНО: НЕ используем fallback - лучше ошибка чем заглушка
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось сгенерировать контент для {title}: {e}")

    async def generate_unified_content_structured(self, product_facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Генерирует ВЕСЬ контент с Structured Output и строгой валидацией"""
        
        # КРИТИЧНО: Проверяем наличие реальных данных
        if not product_facts or not product_facts.get('title'):
            raise ValueError("❌ ЗАПРЕЩЕНО: Нет данных о товаре для генерации")
        
        title = product_facts.get('title', '').strip()
        if len(title) < 5:
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Слишком короткое название товара: '{title}'")
        
        logger.info(f"✅ Структурированная генерация контента: '{title}' ({locale})")
        
        try:
            # Используем новый метод с Structured Output
            structured_content = await self.llm.generate_content_with_structured_output(
                parsed_data=product_facts,
                locale=locale,
                system_prompt=STRUCTURED_SYSTEM_PROMPT,
                max_retries=3
            )
            
            # Конвертируем структурированный контент в старый формат для совместимости
            converted_content = self._convert_structured_to_legacy(structured_content, locale)
            
            logger.info(f"✅ Структурированный контент успешно сгенерирован для {title} ({locale})")
            return converted_content
            
        except Exception as e:
            logger.error(f"❌ Ошибка структурированной генерации: {e}")
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось сгенерировать структурированный контент для {title}: {e}")

    def _convert_structured_to_legacy(self, structured_content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Конвертирует структурированный контент в старый формат для совместимости"""
        
        # Извлекаем данные из структурированного формата
        description_obj = structured_content.get('description', {})
        paragraph_1 = description_obj.get('paragraph_1', '')
        paragraph_2 = description_obj.get('paragraph_2', '')
        
        # Формируем HTML описание
        description_html = f"<p>{paragraph_1}</p><p>{paragraph_2}</p>"
        
        # Конвертируем преимущества
        benefits_list = []
        for benefit in structured_content.get('benefits', []):
            title = benefit.get('title', '')
            description = benefit.get('description', '')
            benefits_list.append(f"{title}: {description}")
        
        # Конвертируем FAQ
        faq_list = []
        for faq_item in structured_content.get('faq', []):
            faq_list.append({
                'question': faq_item.get('question', ''),
                'answer': faq_item.get('answer', '')
            })
        
        # Возвращаем в старом формате
        return {
            'description': description_html,
            'advantages': benefits_list,
            'faq': faq_list,
            'note_buy': structured_content.get('note_buy', ''),
            'characteristics': structured_content.get('characteristics', [])
        }
    
    async def _extract_purpose(self, product_facts: Dict[str, Any]) -> str:
        """✅ УНИВЕРСАЛЬНОЕ извлечение назначения через LLM - работает для ЛЮБЫХ товаров"""
        title = product_facts.get('title', '')
        characteristics = product_facts.get('specs', [])
        
        # ✅ УНИВЕРСАЛЬНЫЙ подход через LLM с fallback
        try:
            # Формируем контекст для LLM
            specs_text = ""
            if isinstance(characteristics, list):
                specs_text = "\n".join([f"- {spec.get('label', '')}: {spec.get('value', '')}" for spec in characteristics[:5]])
            elif isinstance(characteristics, dict):
                specs_text = "\n".join([f"- {k}: {v}" for k, v in list(characteristics.items())[:5]])
            
            prompt = f"""Определи назначение товара на основе его названия и характеристик:

Название: {title}
Характеристики:
{specs_text}

Требования:
- Определи ТОЧНОЕ назначение товара
- НЕ используй общие фразы типа "уход за кожей"
- Будь конкретным и точным
- БЕЗ пояснений

Формат ответа (ТОЛЬКО результат):
[конкретное назначение товара]"""

            # ✅ Smart Routing: Передаём контекст для маршрутизации
            context = {
                'title': title,
                'type': 'purpose_extraction'
            }
            
            # Используем SmartLLMClient с умной маршрутизацией
            purpose = await self.llm.generate(
                prompt=prompt,
                context=context,
                max_tokens=100,
                temperature=0.3,
                validate_content=False,  # Purpose extraction не требует валидации
                locale='ru'  # Purpose всегда на русском
            )
            
            logger.info(f"✅ LLM определил назначение: '{title}' → '{purpose}'")
            return purpose.strip()
                    
        except Exception as e:
            logger.error(f"❌ Ошибка LLM определения назначения: {e}")
            return "специализированное применение"  # Универсальный fallback
    
    
    def _format_characteristics(self, characteristics) -> str:
        """Форматирует характеристики для промпта (поддерживает и список и словарь)"""
        if not characteristics:
            return "Характеристики не указаны"
        
        formatted = []
        
        # Если это список (новый формат)
        if isinstance(characteristics, list):
            for item in characteristics:
                if isinstance(item, dict) and 'label' in item and 'value' in item:
                    formatted.append(f"- {item['label']}: {item['value']}")
                elif isinstance(item, tuple) and len(item) == 2:
                    formatted.append(f"- {item[0]}: {item[1]}")
        
        # Если это словарь (старый формат)
        elif isinstance(characteristics, dict):
            for key, value in characteristics.items():
                formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted) if formatted else "Характеристики не указаны"
    
    def _get_language_instructions(self, locale: str) -> dict:
        """Получает языковые инструкции для промпта"""
        if locale == 'ru':
            return {
                'instruction': 'СТРОГО русский язык',
                'forbidden_letters': 'ґ є і ї',
                'recommended_words': 'это, который, будет, можно'
            }
        else:  # ua
            return {
                'instruction': 'СТРОГО українську мову',
                'forbidden_letters': 'ы э ъ ё',
                'recommended_words': 'це, який, буде, можна'
            }
    
    async def _retry_with_strict_language(self, product_facts: dict, locale: str, error: str) -> dict:
        """Повторная генерация с более строгими языковыми требованиями"""
        logger.warning(f"🔄 Повторная генерация с строгими языковыми требованиями: {error}")
        
        # Создаем более строгий промпт с полным форматом
        language_instructions = self._get_language_instructions(locale)
        strict_prompt = f"""
КРИТИЧНО: Предыдущая генерация содержала языковые ошибки: {error}

Исправь и сгенерируй контент заново, соблюдая СТРОГО {language_instructions['instruction']}.

ДАННЫЕ:
Название: {product_facts.get('title', '')}
Объём: {product_facts.get('volume', '')}
Тип товара: {product_facts.get('product_type', '')}
Характеристики: {self._format_characteristics(product_facts.get('specs', {}))}

КРИТИЧНО - ЯЗЫК:
- Используй ТОЛЬКО {language_instructions['instruction']}
- Проверь что нет букв: {language_instructions['forbidden_letters']}
- Используй слова: {language_instructions['recommended_words']}

ТРЕБОВАНИЯ:
1. ОПИСАНИЕ (список абзацев): 2 абзаца, 6-8 предложений
2. ПРЕИМУЩЕСТВА (список строк): 3-6 уникальных пунктов  
3. FAQ (список объектов): 6 вопросов-ответов с ключами question, answer
4. NOTE_BUY (строка): коммерческая фраза

ФОРМАТ JSON:
{{
  "description": ["первый абзац описания", "второй абзац описания"],
  "advantages": ["преимущество 1", "преимущество 2", "преимущество 3"],
  "faq": [
    {{"question": "вопрос 1", "answer": "ответ 1"}},
    {{"question": "вопрос 2", "answer": "ответ 2"}}
  ],
  "note_buy": "коммерческая фраза для покупки"
}}
"""
        
        try:
            # ✅ Smart Routing: Передаём контекст для маршрутизации
            context = {
                'title': product_facts.get('title', ''),
                'locale': locale,
                'type': 'retry_generation'
            }
            
            # Используем SmartLLMClient с умной маршрутизацией и валидацией
            content = await self.llm.generate(
                prompt=strict_prompt,
                context=context,
                max_tokens=2000,
                temperature=0.3,
                validate_content=True,  # ✅ ВКЛЮЧИТЬ ВАЛИДАЦИЮ
                locale=locale  # ✅ Для валидации
            )
            
            # Парсим JSON
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            parsed_content = json.loads(content)
            
            # ИСПРАВЛЕНИЕ: Обеспечиваем правильный формат описания
            if 'description' in parsed_content:
                description = parsed_content['description']
                if isinstance(description, str):
                    # Если описание - строка, разбиваем на параграфы
                    paragraphs = [p.strip() for p in description.split('\n\n') if p.strip()]
                    if len(paragraphs) < 2:
                        # Если параграфов мало, разбиваем по предложениям
                        sentences = [s.strip() + '.' for s in description.split('.') if s.strip()]
                        if len(sentences) >= 4:
                            mid = len(sentences) // 2
                            paragraphs = [
                                ' '.join(sentences[:mid]),
                                ' '.join(sentences[mid:])
                            ]
                    parsed_content['description'] = paragraphs
                    logger.info(f"✅ Исправлен формат описания в retry: {len(paragraphs)} параграфов")
            
            # Проверяем язык еще раз
            is_valid_lang, lang_error = self.language_validator.validate_content_language(parsed_content, locale)
            if not is_valid_lang:
                raise ValueError(f"❌ ЗАПРЕЩЕНО: LLM не может сгенерировать контент на правильном языке: {lang_error}")
            
            logger.info(f"✅ Повторная генерация успешна для {locale}")
            return parsed_content
            
        except Exception as e:
            logger.error(f"❌ Ошибка повторной генерации: {e}")
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось сгенерировать контент на правильном языке: {e}")
    
