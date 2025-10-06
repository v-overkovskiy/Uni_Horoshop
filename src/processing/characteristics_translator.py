# src/processing/characteristics_translator.py

import logging
from typing import Dict
from src.llm.smart_llm_client import SmartLLMClient

logger = logging.getLogger(__name__)

class CharacteristicsTranslator:
    """
    Умный переводчик названий характеристик с русского на украинский.
    Использует частичный перевод и морфологический анализ без статических словарей.
    """
    
    def __init__(self):
        self.llm = SmartLLMClient()
    
    # ✅ УНИВЕРСАЛЬНАЯ СИСТЕМА: Никаких словарей! Только LLM перевод

    async def translate(self, ru_key: str) -> str:
        """
        ✅ УНИВЕРСАЛЬНЫЙ перевод через LLM - работает для ЛЮБЫХ характеристик
        
        Args:
            ru_key: Ключ характеристики на русском языке
            
        Returns:
            str: Переведенный ключ на украинском языке
        """
        if not ru_key:
            return ru_key
        
        # Убираем двоеточие и лишние пробелы
        clean_key = ru_key.replace(':', '').strip()
        
        # ✅ УНИВЕРСАЛЬНЫЙ перевод через LLM
        try:
            import httpx
            import os
            
            # Формируем промпт для перевода
            prompt = f"""Переведи название характеристики товара на украинский язык:
Название: {clean_key}

Требования:
- Точный перевод
- Сохрани технические термины
- БЕЗ пояснений

Формат ответа (ТОЛЬКО результат):
[переведенное название]"""

            # ✅ Smart Routing: Передаём контекст для маршрутизации
            context = {
                'title': clean_key,
                'type': 'translation'
            }
            
            # Используем SmartLLMClient с умной маршрутизацией
            translated_text = await self.llm.generate(
                prompt=prompt,
                context=context,
                max_tokens=50,
                temperature=0.3,
                validate_content=False,  # Перевод не требует валидации
                locale='ua'  # Перевод на украинский
            )
            
            # Капитализация первой буквы
            if translated_text and len(translated_text) > 0:
                translated_text = translated_text[0].upper() + translated_text[1:]
            
            # Восстанавливаем двоеточие если было
            if ru_key.endswith(':'):
                translated_text += ':'
            
            logger.info(f"✅ LLM перевод характеристики: '{clean_key}' → '{translated_text}'")
            return translated_text
                    
        except Exception as e:
            logger.error(f"❌ Ошибка LLM перевода: {e}")
            return ru_key  # Fallback: возвращаем оригинал

    def translate_characteristics(self, specs: Dict[str, str]) -> Dict[str, str]:
        """
        Переводит все ключи в словаре характеристик.
        
        Args:
            specs: Словарь характеристик с русскими ключами
            
        Returns:
            Dict[str, str]: Словарь с переведенными ключами
        """
        if not specs:
            return specs
            
        translated_specs = {}
        for key, value in specs.items():
            translated_key = self.translate(key)
            translated_specs[translated_key] = value
            
        logger.info(f"Переведено {len(translated_specs)} названий характеристик")
        return translated_specs
    
    async def translate_text(self, text: str, target_lang: str = 'ru') -> str:
        """
        Переводит произвольный текст с помощью LLM
        
        Args:
            text: Текст для перевода
            target_lang: Целевой язык ('ru' или 'ua')
            
        Returns:
            str: Переведенный текст
        """
        if not text:
            return text
        
        # Сначала пробуем простой словарь
        simple_translation = self._simple_translate(text, target_lang)
        if simple_translation != text:
            logger.info(f"✅ Простой перевод успешен: {text} → {simple_translation}")
            return simple_translation
        
        # Если простой перевод не сработал, используем LLM
        logger.info(f"🔄 Простой перевод не сработал, используем LLM для: {text}")
        return await self._llm_translate(text, target_lang)
    
    def _simple_translate(self, text: str, target_lang: str) -> str:
        """✅ УНИВЕРСАЛЬНЫЙ перевод характеристики через LLM
        БЕЗ словарей - работает для ЛЮБЫХ товаров"""
        
        if target_lang == 'ua':
            return text  # UA - исходный язык
        
        # Для RU переводим через LLM
        prompt = f"""Переведи характеристику товара на русский:
Текст: {text}

Требования:
- Точный перевод
- Сохрани технические термины
- БЕЗ пояснений

Формат ответа (ТОЛЬКО результат):
[переведенный текст]"""

        try:
            import httpx
            import os
            
            # Синхронный HTTP запрос (для совместимости)
            api_key = os.getenv('OPENAI_API_KEY')
            with httpx.Client() as client:
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 100
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    translated_text = result['choices'][0]['message']['content'].strip()
                else:
                    logger.error(f"❌ LLM API ошибка: {response.status_code}")
                    return text
            
            # Капитализация первой буквы
            if translated_text and len(translated_text) > 0:
                translated_text = translated_text[0].upper() + translated_text[1:]
            
            logger.info(f"✅ LLM перевод: '{text}' → '{translated_text}'")
            return translated_text
            
        except Exception as e:
            logger.error(f"❌ Ошибка LLM перевода: {e}")
            # Fallback: оригинал
            return text
    
    async def _llm_translate(self, text: str, target_lang: str) -> str:
        """Перевод с помощью LLM"""
        import httpx
        import os
        
        # Определяем исходный и целевой языки
        source_lang = 'ua' if target_lang == 'ru' else 'ru'
        target_lang_name = 'русский' if target_lang == 'ru' else 'украинский'
        
        prompt = f"""
Переведи название товара с {source_lang} на {target_lang_name} язык.

Название: {text}

ТРЕБОВАНИЯ:
1. Сохрани структуру и формат названия
2. Переведи ТОЛЬКО слова, которые нужно перевести
3. Сохрани технические термины и бренды как есть
4. Используй правильную грамматику {target_lang_name} языка
5. Отвечай ТОЛЬКО переведенным названием, без дополнительных слов

Переведенное название:"""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": f"Ты эксперт по переводу названий товаров с {source_lang} на {target_lang_name} язык."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 100
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ LLM API ошибка: {response.status_code}")
                    return text
                
                result = response.json()
                translated = result['choices'][0]['message']['content'].strip()
                
                # Убираем кавычки если есть
                if translated.startswith('"') and translated.endswith('"'):
                    translated = translated[1:-1]
                
                # ⚠️ КРИТИЧНО: Всегда капитализируем первую букву
                if translated and len(translated) > 0:
                    if translated[0].islower():
                        translated = translated[0].upper() + translated[1:]
                        logger.info(f"🔧 LLM: исправлена капитализация: '{translated}'")
                
                logger.info(f"✅ LLM перевод: {text} → {translated}")
                return translated
                
        except Exception as e:
            logger.error(f"❌ Ошибка LLM перевода: {e}")
            return text
    
    async def translate_characteristics_batch(
        self,
        characteristics: list,
        target_locale: str
    ) -> list:
        """
        УНИВЕРСАЛЬНЫЙ перевод характеристик через LLM
        Работает для ЛЮБЫХ товаров и характеристик
        """
        if not characteristics:
            return []
        
        if target_locale == 'ua':
            # UA - исходный язык, возвращаем как есть
            return characteristics
        
        # Для RU переводим ВСЕ через LLM
        logger.info(f"🔄 УНИВЕРСАЛЬНЫЙ перевод {len(characteristics)} характеристик → {target_locale}")
        
        # Формируем промпт для ПАКЕТНОГО перевода (эффективнее)
        prompt = self._build_translation_prompt(characteristics, target_locale)
        
        try:
            # ✅ Smart Routing: Передаём контекст для маршрутизации
            context = {
                'type': 'batch_translation',
                'target_locale': target_locale
            }
            
            # Используем SmartLLMClient с умной маршрутизацией
            system_prompt = "Ты эксперт по переводу характеристик товаров."
            full_prompt = f"{system_prompt}\n\n{prompt}"
            
            response_text = await self.llm.generate(
                prompt=full_prompt,
                context=context,
                max_tokens=500,
                temperature=0.3,
                validate_content=False,  # Перевод не требует валидации
                locale=target_locale  # Целевая локаль
            )
            
            # Парсим ответ LLM
            logger.info(f"🔍 DEBUG: LLM ответ: {response_text}")
            translated = self._parse_translation_response(response_text, characteristics)
            logger.info(f"🔍 DEBUG: Переведенные характеристики: {translated}")
            logger.info(f"🔍 DEBUG: Тип переведенных: {type(translated)}")
            
            # Валидация и логирование
            for orig, trans in zip(characteristics, translated):
                logger.info(f"✅ {orig['label']}={orig['value']} → {trans['label']}={trans['value']}")
            
            return translated
                
        except Exception as e:
            logger.error(f"❌ Ошибка LLM перевода характеристик: {e}")
            # Fallback: возвращаем оригинал
            return characteristics
    
    def _build_translation_prompt(self, characteristics: list, target_locale: str) -> str:
        """Строит промпт для перевода характеристик"""
        # Формируем список характеристик
        chars_text = "\n".join([
            f"{i+1}. {char['label']}: {char['value']}"
            for i, char in enumerate(characteristics)
        ])
        
        locale_name = {
            'ru': 'русский',
            'ua': 'украинский'
        }.get(target_locale, target_locale)
        
        prompt = f"""Переведи характеристики товара на {locale_name} язык.
ИСХОДНЫЕ ХАРАКТЕРИСТИКИ:
{chars_text}

ТРЕБОВАНИЯ:
- Переведи ТОЧНО каждую метку и значение
- Сохрани технические термины и единицы измерения
- Используй естественный язык целевой локали
- НЕ добавляй ничего от себя
- Сохрани порядок и структуру

ФОРМАТ ОТВЕТА (строго JSON):
[
{{"label": "переведенная_метка_1", "value": "переведенное_значение_1"}},
{{"label": "переведенная_метка_2", "value": "переведенное_значение_2"}},
...
]

ПЕРЕВЕДЁННЫЕ ХАРАКТЕРИСТИКИ:"""
        
        return prompt
    
    def _parse_translation_response(self, response: str, original: list) -> list:
        """Парсит ответ LLM с переведёнными характеристиками"""
        import json
        import re
        
        try:
            # Извлекаем JSON из ответа
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                translated = json.loads(json_str)
                
                # Валидация структуры
                if isinstance(translated, list) and len(translated) == len(original):
                    for item in translated:
                        if not isinstance(item, dict) or 'label' not in item or 'value' not in item:
                            raise ValueError("Неверная структура ответа")
                    
                    return translated
            
            logger.warning("⚠️ Не удалось распарсить JSON ответ, пробуем построчный парсинг")
            
            # Fallback: построчный парсинг
            lines = [line.strip() for line in response.split('\n') if line.strip()]
            translated = []
            
            for line in lines:
                # Ищем паттерн "метка: значение"
                match = re.match(r'(?:\d+\.\s*)?(.+?):\s*(.+)', line)
                if match:
                    translated.append({
                        'label': match.group(1).strip(),
                        'value': match.group(2).strip()
                    })
            
            if len(translated) == len(original):
                return translated
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга перевода: {e}")
        
        # Последний fallback: возвращаем оригинал
        logger.warning("⚠️ Используем оригинальные характеристики (перевод не удался)")
        return original