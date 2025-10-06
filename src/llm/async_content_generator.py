"""
Асинхронный LLM генератор контента для новой архитектуры
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
import httpx

logger = logging.getLogger(__name__)

class AsyncLLMContentGenerator:
    """Асинхронный генератор контента с помощью LLM"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    async def generate_content(self, product_data: Dict[str, Any], locale: str, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Асинхронная генерация контента для товара"""
        try:
            # Подготавливаем факты для промпта
            facts = self._prepare_facts(product_data, locale)
            
            # Генерируем контент
            content = await self._call_llm(facts, locale, client)
            
            # Валидируем и исправляем контент
            validated_content = self._validate_content(content, locale)
            
            return validated_content
            
        except Exception as e:
            logger.error(f"Ошибка генерации контента для {locale}: {e}")
            raise e
    
    async def call_api(self, prompt: str, client: httpx.AsyncClient, max_tokens: int = 1000, temperature: float = 0.3) -> str:
        """
        Асинхронный публичный метод для вызова LLM API.
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            response = await client.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result
            else:
                logger.error(f"LLM API ошибка: {response.status_code} - {response.text}")
                raise Exception(f"LLM API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ошибка вызова LLM API: {e}")
            raise e
    
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
    
    def _prepare_facts(self, product_data: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Подготовка фактов для промпта"""
        facts = {
            'title': product_data.get('title', ''),
            'description': product_data.get('description', ''),
            'specs': product_data.get('specs', []),
            'locale': locale
        }
        
        # Добавляем специфичные для локали данные
        if locale == 'ua':
            facts['language'] = 'українська'
            facts['currency'] = 'грн'
        else:
            facts['language'] = 'русский'
            facts['currency'] = 'руб'
        
        return facts
    
    async def _call_llm(self, facts: Dict[str, Any], locale: str, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Асинхронный вызов LLM для генерации контента"""
        try:
            # Создаем промпт на основе фактов
            prompt = self._create_prompt(facts, locale)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.3
            }
            
            response = await client.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Парсим JSON ответ (убираем markdown блоки если есть)
                try:
                    # Убираем markdown блоки ```json и ```
                    if content.startswith('```json'):
                        content = content[7:]  # Убираем ```json
                    if content.endswith('```'):
                        content = content[:-3]  # Убираем ```
                    content = content.strip()
                    
                    parsed_content = json.loads(content)
                    logger.info(f"🔍 LLM ответ для {locale}: {parsed_content}")
                    return parsed_content
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON ответа LLM: {e}")
                    logger.error(f"Сырой ответ: {content}")
                    raise e
            else:
                logger.error(f"LLM API ошибка: {response.status_code} - {response.text}")
                raise Exception(f"LLM API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ошибка вызова LLM: {e}")
            raise e
    
    def _create_prompt(self, facts: Dict[str, Any], locale: str) -> str:
        """Создание промпта для LLM"""
        if locale == 'ua':
            return f"""
            Створи опис товару українською мовою на основі наступних фактів:
            Назва: {facts['title']}
            Опис: {facts['description']}
            Характеристики: {self._format_specs_for_prompt(facts['specs'])}
            
            Поверни JSON з наступними полями:
            - description: детальний опис товару (4-6 речень)
            - advantages: список переваг (3-4 пункти)
            - specs: характеристики товару
            - faq: список питань та відповідей (6 пунктів)
            - note_buy: короткий текст про покупку
            """
        else:
            return f"""
            Создай описание товара на русском языке на основе следующих фактов:
            Название: {facts['title']}
            Описание: {facts['description']}
            Характеристики: {self._format_specs_for_prompt(facts['specs'])}
            
            Верни JSON со следующими полями:
            - description: детальное описание товара (4-6 предложений)
            - advantages: список преимуществ (3-4 пункта)
            - specs: характеристики товара
            - faq: список вопросов и ответов (6 пунктов)
            - note_buy: короткий текст о покупке
            """
    
    def _validate_content(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Валидация и исправление контента"""
        # Базовая валидация
        required_fields = ['description', 'advantages', 'specs', 'faq', 'note_buy']
        
        for field in required_fields:
            if field not in content:
                content[field] = []
                logger.warning(f"Отсутствует поле {field} в ответе LLM")
        
        # Валидация FAQ
        if isinstance(content.get('faq'), list) and len(content['faq']) < 6:
            logger.warning(f"Недостаточно FAQ: {len(content['faq'])}/6")
            # Дополняем FAQ до 6 пунктов
            while len(content['faq']) < 6:
                content['faq'].append({
                    'question': f'Вопрос {len(content["faq"]) + 1}',
                    'answer': 'Ответ на вопрос'
                })
        
        return content
