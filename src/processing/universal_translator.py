"""
Универсальный переводчик для перевода FAQ и другого контента.
Использует SmartLLMClient для качественного перевода с сохранением контекста.
"""

import logging
from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.llm.smart_llm_client import SmartLLMClient

logger = logging.getLogger(__name__)

class UniversalTranslator:
    """
    Универсальный переводчик для перевода FAQ и другого контента.
    Использует SmartLLMClient для качественного перевода с сохранением контекста.
    """
    
    def __init__(self, llm_client: 'SmartLLMClient' = None):
        self.llm_client = llm_client
    
    async def translate_faq_list(self, faq_list: List[Dict[str, str]], target_lang: str) -> List[Dict[str, str]]:
        """
        Переводит весь список FAQ ПАКЕТНО одним запросом для максимальной производительности.
        
        Args:
            faq_list: Список FAQ на русском языке
            target_lang: Целевой язык ('uk' для украинского)
            
        Returns:
            List[Dict[str, str]]: Переведенный список FAQ
        """
        if not faq_list:
            return []
        
        if target_lang == 'ru':
            return faq_list  # Уже на русском
        
        logger.info(f"🔄 ПАКЕТНЫЙ перевод {len(faq_list)} FAQ на {target_lang}")
        
        try:
            # Собираем все тексты для перевода в один список
            texts_to_translate = []
            for item in faq_list:
                texts_to_translate.append(item['question'])
                texts_to_translate.append(item['answer'])
            
            # ОДИН пакетный запрос на перевод всех текстов
            translated_texts = await self._translate_batch(texts_to_translate, target_lang)
            
            # Собираем переведенный FAQ обратно в структуру
            translated_faq = []
            for i in range(len(faq_list)):
                translated_faq.append({
                    'question': translated_texts[i * 2],
                    'answer': translated_texts[i * 2 + 1]
                })
            
            logger.info(f"✅ ПАКЕТНО переведено {len(translated_faq)} FAQ на {target_lang}")
            return translated_faq
            
        except Exception as e:
            logger.error(f"❌ Ошибка пакетного перевода: {e}")
            # Fallback - возвращаем оригинал
            return faq_list
    
    def _build_translation_context(self, faq_list: List[Dict[str, str]], target_lang: str) -> str:
        """Создает контекст для перевода на основе всех FAQ."""
        context_parts = []
        
        for faq in faq_list:
            context_parts.append(f"Вопрос: {faq.get('question', '')}")
            context_parts.append(f"Ответ: {faq.get('answer', '')}")
        
        context = "\n".join(context_parts)
        
        if target_lang == 'uk':
            return f"""
Контекст для перевода на украинский язык:

{context}

Требования к переводу:
1. Сохранить техническую точность и специфику
2. Использовать профессиональную косметическую терминологию
3. Сохранить развернутость и детализацию ответов
4. Адаптировать под украинскую аудиторию
5. Сохранить структуру вопрос-ответ
"""
        return context
    
    async def _translate_single_faq(self, faq_item: Dict[str, str], context: str, target_lang: str) -> Dict[str, str]:
        """Переводит один FAQ с учетом контекста."""
        
        if target_lang == 'uk':
            prompt = f"""
Переведи следующий FAQ на украинский язык, сохранив техническую точность и развернутость:

Вопрос: {faq_item.get('question', '')}
Ответ: {faq_item.get('answer', '')}

Контекст: {context}

Требования:
- Используй профессиональную косметическую терминологию
- Сохрани развернутость и детализацию
- Адаптируй под украинскую аудиторию
- Сохрани структуру вопрос-ответ

Верни результат в формате JSON:
{{
    "question": "переведенный вопрос",
    "answer": "переведенный ответ"
}}
"""
        else:
            # Для других языков - базовый перевод
            prompt = f"""
Переведи следующий FAQ на {target_lang}:

Вопрос: {faq_item.get('question', '')}
Ответ: {faq_item.get('answer', '')}

Верни результат в формате JSON:
{{
    "question": "переведенный вопрос", 
    "answer": "переведенный ответ"
}}
"""
        
        try:
            # Используем SmartLLMClient для перевода
            full_prompt = f"Ты профессиональный переводчик косметических товаров. Переводи точно и развернуто.\n\n{prompt}"
            
            response_text = await self.llm_client.generate(
                prompt=full_prompt,
                context={},
                max_tokens=1000,
                temperature=0.3,
                locale=target_lang
            )
            
            import json
            result = json.loads(response_text)
            
            return {
                "question": result.get("question", faq_item.get('question', '')),
                "answer": result.get("answer", faq_item.get('answer', ''))
            }
            
        except Exception as e:
            logger.error(f"Ошибка перевода FAQ: {e}")
            return faq_item  # Fallback на оригинал
    
    async def _translate_batch(self, texts: List[str], target_lang: str) -> List[str]:
        """
        Переводит список текстов ОДНИМ пакетным запросом к LLM.
        Кардинально ускоряет перевод с 12 запросов до 1.
        
        Args:
            texts: Список текстов для перевода
            target_lang: Целевой язык
            
        Returns:
            List[str]: Переведенные тексты
        """
        if target_lang == 'ru':
            return texts
        
        try:
            # Создаем один промпт для перевода всех текстов
            texts_text = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
            
            if target_lang == 'uk':
                prompt = f"""
Переведи следующие тексты на украинский язык, сохранив техническую точность и развернутость:

{texts_text}

Требования:
- Используй профессиональную косметическую терминологию
- Сохрани развернутость и детализацию
- Адаптируй под украинскую аудиторию
- Сохрани нумерацию (1., 2., 3., ...)

Верни результат в том же формате с нумерацией:
1. переведенный текст 1
2. переведенный текст 2
...
"""
            else:
                prompt = f"Переведи следующие тексты на {target_lang}:\n\n{texts_text}\n\nВерни результат в том же формате с нумерацией."
            
            # Используем SmartLLMClient для перевода
            full_prompt = f"Ты профессиональный переводчик косметических товаров. Переводи точно и развернуто.\n\n{prompt}"
            
            translated_response = await self.llm_client.generate(
                prompt=full_prompt,
                context={},
                max_tokens=2000,
                temperature=0.3,
                locale=target_lang
            )
            
            # Парсим ответ и извлекаем переведенные тексты
            translated_response = translated_response.strip()
            translated_lines = translated_response.split('\n')
            
            # Извлекаем тексты после номеров
            translated_texts = []
            for line in translated_lines:
                if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith('-')):
                    # Убираем номер и точку/тире
                    text = line.strip()
                    if text[0].isdigit():
                        text = text.split('.', 1)[1].strip() if '.' in text else text[1:].strip()
                    elif text.startswith('-'):
                        text = text[1:].strip()
                    translated_texts.append(text)
            
            # Если количество не совпадает, используем fallback
            if len(translated_texts) != len(texts):
                logger.warning(f"Количество переведенных текстов ({len(translated_texts)}) не совпадает с исходным ({len(texts)})")
                # Fallback - переводим по одному
                return await self._translate_individual_fallback(texts, target_lang)
            
            logger.info(f"✅ ПАКЕТНО переведено {len(translated_texts)} текстов за 1 запрос")
            return translated_texts
            
        except Exception as e:
            logger.error(f"Ошибка пакетного перевода: {e}")
            # Fallback - переводим по одному
            return await self._translate_individual_fallback(texts, target_lang)
    
    async def _translate_individual_fallback(self, texts: List[str], target_lang: str) -> List[str]:
        """Fallback метод для перевода по одному тексту."""
        logger.info("🔄 Fallback: переводим по одному тексту")
        translated_texts = []
        for text in texts:
            try:
                translated = await self.translate_text(text, target_lang)
                translated_texts.append(translated)
            except Exception as e:
                logger.error(f"Ошибка перевода текста: {e}")
                translated_texts.append(text)  # Оставляем оригинал
        return translated_texts
    
    async def translate_text(self, text: str, target_lang: str) -> str:
        """
        Переводит произвольный текст.
        
        Args:
            text: Текст для перевода
            target_lang: Целевой язык
            
        Returns:
            str: Переведенный текст
        """
        if target_lang == 'ru':
            return text
        
        try:
            if target_lang == 'uk':
                prompt = f"""
Переведи следующий текст на украинский язык, сохранив техническую точность:

{text}

Требования:
- Используй профессиональную косметическую терминологию
- Сохрани развернутость и детализацию
- Адаптируй под украинскую аудиторию
"""
            else:
                prompt = f"Переведи следующий текст на {target_lang}:\n\n{text}"
            
            # Используем SmartLLMClient для перевода
            full_prompt = f"Ты профессиональный переводчик косметических товаров.\n\n{prompt}"
            
            response_text = await self.llm_client.generate(
                prompt=full_prompt,
                context={},
                max_tokens=1000,
                temperature=0.3,
                locale=target_lang
            )
            
            return response_text.strip()
            
        except Exception as e:
            logger.error(f"Ошибка перевода текста: {e}")
            return text  # Fallback на оригинал
