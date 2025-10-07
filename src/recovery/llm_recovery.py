"""
Восстановление данных через LLM при сбоях парсинга
Универсальный recovery механизм без хардкода
"""
import json
import logging
from typing import Dict, List, Optional, Any
import re

logger = logging.getLogger(__name__)

class LLMRecovery:
    """Восстановление данных через LLM при сбоях парсинга"""
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.model = "gpt-4o-mini"  # По умолчанию, можно переопределить
    
    async def extract_characteristics_from_raw_html(
        self, 
        html: str, 
        product_name: str
    ) -> List[Dict[str, str]]:
        """Извлечение характеристик через LLM если парсинг не сработал"""
        
        try:
            logger.info(f"🤖 LLM Recovery: извлекаем характеристики для '{product_name}'")
            
            # Обрезаем HTML до разумного размера
            html_sample = html[:3000] if len(html) > 3000 else html
            
            prompt = f"""Извлеки характеристики товара из HTML.

ТОВАР: {product_name}

HTML (первые 3000 символов):
{html_sample}

ТРЕБОВАНИЯ:
- Найди все характеристики товара в HTML
- Верни ТОЛЬКО JSON без дополнительного текста
- Каждая характеристика: {{"label": "название", "value": "значение"}}
- Если характеристик нет, верни пустой массив []

ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
[
  {{"label": "Тип кожи", "value": "Жирная, Сухая"}},
  {{"label": "Объем", "value": "30 мл"}}
]"""

            response = await self._call_llm(prompt)
            characteristics = self._parse_characteristics_response(response)
            
            logger.info(f"✅ LLM Recovery: извлечено {len(characteristics)} характеристик")
            return characteristics
            
        except Exception as e:
            logger.error(f"❌ LLM Recovery: ошибка извлечения характеристик: {e}")
            return []
    
    async def find_image_from_raw_html(
        self, 
        html: str, 
        product_name: str
    ) -> Optional[str]:
        """Поиск изображения через LLM если обычный поиск не сработал"""
        
        try:
            logger.info(f"🤖 LLM Recovery: ищем изображение для '{product_name}'")
            
            # Обрезаем HTML до разумного размера
            html_sample = html[:2000] if len(html) > 2000 else html
            
            prompt = f"""Найди URL главного изображения товара в HTML.

ТОВАР: {product_name}

HTML (первые 2000 символов):
{html_sample}

ТРЕБОВАНИЯ:
- Найди URL главного изображения товара
- Верни ТОЛЬКО URL или "NOT_FOUND"
- Ищи в атрибутах src, data-src, data-lazy-src
- Предпочитай изображения высокого качества (600x600, 800x800)

ФОРМАТ ОТВЕТА (ТОЛЬКО URL):
https://example.com/image.jpg

ИЛИ если не найдено:
NOT_FOUND"""

            response = await self._call_llm(prompt)
            image_url = self._parse_image_response(response)
            
            if image_url:
                logger.info(f"✅ LLM Recovery: найдено изображение: {image_url}")
            else:
                logger.warning(f"⚠️ LLM Recovery: изображение не найдено")
                
            return image_url
            
        except Exception as e:
            logger.error(f"❌ LLM Recovery: ошибка поиска изображения: {e}")
            return None
    
    async def extract_title_from_raw_html(
        self, 
        html: str
    ) -> Optional[str]:
        """Извлечение названия товара через LLM"""
        
        try:
            logger.info(f"🤖 LLM Recovery: извлекаем название товара")
            
            html_sample = html[:1500] if len(html) > 1500 else html
            
            prompt = f"""Найди название товара в HTML.

HTML (первые 1500 символов):
{html_sample}

ТРЕБОВАНИЯ:
- Найди название товара (обычно в h1, h2, title)
- Верни ТОЛЬКО название без дополнительного текста
- Если не найдено, верни "NOT_FOUND"

ФОРМАТ ОТВЕТА (ТОЛЬКО название):
Пилинг салициловый 20% рН 2.8 Esti Professional, 30 мл"""

            response = await self._call_llm(prompt)
            title = self._parse_title_response(response)
            
            if title:
                logger.info(f"✅ LLM Recovery: найдено название: '{title}'")
            else:
                logger.warning(f"⚠️ LLM Recovery: название не найдено")
                
            return title
            
        except Exception as e:
            logger.error(f"❌ LLM Recovery: ошибка извлечения названия: {e}")
            return None
    
    async def fix_language_issues(
        self, 
        characteristics: List[Dict[str, str]], 
        target_locale: str = 'ru'
    ) -> List[Dict[str, str]]:
        """Исправление языковых проблем через LLM"""
        
        try:
            logger.info(f"🤖 LLM Recovery: исправляем язык для {target_locale}")
            
            # Преобразуем характеристики в текст
            chars_text = "\n".join([
                f"- {char.get('label', '')}: {char.get('value', '')}"
                for char in characteristics
            ])
            
            locale_name = "русский" if target_locale == 'ru' else "украинский"
            
            prompt = f"""Исправь языковые ошибки в характеристиках товара.

ЦЕЛЕВОЙ ЯЗЫК: {locale_name}

ХАРАКТЕРИСТИКИ:
{chars_text}

ТРЕБОВАНИЯ:
- Переведи все на {locale_name} язык
- Исправь ошибки языка
- Сохрани технические термины
- Верни ТОЛЬКО JSON

ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
[
  {{"label": "исправленная_метка", "value": "исправленное_значение"}}
]"""

            response = await self._call_llm(prompt)
            fixed_characteristics = self._parse_characteristics_response(response)
            
            logger.info(f"✅ LLM Recovery: исправлено {len(fixed_characteristics)} характеристик")
            return fixed_characteristics
            
        except Exception as e:
            logger.error(f"❌ LLM Recovery: ошибка исправления языка: {e}")
            return characteristics  # Возвращаем оригинал при ошибке
    
    async def generate_fallback_content(
        self, 
        product_name: str, 
        characteristics: List[Dict[str, str]], 
        locale: str = 'ru'
    ) -> Dict[str, Any]:
        """Генерация fallback контента через LLM если обычная генерация не удалась"""
        
        try:
            logger.info(f"🤖 LLM Recovery: генерируем fallback контент для '{product_name}'")
            
            # Преобразуем характеристики в текст
            chars_text = "\n".join([
                f"- {char.get('label', '')}: {char.get('value', '')}"
                for char in characteristics[:10]  # Берем первые 10
            ])
            
            locale_name = "русском" if locale == 'ru' else "украинском"
            
            prompt = f"""Создай полный контент для товара на {locale_name} языке.

ТОВАР: {product_name}

ХАРАКТЕРИСТИКИ:
{chars_text}

КРИТИЧЕСКИ ВАЖНО - НАРУШЕНИЕ ВЛЕЧЕТ ОШИБКУ:
- ЗАПРЕЩЕНО использовать фразы: "качественный продукт", "профессиональный продукт", "эффективный продукт", "отличный выбор", "идеальный вариант", "превосходное качество", "якісний продукт", "професійний продукт", "ефективний продукт"
- ЗАПРЕЩЕНО упоминать: цену, стоимость, UAH, грн, доставку, магазин, "не указано", "не вказано"
- Описание ДОЛЖНО точно соответствовать типу товара из названия
- ОБЯЗАТЕЛЬНО упомяни конкретное название товара в описании
- Пиши КОНКРЕТНО: для какого типа кожи/волос, какие ингредиенты, какой эффект

ТРЕБОВАНИЯ:
- Создай описание (2-3 предложения)
- Создай 5 преимуществ
- Создай 6 FAQ
- Верни ТОЛЬКО JSON

ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
{{
  "description": "описание товара",
  "advantages": ["преимущество 1", "преимущество 2", ...],
  "faq": [
    {{"question": "вопрос 1", "answer": "ответ 1"}},
    {{"question": "вопрос 2", "answer": "ответ 2"}}
  ]
}}"""

            response = await self._call_llm(prompt)
            content = self._parse_content_response(response)
            
            # ✅ ВАЛИДАЦИЯ fallback контента
            from src.validation.content_validator import ContentValidator
            validator = ContentValidator()
            
            if not validator.validate_all_content(content, locale):
                logger.error("❌ LLM Recovery: fallback контент не прошёл валидацию")
                # Генерируем минимальный валидный контент
                return {
                    "description": f"Специализированное средство {product_name} для профессионального применения.",
                    "advantages": ["Профессиональное качество", "Удобная упаковка", "Быстрый результат"],
                    "faq": [
                        {"question": "Для чего предназначен товар?", "answer": "Для профессионального использования согласно инструкции."},
                        {"question": "Как использовать?", "answer": "Следуйте инструкции производителя."}
                    ]
                }
            
            logger.info(f"✅ LLM Recovery: сгенерирован валидный fallback контент")
            return content
            
        except Exception as e:
            logger.error(f"❌ LLM Recovery: ошибка генерации fallback контента: {e}")
            return {}
    
    async def _call_llm(self, prompt: str) -> str:
        """Вызов LLM для генерации (поддерживает OpenAI и Anthropic)"""
        if not self.llm:
            raise Exception("LLM клиент не доступен")
        
        try:
            # Определяем тип клиента
            client_type = type(self.llm).__name__
            
            if client_type == "Anthropic":
                # Claude API
                system_prompt = "Ты эксперт по извлечению данных из HTML. Отвечай только JSON или указанным форматом."
                full_prompt = f"{system_prompt}\n\n{prompt}"
                
                response = self.llm.messages.create(
                    model=self.model,
                    max_tokens=2000,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": full_prompt}
                    ]
                )
                
                return response.content[0].text.strip()
                
            else:
                # OpenAI API
                response = self.llm.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Ты эксперт по извлечению данных из HTML. Отвечай только JSON или указанным форматом."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )
                
                return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"❌ Ошибка вызова LLM ({client_type}): {e}")
            raise
    
    def _parse_characteristics_response(self, response: str) -> List[Dict[str, str]]:
        """Парсинг ответа с характеристиками"""
        try:
            # Ищем JSON в ответе
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                characteristics = json.loads(json_str)
                
                if isinstance(characteristics, list):
                    return characteristics
            
            logger.warning(f"⚠️ Не удалось распарсить характеристики: {response[:200]}")
            return []
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга характеристик: {e}")
            return []
    
    def _parse_image_response(self, response: str) -> Optional[str]:
        """Парсинг ответа с изображением"""
        response = response.strip()
        
        if response == "NOT_FOUND" or not response:
            return None
        
        # Проверяем что это похоже на URL
        if response.startswith(('http://', 'https://')):
            return response
        
        return None
    
    def _parse_title_response(self, response: str) -> Optional[str]:
        """Парсинг ответа с названием"""
        response = response.strip()
        
        if response == "NOT_FOUND" or not response:
            return None
        
        # Капитализируем первую букву
        if response and len(response) > 0:
            response = response[0].upper() + response[1:]
        
        return response
    
    def _parse_content_response(self, response: str) -> Dict[str, Any]:
        """Парсинг ответа с контентом"""
        try:
            # Ищем JSON в ответе
            json_match = re.search(r'\{.*?\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                content = json.loads(json_str)
                
                if isinstance(content, dict):
                    return content
            
            logger.warning(f"⚠️ Не удалось распарсить контент: {response[:200]}")
            return {}
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга контента: {e}")
            return {}
