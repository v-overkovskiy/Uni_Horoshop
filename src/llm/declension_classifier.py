"""
LLM классификатор для склонения в note-buy
"""

import json
import logging
from typing import Dict, Any
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class DeclensionClassifier:
    """LLM классификатор склонения для note-buy"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def classify(self, title: str, locale: str) -> Dict[str, Any]:
        """Классифицирует, нужно ли склонять первое слово"""
        prompt = self._build_prompt(title, locale)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты эксперт по морфологии русского и украинского языков. Отвечай только JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            
            # Парсим JSON
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                logger.warning(f"Не удалось распарсить JSON от LLM: {content}")
                return self._fallback_result(locale)
                
        except Exception as e:
            logger.error(f"Ошибка LLM классификации: {e}")
            return self._fallback_result(locale)
    
    def _build_prompt(self, title: str, locale: str) -> str:
        """Строит промпт для классификации"""
        lang_name = "украинском" if locale == "ua" else "русском"
        
        return f"""
Классифицируй, нужно ли склонять первое слово заголовка товара в винительный падеж для фразы "купить/купити {title}".

Заголовок: {title}
Язык: {lang_name}

Правила склонения:
- Склоняем нарицательные существительные женского рода на -ка/-а/-ия/-ция
- НЕ склоняем бренды/модели/артикулы (ESTI, BUCOS, EPILAX, №, PRO, II, III, IV, V)
- НЕ склоняем слова с латиницей/цифрами/дефисами
- НЕ склоняем прилагательные перед брендом
- НЕ склоняем слова в UPPER CASE

Примеры склонения:
- "Пінка до депіляції" → "пінку до депіляції" (ж.р. -ка)
- "Крем для лица" → "крем для лица" (м.р., не меняется)
- "ESTI Professional" → "ESTI Professional" (бренд)
- "BUCOS CP-200" → "BUCOS CP-200" (модель с цифрами)

Верни строго JSON:
{{
    "locale": "{locale}",
    "need_inflect": true/false,
    "first_word_acc": "склонённая_форма_первого_слова_или_пустая_строка",
    "reason": "краткое_объяснение_решения",
    "confidence": 0.0-1.0
}}
"""
    
    def _fallback_result(self, locale: str) -> Dict[str, Any]:
        """Fallback результат при ошибке LLM"""
        return {
            "locale": locale,
            "need_inflect": False,
            "first_word_acc": "",
            "reason": "LLM error fallback",
            "confidence": 0.0
        }


