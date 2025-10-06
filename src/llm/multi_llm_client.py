import os
import asyncio
import logging
from typing import Optional
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

class MultiLLMClient:
    """
    Умный клиент с автоматическим fallback:
    OpenAI → Claude при отказе
    """

    def __init__(self):
        # Primary: OpenAI
        openai_key = os.getenv('OPENAI_API_KEY')
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        
        if openai_key and openai_key != 'твой-существующий-openai-ключ':
            self.openai = AsyncOpenAI(api_key=openai_key)
        else:
            self.openai = None
            logger.warning("⚠️ OpenAI API ключ не установлен")
        
        if anthropic_key:
            self.claude = AsyncAnthropic(api_key=anthropic_key)
        else:
            self.claude = None
            logger.warning("⚠️ Anthropic API ключ не установлен")
        
        self.stats = {
            'openai_success': 0,
            'openai_failed': 0,
            'claude_used': 0
        }

    async def generate(
        self, 
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> str:
        """
        Умная генерация с автоматическим fallback
        
        Сначала пробует OpenAI, при отказе → Claude
        """
        
        # ПОПЫТКА 1: OpenAI
        if self.openai:
            try:
                logger.info("🤖 Генерация через OpenAI GPT-4o-mini")
                content = await self._generate_openai(
                    prompt, 
                    max_tokens, 
                    temperature
                )
                
                # Проверяем на отказ
                if self._is_refusal(content):
                    logger.warning("⚠️ OpenAI отказался, переключаюсь на Claude")
                    raise ValueError("OpenAI content policy refusal")
                
                self.stats['openai_success'] += 1
                logger.info("✅ OpenAI успешно сгенерировал контент")
                return content
                
            except Exception as e:
                logger.warning(f"⚠️ OpenAI failed: {e}")
                self.stats['openai_failed'] += 1
        else:
            logger.warning("⚠️ OpenAI недоступен, переключаюсь на Claude")
            self.stats['openai_failed'] += 1
        
        # ПОПЫТКА 2: Claude (fallback)
        if self.claude:
            logger.info("🔄 Переключаюсь на Claude (Anthropic)")
            content = await self._generate_claude(
                prompt, 
                max_tokens, 
                temperature
            )
            
            self.stats['claude_used'] += 1
            logger.info("✅ Claude успешно сгенерировал контент")
            return content
        else:
            raise ValueError("❌ Ни один LLM клиент недоступен (OpenAI и Claude)")

    async def _generate_openai(
        self, 
        prompt: str, 
        max_tokens: int, 
        temperature: float
    ) -> str:
        """Генерация через OpenAI"""
        
        response = await self.openai.chat.completions.create(
            model="gpt-4o-mini",  # Используем более дешевую модель
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional copywriter for e-commerce. Generate high-quality product descriptions, advantages, and FAQ content."
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
        """Генерация через Claude (Anthropic)"""
        
        response = await self.claude.messages.create(
            model="claude-instant-1",  # Latest Claude
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        content = response.content[0].text
        return content.strip()

    def _is_refusal(self, content: str) -> bool:
        """Проверяет, отказался ли LLM генерировать"""
        
        refusal_phrases = [
            'запрещено',
            'не могу',
            'cannot',
            'i cannot',
            'content policy',
            'against policy',
            'inappropriate',
            'качественный продукт',  # Шаблонный ответ = провал
            'профессиональный уход',  # Еще один шаблон
            'эффективный результат'  # И еще один
        ]
        
        content_lower = content.lower()
        
        # Если контент слишком короткий - подозрительно
        if len(content) < 20:
            logger.warning(f"⚠️ Слишком короткий ответ: {len(content)} символов")
            return True
        
        # Проверяем на фразы отказа
        for phrase in refusal_phrases:
            if phrase in content_lower:
                logger.warning(f"⚠️ Обнаружена фраза отказа: '{phrase}'")
                return True
        
        return False

    def get_stats(self) -> dict:
        """Статистика использования"""
        return self.stats.copy()
    
    def print_stats(self):
        """Выводит статистику в консоль"""
        stats = self.get_stats()
        total = stats['openai_success'] + stats['claude_used']
        
        if total > 0:
            claude_percent = (stats['claude_used'] / total) * 100
        else:
            claude_percent = 0
        
        print("\n" + "="*80)
        print("📊 СТАТИСТИКА ИСПОЛЬЗОВАНИЯ LLM:")
        print("="*80)
        print(f"   ✅ OpenAI успешно: {stats['openai_success']}")
        print(f"   ❌ OpenAI отказов: {stats['openai_failed']}")
        print(f"   🔄 Claude fallback: {stats['claude_used']}")
        print(f"   📈 Процент Claude: {claude_percent:.1f}%")
        print("="*80)
