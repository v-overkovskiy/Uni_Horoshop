"""
LLM генератор контента для новой архитектуры
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class LLMContentGenerator:
    """Генератор контента с помощью LLM"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    def generate_content(self, product_data: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Генерация контента для товара"""
        try:
            # Подготавливаем факты для промпта
            facts = self._prepare_facts(product_data, locale)
            
            # Генерируем контент
            content = self._call_llm(facts, locale)
            
            # Валидируем и исправляем контент
            validated_content = self._validate_content(content, locale)
            
            return validated_content
            
        except Exception as e:
            logger.error(f"Ошибка генерации контента для {locale}: {e}")
            raise e  # Не используем fallback, выбрасываем ошибку
    
    def call_api(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        Публичный метод для вызова LLM API.
        Используется в SanityFixer для локализации ключей и других задач.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            content = response.choices[0].message.content
            if not content or content.strip() == "":
                logger.error("LLM вернул пустой ответ")
                return ""
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка вызова LLM API: {e}")
            return ""

    def call_api_with_json_mode(self, prompt: str, max_tokens: int = 1000, temperature: float = 0.1) -> str:
        """
        Публичный метод для вызова LLM API с JSON-строгим режимом.
        Используется в SanityFixer для локализации ключей с гарантированным JSON.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}  # Строгий JSON режим
            )
            
            content = response.choices[0].message.content
            if not content or content.strip() == "":
                logger.error("LLM вернул пустой ответ в JSON режиме")
                return ""
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Ошибка вызова LLM API в JSON режиме: {e}")
            return ""

    def repair_description(self, product_data: Dict[str, Any], locale: str) -> str:
        """Ремонт описания - один дополнительный вызов LLM для исправления описания"""
        try:
            facts = self._prepare_facts(product_data, locale)
            content = self._call_llm(facts, locale, is_repair=True)
            
            if 'description' in content and content['description']:
                return content['description']
            else:
                raise ValueError("LLM не вернул описание в ремонте")
                
        except Exception as e:
            logger.error(f"Ошибка ремонта описания для {locale}: {e}")
            raise e
    
    def _prepare_facts(self, product_data: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Подготовка фактов для промпта"""
        return {
            "title": product_data.get("title", ""),
            "description": product_data.get("description", ""),
            "brand": product_data.get("brand", ""),
            "product_type": product_data.get("product_type", ""),
            "volume": product_data.get("volume", ""),
            "specs": product_data.get("specs", []),
            "locale": locale
        }
    
    def _call_llm(self, facts: Dict[str, Any], locale: str, is_repair: bool = False) -> Dict[str, Any]:
        """Вызов LLM для генерации контента"""
        prompt = self._build_prompt(facts, locale, is_repair)
        
        # Строгая JSON схема для предотвращения обрезаний
        json_schema = {
            "type": "object",
            "properties": {
                "description": {"type": "string", "maxLength": 600},
                "specs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["name", "value"]
                    },
                    "maxItems": 8
                },
                "advantages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 4
                },
                "faq": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"}
                        },
                        "required": ["question", "answer"]
                    },
                    "minItems": 6,
                    "maxItems": 6
                }
            },
            "required": ["description", "specs", "advantages", "faq"]
        }
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt(locale)},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1000,  # Увеличили для предотвращения обрезаний
            response_format={"type": "json_object"}  # Строгий JSON режим
        )
        
        content = response.choices[0].message.content
        logger.info(f"🔍 LLM ответ для {locale}: {content[:200]}...")
        
        if not content or content.strip() == "":
            logger.error(f"LLM вернул пустой ответ для {locale}")
            raise ValueError(f"LLM вернул пустой ответ для {locale}")
        
        try:
            # Очищаем контент от возможных артефактов
            content = content.strip()
            
            # Ищем JSON в ответе (на случай если есть дополнительный текст)
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            
            # Ищем первую { и последнюю }
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                content = content[start_idx:end_idx + 1]
            
            # Очищаем от недопустимых символов JSON
            import re
            # Заменяем недопустимые управляющие символы на пробелы
            content = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', content)
            # Убираем лишние пробелы
            content = re.sub(r'\s+', ' ', content)
            
            # Проверяем, что JSON не обрезан (должны быть все закрывающие скобки)
            open_braces = content.count('{')
            close_braces = content.count('}')
            open_brackets = content.count('[')
            close_brackets = content.count(']')
            
            if open_braces != close_braces or open_brackets != close_brackets:
                logger.error(f"JSON обрезан для {locale}: открывающих {{ {open_braces}, закрывающих }} {close_braces}")
                logger.error(f"Полный ответ LLM: {content}")
                raise ValueError(f"LLM вернул обрезанный JSON для {locale}")
            
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"LLM вернул не-JSON для {locale}: {e}")
            logger.error(f"Полный ответ LLM: {content}")
            raise ValueError(f"LLM вернул невалидный JSON для {locale}")
    
    def _build_prompt(self, facts: Dict[str, Any], locale: str, is_repair: bool = False) -> str:
        """Построение промпта"""
        if locale == 'ru':
            repair_text = "РЕМОНТ: " if is_repair else ""
            return f"""
{repair_text}Создай качественное описание товара на русском языке:

Название: {facts['title']}
Бренд: {facts['brand']}
Тип: {facts['product_type']}
Объем: {facts['volume']}

Существующее описание: {facts['description']}

КРИТИЧЕСКИ ВАЖНО: 
- description: Дай ровно 6 кратких предложений, разбитых на 2 абзаца по 3 предложения
- Каждое предложение должно быть информативным и содержательным
- Общая длина описания: 200-300 символов

СТРОГО: Ответь ТОЛЬКО валидным JSON без дополнительного текста, комментариев или объяснений!
JSON должен быть полным и корректным!

Создай JSON с полями:
- description: 2 абзаца по 3 предложения каждый (всего 6 предложений)
- specs: массив характеристик (минимум 8, используй переданные характеристики из сайта)
- advantages: массив преимуществ (минимум 4)
- faq: массив вопросов-ответов (ровно 6)

Переданные характеристики с сайта: {self._format_specs_for_prompt(facts['specs'])}

Все на русском языке, без украинских слов.

Пример формата:
{{
  "description": "Первое предложение. Второе предложение. Третье предложение.\n\nЧетвертое предложение. Пятое предложение. Шестое предложение.",
  "specs": [{{"name": "Характеристика", "value": "Значение"}}],
  "advantages": ["Преимущество 1", "Преимущество 2"],
  "faq": [{{"question": "Вопрос?", "answer": "Ответ"}}]
}}
"""
        else:  # ua
            repair_text = "РЕМОНТ: " if is_repair else ""
            return f"""
{repair_text}Створи якісний опис товару українською мовою:

Назва: {facts['title']}
Бренд: {facts['brand']}
Тип: {facts['product_type']}
Об'єм: {facts['volume']}

Існуючий опис: {facts['description']}

КРИТИЧНО ВАЖЛИВО:
- description: Дай рівно 6 коротких речень, розбитих на 2 абзаци по 3 речення
- Кожне речення має бути інформативним та змістовним
- Загальна довжина опису: 200-300 символів

СТРОГО: Відповідай ТІЛЬКИ валідним JSON без додаткового тексту, коментарів або пояснень!
JSON має бути повним та коректним!

Створи JSON з полями:
- description: 2 абзаци по 3 речення кожен (всього 6 речень)
- specs: масив характеристик (мінімум 8, використовуй передані характеристики з сайту)
- advantages: масив переваг (мінімум 4)
- faq: масив питань-відповідей (рівно 6)

Передані характеристики з сайту: {self._format_specs_for_prompt(facts['specs'])}

Все українською мовою, без російських слів.

Приклад формату:
{{
  "description": "Перше речення. Друге речення. Третє речення.\n\nЧетверте речення. П'яте речення. Шосте речення.",
  "specs": [{{"name": "Характеристика", "value": "Значення"}}],
  "advantages": ["Перевага 1", "Перевага 2"],
  "faq": [{{"question": "Питання?", "answer": "Відповідь"}}]
}}
"""
    
    def _get_system_prompt(self, locale: str) -> str:
        """Системный промпт"""
        if locale == 'ru':
            return """
Ты - эксперт по созданию качественных описаний товаров для интернет-магазина.
Создавай уникальный, информативный контент на русском языке.
Избегай шаблонных фраз и общих формулировок.
Используй только факты из предоставленных данных.
"""
        else:  # ua
            return """
Ти - експерт зі створення якісних описів товарів для інтернет-магазину.
Створюй унікальний, інформативний контент українською мовою.
Уникай шаблонних фраз і загальних формулювань.
Використовуй тільки факти з наданих даних.
"""
    
    def _format_specs_for_prompt(self, specs):
        """Форматирует характеристики для промпта"""
        if not specs:
            return "Нет характеристик"
        
        if isinstance(specs, list):
            # Список словарей
            formatted = []
            for spec in specs:
                if isinstance(spec, dict):
                    formatted.append(f"{spec.get('label', '')}: {spec.get('value', '')}")
                else:
                    formatted.append(str(spec))
            return "\n".join(formatted)
        elif isinstance(specs, dict):
            # Словарь
            formatted = []
            for key, value in specs.items():
                formatted.append(f"{key}: {value}")
            return "\n".join(formatted)
        else:
            return str(specs)
    
    

