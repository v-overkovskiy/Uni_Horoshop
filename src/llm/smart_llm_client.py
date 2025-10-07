"""
Smart LLM Router для оптимизации затрат на API
Автоматически выбирает оптимальную LLM для каждого товара
"""

import os
import logging
import asyncio
from typing import Optional, Dict, List
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from src.validation.content_validator import ContentValidator
from src.llm.schemas import PRODUCT_CONTENT_SCHEMA

load_dotenv()
logger = logging.getLogger(__name__)

class SmartLLMClient:
    """
    Интеллектуальный клиент с умной маршрутизацией
    
    Стратегия:
    - GPT-4o-mini для стандартных товаров (быстро, дёшево)
    - Claude 3.5 Sonnet для проблемных товаров (надёжно, дорого)
    """
    
    # Ключевые слова для определения проблемных товаров
    SENSITIVE_KEYWORDS = {
        'ru': [
            'депиляция', 'депиляци', 'воск', 'восковая',
            'удаление волос', 'эпиляция', 'эпиляци',
            'интим', 'бикини', 'шугаринг'
        ],
        'ua': [
            'депіляція', 'депіляці', 'віск', 'воскова',
            'видалення волосся', 'епіляція', 'епіляці',
            'інтим', 'бікіні', 'шугарінг'
        ]
    }
    
    # Цены за 1M токенов (USD)
    PRICING = {
        'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
        'claude-3.5-sonnet': {'input': 3.00, 'output': 15.00}
    }
    
    def __init__(self):
        """Инициализация клиентов LLM"""
        
        # Клиенты
        self.openai = AsyncOpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.claude = AsyncAnthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
        
        # Настройки - ОТКЛЮЧАЕМ smart routing, все товары идут на OpenAI
        self.smart_routing_enabled = False  # Принудительно отключено - все на OpenAI
        self.cost_tracking_enabled = os.getenv('COST_TRACKING_ENABLED', 'true').lower() == 'true'
        
        # Расширенный blacklist шаблонных фраз
        self.template_blacklist_ru = [
            'качественный продукт',
            'высокое качество',
            'профессиональный уход',
            'отличный выбор',
            'идеально подходит',
            'обеспечивает эффективный результат',
            'разработан с учетом особенностей',
            'эффективный продукт',
            'профессиональный продукт',
            'превосходное качество',
            'идеальный вариант',
            'удобно в использовании'
        ]
        
        self.template_blacklist_ua = [
            'якісний продукт',
            'висока якість',
            'професійний догляд',
            'чудовий вибір',
            'ідеально підходить',
            'забезпечує ефективний результат',
            'розроблений з урахуванням особливостей',
            'ефективний продукт',
            'професійний продукт',
            'чудова якість',
            'ідеальний варіант',
            'зручно у використанні'
        ]
        
        # Статистика
        self.stats = {
            'openai_calls': 0,
            'openai_tokens': {'input': 0, 'output': 0},
            'openai_cost': 0.0,
            'openai_failed': 0,
            
            'claude_calls': 0,
            'claude_tokens': {'input': 0, 'output': 0},
            'claude_cost': 0.0,
            'claude_failed': 0,
            
            'total_requests': 0,
            'total_cost': 0.0
        }
        
        logger.info(f"🤖 SmartLLMClient initialized")
        logger.info(f"   Smart Routing: {'✅ Enabled' if self.smart_routing_enabled else '❌ Disabled'}")
        logger.info(f"   Cost Tracking: {'✅ Enabled' if self.cost_tracking_enabled else '❌ Disabled'}")

    async def generate(
        self,
        prompt: str,
        context: Optional[Dict] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        force_provider: Optional[str] = None,
        validate_content: bool = True,  # ✅ НОВОЕ
        locale: str = 'ru'  # ✅ НОВОЕ для валидации
    ) -> str:
        """
        Умная генерация с ВАЛИДАЦИЕЙ и FALLBACK
        
        Логика:
        1. Пробуем primary LLM (OpenAI или по smart routing)
        2. ВАЛИДИРУЕМ результат
        3. Если провал валидации → fallback на Claude
        4. Если Claude тоже провалился → возвращаем ошибку
        """
        
        self.stats['total_requests'] += 1
        
        # Определяем primary provider
        if force_provider:
            primary_provider = force_provider
        else:
            primary_provider = self._route_request(context)
        
        # ═════════════════════════════════════════════════════════
        # ПОПЫТКА 1: PRIMARY LLM
        # ═════════════════════════════════════════════════════════
        
        try:
            logger.info(f"🔵 Primary attempt: {primary_provider}")
            
            if primary_provider == 'claude':
                content = await self._generate_claude(prompt, max_tokens, temperature)
            else:
                content = await self._generate_openai(prompt, max_tokens, temperature)
            
            # ✅ НОВОЕ: ВАЛИДАЦИЯ контента
            if validate_content:
                is_valid = self._validate_generated_content(content, locale)
                
                if not is_valid:
                    logger.warning(f"⚠️ {primary_provider} ПРОВАЛ ВАЛИДАЦИИ!")
                    raise ValueError(f"{primary_provider} content validation failed")
            
            # Контент валидный!
            self._track_usage(primary_provider, prompt, content)
            logger.info(f"✅ {primary_provider} SUCCESS")
            
            return content
        
        except Exception as e:
            logger.error(f"❌ {primary_provider} failed: {e}")
            self.stats[f'{primary_provider}_failed'] += 1
        
        # ═════════════════════════════════════════════════════════
        # ПОПЫТКА 2: FALLBACK НА CLAUDE
        # ═════════════════════════════════════════════════════════
        
        if primary_provider != 'claude':  # Если primary не Claude
            try:
                logger.info(f"🟣 FALLBACK → Claude")
                
                content = await self._generate_claude(prompt, max_tokens, temperature)
                
                # Валидация Claude
                if validate_content:
                    is_valid = self._validate_generated_content(content, locale)
                    
                    if not is_valid:
                        logger.error(f"🚫 Claude ТОЖЕ провал валидации!")
                        raise ValueError("Claude content validation failed")
                
                # Claude справился!
                self._track_usage('claude', prompt, content)
                logger.info(f"✅ Claude FALLBACK SUCCESS")
                
                return content
            
            except Exception as e:
                logger.error(f"❌ Claude fallback failed: {e}")
                self.stats['claude_failed'] += 1
        
        # ═════════════════════════════════════════════════════════
        # ОБЕ LLM ПРОВАЛИЛИСЬ
        # ═════════════════════════════════════════════════════════
        
        logger.error(f"🚫 ВСЕ LLM ПРОВАЛИЛИСЬ для prompt: {prompt[:100]}...")
        raise Exception("All LLMs failed validation")

    def _validate_generated_content(self, content: str, locale: str) -> bool:
        """
        Валидация сгенерированного контента
        
        Returns:
            True если контент валидный, False если провал
        """
        
        # Простая валидация на уровне SmartLLMClient
        # (детальная валидация будет в ContentValidator)
        
        content_lower = content.lower()
        
        # 1. Проверка на шаблоны
        template_phrases = ContentValidator.TEMPLATE_PHRASES.get(locale, [])
        for phrase in template_phrases:
            if phrase in content_lower:
                logger.warning(f"⚠️ Валидация: найден шаблон '{phrase}'")
                return False
        
        # 2. Проверка на запрещённый контент
        for forbidden in ContentValidator.FORBIDDEN_CONTENT:
            if forbidden in content_lower:
                logger.warning(f"⚠️ Валидация: найдено запрещённое '{forbidden}'")
                return False
        
        # 3. Минимальная длина
        if len(content) < 50:
            logger.warning(f"⚠️ Валидация: слишком короткий контент ({len(content)} символов)")
            return False
        
        return True

    def _route_request(self, context: Optional[Dict]) -> str:
        """
        Умная маршрутизация запроса
        
        Логика:
        - Проблемные товары (депиляция и т.д.) → Claude
        - Стандартные товары → GPT-4o-mini
        
        Args:
            context: Контекст товара с полями 'title', 'category' и т.д.
        
        Returns:
            'openai' или 'claude'
        """
        
        if not self.smart_routing_enabled:
            return 'openai'
        
        if not context:
            return 'openai'
        
        # Проверяем название товара
        title = context.get('title', '').lower()
        category = context.get('category', '').lower()
        
        # Объединяем все текстовые поля для анализа
        text_to_check = f"{title} {category}".lower()
        
        # Проверяем на триггерные слова
        all_keywords = self.SENSITIVE_KEYWORDS['ru'] + self.SENSITIVE_KEYWORDS['ua']
        
        for keyword in all_keywords:
            if keyword in text_to_check:
                logger.info(f"🟣 Sensitive product detected ('{keyword}') → Claude 3.5 Sonnet")
                return 'claude'
        
        # Стандартный товар
        logger.info("🔵 Standard product → GPT-4o-mini")
        return 'openai'

    async def _generate_openai(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Генерация через GPT-4o-mini"""
        
        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional e-commerce copywriter specializing in product descriptions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        content = response.choices[0].message.content
        return content.strip()

    async def _generate_claude(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> str:
        """Генерация через Claude с автоматическим выбором доступной модели"""
        
        # Список моделей для попытки (от лучшей к худшей) - только работающие
        claude_models = [
            "claude-3-haiku-20240307",     # Единственная работающая модель
        ]
        
        for model in claude_models:
            try:
                logger.info(f"🔍 Trying Claude model: {model}")
                
                response = await self.claude.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                
                logger.info(f"✅ Claude model {model} works!")
                content = response.content[0].text
                return content.strip()
                
            except Exception as e:
                logger.warning(f"⚠️ Claude model {model} failed: {e}")
                continue
        
        # Если ни одна модель не сработала
        raise Exception("❌ No working Claude model found")

    async def generate_content_with_structured_output(
        self,
        parsed_data: dict,
        locale: str,
        system_prompt: str,
        max_retries: int = 3
    ) -> dict:
        """Генерация с Structured Output и retry логикой"""
        
        # Создаём user prompt с данными
        user_prompt = self._create_user_prompt(parsed_data, locale)
        
        for attempt in range(max_retries):
            try:
                # ПОПЫТКА 1-2: OpenAI GPT-4o-mini с Structured Output
                if attempt < 2:
                    content = await self._generate_with_openai_structured(
                        system_prompt, 
                        user_prompt, 
                        locale,
                        strict_mode=(attempt == 1)  # Вторая попытка с усиленным промптом
                    )
                # ПОПЫТКА 3: Claude Sonnet как fallback
                else:
                    content = await self._generate_with_claude_structured(
                        system_prompt,
                        user_prompt,
                        locale
                    )
                
                # Валидация результата
                is_valid, errors = self._validate_structured_content(content, locale)
                
                if is_valid:
                    return content
                else:
                    logger.warning(f"Attempt {attempt+1} failed validation: {errors}")
                    
            except Exception as e:
                logger.error(f"Attempt {attempt+1} error: {str(e)}")
                if attempt == max_retries - 1:
                    raise
        
        raise Exception("All attempts failed")

    async def _generate_with_openai_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        locale: str,
        strict_mode: bool = False
    ) -> dict:
        """OpenAI генерация с JSON Schema"""
        
        # Усиленный промпт для второй попытки
        if strict_mode:
            system_prompt = self._add_strict_warnings(system_prompt, locale)
        
        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "product_content",
                    "strict": True,
                    "schema": PRODUCT_CONTENT_SCHEMA
                }
            },
            temperature=0.3,  # Снижаем креативность для стабильности
            max_tokens=2000
        )
        
        import json
        return json.loads(response.choices[0].message.content)

    async def _generate_with_claude_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        locale: str
    ) -> dict:
        """Claude генерация с JSON Schema (fallback)"""
        
        # Усиленный промпт для Claude
        system_prompt = self._add_strict_warnings(system_prompt, locale)
        
        response = await self.claude.messages.create(
            model="claude-3-haiku-20240307",  # Используем доступную модель
            max_tokens=2000,
            temperature=0.3,
            messages=[
                {"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}
            ]
        )
        
        import json
        content = response.content[0].text
        
        # Claude не поддерживает structured output, парсим JSON
        try:
            # Убираем возможные markdown блоки
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Claude JSON parsing error: {e}")
            raise

    def _add_strict_warnings(self, system_prompt: str, locale: str) -> str:
        """Добавляет критические предупреждения для повторных попыток"""
        
        blacklist = (
            self.template_blacklist_ru if locale == 'ru' 
            else self.template_blacklist_ua
        )
        
        warnings = f"""

⚠️⚠️⚠️ КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ ⚠️⚠️⚠️

Предыдущая попытка провалена. ОБЯЗАТЕЛЬНО исправь:

1. ЗАПРЕЩЁННЫЕ ФРАЗЫ (автоматический reject):
{chr(10).join(f'   ❌ "{phrase}"' for phrase in blacklist)}

2. СТРУКТУРА ОПИСАНИЯ:
   ✅ ТОЧНО 2 параграфа (paragraph_1 И paragraph_2)
   ✅ 6-10 предложений ВСЕГО (3-5 в каждом)
   ✅ Только ФАКТЫ из исходных данных

3. FAQ:
   ✅ ОБЯЗАТЕЛЬНО 4-6 вопросов
   ✅ Каждый вопрос основан на характеристиках

4. ЯЗЫК:
   {'✅ НЕТ букв: і, ї, є, ґ' if locale == 'ru' else '✅ НЕТ букв: ы, э, ъ, ё'}

ЕСЛИ НЕ ИСПРАВИШЬ → ОТКЛОНЕНО
"""
        return system_prompt + warnings

    def _validate_structured_content(self, content: dict, locale: str) -> tuple[bool, list]:
        """Жёсткая валидация сгенерированного контента"""
        errors = []
        
        # 1. Проверка описания
        desc = content.get('description', {})
        p1 = desc.get('paragraph_1', '')
        p2 = desc.get('paragraph_2', '')
        
        # Считаем предложения
        sentences_p1 = len([s for s in p1.split('.') if s.strip()])
        sentences_p2 = len([s for s in p2.split('.') if s.strip()])
        total_sentences = sentences_p1 + sentences_p2
        
        if not (6 <= total_sentences <= 10):
            errors.append(f"Описание: {total_sentences} предложений (нужно 6-10)")
        
        # 2. Проверка на шаблоны
        blacklist = (
            self.template_blacklist_ru if locale == 'ru' 
            else self.template_blacklist_ua
        )
        
        import json
        full_text = json.dumps(content, ensure_ascii=False).lower()
        for phrase in blacklist:
            if phrase.lower() in full_text:
                errors.append(f"Шаблонная фраза: '{phrase}'")
        
        # 3. Проверка языковой чистоты
        if locale == 'ru':
            forbidden_chars = {'і', 'ї', 'є', 'ґ'}
            if any(char in full_text for char in forbidden_chars):
                errors.append("RU: содержит украинские буквы")
        else:
            forbidden_chars = {'ы', 'э', 'ъ', 'ё'}
            if any(char in full_text for char in forbidden_chars):
                errors.append("UA: содержит русские буквы")
        
        # 4. Проверка FAQ
        faq = content.get('faq', [])
        if not (4 <= len(faq) <= 6):
            errors.append(f"FAQ: {len(faq)} вопросов (нужно 4-6)")
        
        # 5. Проверка преимуществ
        benefits = content.get('benefits', [])
        if not (3 <= len(benefits) <= 6):
            errors.append(f"Преимущества: {len(benefits)} (нужно 3-6)")
        
        # 6. Проверка характеристик
        chars = content.get('characteristics', [])
        if len(chars) < 2:
            errors.append("Характеристик меньше 2")
        
        return (len(errors) == 0, errors)

    def _create_user_prompt(self, parsed_data: dict, locale: str) -> str:
        """Создаёт детальный user prompt с данными"""
        import json
        return f"""
Сгенерируй контент для товара на языке: {locale.upper()}

ИСХОДНЫЕ ДАННЫЕ:
Название: {parsed_data.get('title', 'N/A')}
Характеристики: {json.dumps(parsed_data.get('specs', []), ensure_ascii=False, indent=2)}
Описание из источника: {parsed_data.get('description', 'N/A')}

ОБЯЗАТЕЛЬНО:
1. Переведи название на {locale.upper()} язык
2. Используй ВСЕ характеристики из данных
3. Создай 2 параграфа описания (6-10 предложений)
4. Сгенерируй 4-6 FAQ на основе характеристик
5. НЕ используй шаблонные фразы
6. Только ФАКТЫ из исходных данных
"""

    def _is_refusal(self, content: str) -> bool:
        """
        Проверяет, отказался ли LLM генерировать контент
        
        Признаки отказа:
        - Слишком короткий текст (< 50 символов)
        - Фразы отказа
        - Шаблонный контент
        """
        
        if len(content) < 50:
            return True
        
        refusal_phrases = [
            'запрещено', 'не могу', 'cannot', 'i cannot',
            'content policy', 'against policy', 'inappropriate',
            'качественный продукт',  # Шаблонная фраза = провал
            'i apologize', 'i\'m sorry'
        ]
        
        content_lower = content.lower()
        
        for phrase in refusal_phrases:
            if phrase in content_lower:
                return True
        
        return False

    def _track_usage(self, provider: str, prompt: str, content: str):
        """
        Отслеживание использования токенов и затрат
        
        Args:
            provider: 'openai' или 'claude'
            prompt: Промпт (для подсчёта input токенов)
            content: Ответ (для подсчёта output токенов)
        """
        
        # Примерный подсчёт токенов (1 токен ≈ 4 символа)
        input_tokens = len(prompt) // 4
        output_tokens = len(content) // 4
        
        # Обновляем статистику
        if provider == 'openai':
            self.stats['openai_calls'] += 1
            self.stats['openai_tokens']['input'] += input_tokens
            self.stats['openai_tokens']['output'] += output_tokens
            
            # Стоимость
            cost = (
                input_tokens / 1_000_000 * self.PRICING['gpt-4o-mini']['input'] +
                output_tokens / 1_000_000 * self.PRICING['gpt-4o-mini']['output']
            )
            self.stats['openai_cost'] += cost
        
        else:  # claude
            self.stats['claude_calls'] += 1
            self.stats['claude_tokens']['input'] += input_tokens
            self.stats['claude_tokens']['output'] += output_tokens
            
            # Стоимость
            cost = (
                input_tokens / 1_000_000 * self.PRICING['claude-3.5-sonnet']['input'] +
                output_tokens / 1_000_000 * self.PRICING['claude-3.5-sonnet']['output']
            )
            self.stats['claude_cost'] += cost
        
        # Общая стоимость
        self.stats['total_cost'] = self.stats['openai_cost'] + self.stats['claude_cost']

    def get_stats(self) -> Dict:
        """Получить статистику использования"""
        return self.stats.copy()

    def print_stats(self):
        """Вывести детальную статистику"""
        
        total_calls = self.stats['openai_calls'] + self.stats['claude_calls']
        
        if total_calls == 0:
            logger.info("📊 No LLM calls yet")
            return
        
        openai_percent = (self.stats['openai_calls'] / total_calls * 100) if total_calls > 0 else 0
        claude_percent = (self.stats['claude_calls'] / total_calls * 100) if total_calls > 0 else 0
        
        avg_cost = self.stats['total_cost'] / total_calls if total_calls > 0 else 0
        
        print("\n" + "="*80)
        print("📊 SMART ROUTING СТАТИСТИКА")
        print("="*80)
        
        print(f"\n🔵 GPT-4o-mini:")
        print(f"   Вызовов: {self.stats['openai_calls']} ({openai_percent:.1f}%)")
        print(f"   Токенов: {self.stats['openai_tokens']['input']:,} input / {self.stats['openai_tokens']['output']:,} output")
        print(f"   Стоимость: ${self.stats['openai_cost']:.4f}")
        print(f"   Провалов: {self.stats['openai_failed']}")
        
        print(f"\n🟣 Claude 3.5 Sonnet:")
        print(f"   Вызовов: {self.stats['claude_calls']} ({claude_percent:.1f}%)")
        print(f"   Токенов: {self.stats['claude_tokens']['input']:,} input / {self.stats['claude_tokens']['output']:,} output")
        print(f"   Стоимость: ${self.stats['claude_cost']:.4f}")
        print(f"   Провалов: {self.stats['claude_failed']}")
        
        print(f"\n💰 ИТОГО:")
        print(f"   Всего запросов: {total_calls}")
        print(f"   Общая стоимость: ${self.stats['total_cost']:.4f}")
        print(f"   Средняя стоимость: ${avg_cost:.6f} за товар")
        
        # Сравнение с альтернативами
        cost_if_all_openai = total_calls * 0.00078
        cost_if_all_claude = total_calls * 0.018
        
        print(f"\n📈 ЭКОНОМИЯ:")
        print(f"   Если бы всё через OpenAI: ${cost_if_all_openai:.4f}")
        print(f"   Если бы всё через Claude: ${cost_if_all_claude:.4f}")
        print(f"   Smart Routing: ${self.stats['total_cost']:.4f}")
        
        if self.stats['total_cost'] < cost_if_all_claude:
            savings = cost_if_all_claude - self.stats['total_cost']
            print(f"   ✅ Экономия: ${savings:.4f} ({savings/cost_if_all_claude*100:.1f}%)")
        
        print("="*80 + "\n")
