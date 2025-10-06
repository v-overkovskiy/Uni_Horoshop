"""
Минимальный LLM генератор с адресным ремонтом
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
from ..budget.controller import BudgetController

logger = logging.getLogger(__name__)

class MinimalLLMGenerator:
    """Минимальный LLM генератор с контролем бюджета"""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 budget_controller: Optional[BudgetController] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        # Жесткие таймауты для предотвращения зависания
        self.client = OpenAI(
            api_key=self.api_key,
            timeout=30.0,  # 30 секунд максимум
            max_retries=1  # Только 1 ретрай
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.budget_controller = budget_controller or BudgetController()
        
        # JSON схемы для строгой валидации
        self.schemas = {
            'h1': {
                "type": "object",
                "properties": {
                    "h1": {"type": "string", "minLength": 5, "maxLength": 200}
                },
                "required": ["h1"],
                "additionalProperties": False
            },
            'faq': {
                "type": "object",
                "properties": {
                    "faqs": {
                        "type": "array",
                        "minItems": 6,
                        "maxItems": 6,
                        "items": {
                            "type": "object",
                            "properties": {
                                "q": {"type": "string", "minLength": 8},
                                "a": {"type": "string", "minLength": 12}
                            },
                            "required": ["q", "a"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["faqs"],
                "additionalProperties": False
            },
            'advantages': {
                "type": "object",
                "properties": {
                    "advantages": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 4,
                        "items": {
                            "type": "string", 
                            "minLength": 24, 
                            "maxLength": 160,
                            "pattern": "^(?!.*(?:Дополнительная информация|Подробнее|Преимущество|Информация|Высокое качество|Удобно в использовании|Додаткова інформація|Детальніше|Перевага|Інформація|Висока якість|Зручно у використанні)).*$"
                        }
                    }
                },
                "required": ["advantages"],
                "additionalProperties": False
            },
            'description': {
                "type": "object",
                "properties": {
                    "p1": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "items": {"type": "string", "minLength": 20}
                    },
                    "p2": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "items": {"type": "string", "minLength": 20}
                    }
                },
                "required": ["p1", "p2"],
                "additionalProperties": False
            }
        }
    
    def generate_content(self, 
                        content_model: Any, 
                        locale: str, 
                        item_id: str) -> Optional[Dict[str, Any]]:
        """Генерация контента с контролем бюджета"""
        if not self.budget_controller.can_make_call(item_id, 'generate', locale):
            logger.warning(f"Бюджет исчерпан для генерации {locale} товара {item_id}")
            return None
        
        try:
            # Определяем, что нужно сгенерировать
            needs_generation = self._analyze_content_needs(content_model)
            
            if not needs_generation:
                logger.info(f"Контент {locale} товара {item_id} не требует генерации")
                return None
            
            # Генерируем контент
            generated = self._call_llm_batch(content_model, locale, needs_generation)
            
            # Записываем вызов в бюджет
            if self.budget_controller.record_call(item_id, 'generate', locale):
                logger.info(f"Контент сгенерирован для {locale} товара {item_id}")
                return generated
            else:
                logger.error(f"Не удалось записать вызов в бюджет для {item_id}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка генерации контента для {locale} товара {item_id}: {e}")
            return None
    
    def repair_content(self, 
                      content_model: Any, 
                      locale: str, 
                      item_id: str, 
                      repair_type: str) -> Optional[Dict[str, Any]]:
        """Адресный ремонт контента"""
        if not self.budget_controller.can_make_call(item_id, 'repair'):
            logger.warning(f"Бюджет исчерпан для ремонта товара {item_id}")
            return None
        
        try:
            # Генерируем только проблемный блок
            repaired = self._call_llm_repair(content_model, locale, repair_type)
            
            # Записываем вызов в бюджет
            if self.budget_controller.record_call(item_id, 'repair'):
                logger.info(f"Контент отремонтирован для {locale} товара {item_id} ({repair_type})")
                return repaired
            else:
                logger.error(f"Не удалось записать ремонт в бюджет для {item_id}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка ремонта контента для {locale} товара {item_id}: {e}")
            return None
    
    def _analyze_content_needs(self, content_model: Any) -> List[str]:
        """Анализ потребностей в генерации контента - НЕ генерируем h1"""
        # Генерируем только недостающие блоки, НЕ h1 (должен быть извлечен из страницы)
        return ['faq', 'advantages', 'description']
    
    def _call_llm_batch(self, 
                       content_model: Any, 
                       locale: str, 
                       needs: List[str]) -> Dict[str, Any]:
        """Батчевый вызов LLM для генерации контента"""
        prompt = self._build_batch_prompt(content_model, locale, needs)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt(locale)},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        
        try:
            result = json.loads(content)
            # Валидируем идентичность товара
            self._validate_identity(content_model, result, locale)
            return result
        except json.JSONDecodeError:
            logger.warning(f"LLM вернул не-JSON для {locale}, создаем fallback")
            return self._create_fallback_content(locale, needs)
    
    def _call_llm_repair(self, 
                        content_model: Any, 
                        locale: str, 
                        repair_type: str) -> Dict[str, Any]:
        """Адресный ремонт через LLM"""
        prompt = self._build_repair_prompt(content_model, locale, repair_type)
        schema = self.schemas.get(repair_type)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_repair_system_prompt(locale, repair_type)},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=800,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        
        try:
            result = json.loads(content)
            # Валидируем по схеме
            if self._validate_json_schema(result, schema):
                return result
            else:
                logger.warning(f"Результат ремонта не прошел валидацию схемы для {repair_type}")
                return self._create_fallback_repair(locale, repair_type)
        except json.JSONDecodeError:
            logger.warning(f"LLM вернул не-JSON при ремонте {repair_type}")
            return self._create_fallback_repair(locale, repair_type)
    
    def _get_volume_constraints(self, content_model: Any, locale: str) -> str:
        """Получает ограничения по объёму для LLM"""
        try:
            from src.processing.volume_manager import VolumeManager
            
            # Создаём временный HTML для извлечения объёмов
            specs_html = ""
            if hasattr(content_model, 'specs') and content_model.specs:
                specs_html = "<ul class='specs'>"
                for spec in content_model.specs:
                    specs_html += f"<li><span class='spec-label'>{spec.get('name', '')}:</span> {spec.get('value', '')}</li>"
                specs_html += "</ul>"
            
            volume_manager = VolumeManager(locale)
            allowed_volumes = volume_manager.extract_allowed_volumes(specs_html)
            
            if allowed_volumes:
                constraints = volume_manager.get_llm_constraints(allowed_volumes)
                return f"ВАЖНО по объёму: {constraints['constraint_text']}"
            
        except Exception as e:
            logger.warning(f"Не удалось получить ограничения объёма: {e}")
        
        return ""
    
    def _build_batch_prompt(self, content_model: Any, locale: str, needs: List[str]) -> str:
        """Построение батчевого промпта"""
        facts = {
            'title': content_model.h1,
            'locale': locale
        }
        
        # Получаем ограничения по объёму
        volume_constraints = self._get_volume_constraints(content_model, locale)
        
        if locale == 'ru':
            prompt = f"""
Создай недостающий контент на русском языке для товара:

НАЗВАНИЕ ТОВАРА (НЕ МЕНЯТЬ): {facts['title']}

ВАЖНО: 
- НЕ МЕНЯЙ название товара
- НЕ используй слова: комбайн, пылесос, сумка, смарт-колонка, наушники, телефон
- Используй только факты о товаре, не выдумывай
{volume_constraints}
- Для FAQ используй конкретные факты из характеристик (мощность, объём, материал и т.д.)

Нужно создать: {', '.join(needs)}

Верни JSON с полями:
"""
            if 'h1' in needs:
                prompt += """
- h1: правильное название товара на русском языке
"""
            if 'faq' in needs:
                prompt += """
- faqs: массив из 6 вопросов-ответов (без повторения полного названия в вопросах, с конкретными фактами из характеристик)
"""
            if 'advantages' in needs:
                prompt += """
- advantages: массив из 1-4 преимуществ (строго 24-160 символов каждое, без заглушек типа "Дополнительная информация", "Подробнее", "Преимущество", "Информация", "Высокое качество", "Удобно в использовании")
"""
            if 'description' in needs:
                prompt += """
- p1: массив из 3 предложений для первого абзаца
- p2: массив из 3 предложений для второго абзаца
"""
        else:  # ua
            prompt = f"""
Створи недостатній контент українською мовою для товару:

НАЗВА ТОВАРУ (НЕ ЗМІНЮЙ): {facts['title']}

ВАЖЛИВО:
- НЕ ЗМІНЮЙ назву товару
- НЕ використовуй слова: комбайн, пилосос, сумка, смарт-колонка, навушники, телефон
- Використовуй тільки факти про товар, не вигадуй
{volume_constraints}
- Для FAQ використовуй конкретні факти з характеристик (потужність, об'єм, матеріал тощо)

Потрібно створити: {', '.join(needs)}

Поверни JSON з полями:
"""
            if 'h1' in needs:
                prompt += """
- h1: правильна назва товару українською мовою
"""
            if 'faq' in needs:
                prompt += """
- faqs: масив з 6 питань-відповідей (без повторення повної назви в питаннях, з конкретними фактами з характеристик)
"""
            if 'advantages' in needs:
                prompt += """
- advantages: масив з 1-4 переваг (строго 24-160 символів кожне, без заглушок типу "Додаткова інформація", "Детальніше", "Перевага", "Інформація", "Висока якість", "Зручно у використанні")
"""
            if 'description' in needs:
                prompt += """
- p1: масив з 3 речень для першого абзацу
- p2: масив з 3 речень для другого абзацу
"""
        
        return prompt
    
    def _build_repair_prompt(self, content_model: Any, locale: str, repair_type: str) -> str:
        """Построение промпта для ремонта"""
        if repair_type == 'faq':
            if locale == 'ru':
                return f"""
Создай 6 вопросов-ответов на русском языке для товара "{content_model.h1}".
Вопросы должны быть конкретными, без повторения полного названия товара.
Верни JSON: {{"faqs": [{{"q": "вопрос", "a": "ответ"}}]}}
"""
            else:
                return f"""
Створи 6 питань-відповідей українською мовою для товару "{content_model.h1}".
Питання мають бути конкретними, без повторення повної назви товару.
Поверни JSON: {{"faqs": [{{"q": "питання", "a": "відповідь"}}]}}
"""
        
        elif repair_type == 'advantages':
            if locale == 'ru':
                return f"""
Создай 4-6 преимуществ на русском языке для товара "{content_model.h1}".
Избегай общих штампов, будь конкретным.
Верни JSON: {{"advantages": ["преимущество1", "преимущество2"]}}
"""
            else:
                return f"""
Створи 4-6 переваг українською мовою для товару "{content_model.h1}".
Уникай загальних штампів, будь конкретним.
Поверни JSON: {{"advantages": ["перевага1", "перевага2"]}}
"""
        
        elif repair_type == 'description':
            if locale == 'ru':
                return f"""
Создай описание на русском языке для товара "{content_model.h1}".
2 абзаца по 3 предложения каждый.
Верни JSON: {{"p1": ["предложение1", "предложение2", "предложение3"], "p2": ["предложение4", "предложение5", "предложение6"]}}
"""
            else:
                return f"""
Створи опис українською мовою для товару "{content_model.h1}".
2 абзаци по 3 речення кожен.
Поверни JSON: {{"p1": ["речення1", "речення2", "речення3"], "p2": ["речення4", "речення5", "речення6"]}}
"""
        
        return ""
    
    def _get_system_prompt(self, locale: str) -> str:
        """Системный промпт"""
        if locale == 'ru':
            return """
Ты - эксперт по созданию качественного контента для интернет-магазина.
Создавай уникальный, информативный контент на русском языке.
Избегай шаблонных фраз и общих формулировок.
Используй только факты из предоставленных данных.
Отвечай строго в формате JSON.
"""
        else:
            return """
Ти - експерт зі створення якісного контенту для інтернет-магазину.
Створюй унікальний, інформативний контент українською мовою.
Уникай шаблонних фраз і загальних формулювань.
Використовуй тільки факти з наданих даних.
Відповідай строго у форматі JSON.
"""
    
    def _get_repair_system_prompt(self, locale: str, repair_type: str) -> str:
        """Системный промпт для ремонта"""
        base_prompt = self._get_system_prompt(locale)
        
        if repair_type == 'faq':
            base_prompt += "\nСоздавай конкретные вопросы без повторения полного названия товара."
        elif repair_type == 'advantages':
            base_prompt += "\nИзбегай общих штампов, будь конкретным."
        elif repair_type == 'description':
            base_prompt += "\nСоздавай информативные предложения без промо-фраз."
        
        return base_prompt
    
    def _validate_json_schema(self, data: Dict, schema: Dict) -> bool:
        """Простая валидация JSON схемы"""
        if not schema:
            return True
        
        try:
            # Проверяем обязательные поля
            for required_field in schema.get('required', []):
                if required_field not in data:
                    return False
            
            # Проверяем типы и ограничения
            for field, field_schema in schema.get('properties', {}).items():
                if field in data:
                    value = data[field]
                    if field_schema.get('type') == 'array':
                        if not isinstance(value, list):
                            return False
                        min_items = field_schema.get('minItems', 0)
                        max_items = field_schema.get('maxItems', float('inf'))
                        if not (min_items <= len(value) <= max_items):
                            return False
            
            return True
        except Exception:
            return False
    
    
    def _validate_identity(self, content_model: Any, result: Dict[str, Any], locale: str):
        """Валидация идентичности товара - запрет изменения названия/категории"""
        # Запрещённые токены вне домена
        forbidden_tokens = [
            'комбайн', 'пылесос', 'сумка', 'смарт-колонка', 'наушники', 'телефон',
            'комбайн', 'пилосос', 'сумка', 'смарт-колонка', 'навушники', 'телефон'
        ]
        
        # Проверяем h1 на запрещённые токены и локализацию
        if 'h1' in result:
            h1_text = result['h1'].lower()
            for token in forbidden_tokens:
                if token in h1_text:
                    logger.error(f"❌ Запрещённый токен '{token}' в h1 для {locale}: {result['h1']}")
                    raise ValueError(f"Запрещённый токен '{token}' в названии товара")
            
            # Проверяем локализацию h1
            if locale == 'ru':
                # Проверяем на украинские слова в русском h1
                ukrainian_words = ['ламелярний', 'крем', 'екстра', 'зволоження', 'захист', 'епілакс']
                for word in ukrainian_words:
                    if word in h1_text:
                        logger.error(f"❌ Украинское слово '{word}' в RU h1: {result['h1']}")
                        raise ValueError(f"Украинское слово '{word}' в русском названии товара")
            elif locale == 'ua':
                # Проверяем на русские слова в украинском h1
                russian_words = ['ламелярный', 'крем', 'экстра', 'увлажнение', 'защита', 'эпилакс']
                for word in russian_words:
                    if word in h1_text:
                        logger.error(f"❌ Русское слово '{word}' в UA h1: {result['h1']}")
                        raise ValueError(f"Русское слово '{word}' в украинском названии товара")
        
            # Проверяем описание на запрещённые токены
            if 'description' in result:
                desc_text = ' '.join(result['description'].get('p1', []) + result['description'].get('p2', [])).lower()
                for token in forbidden_tokens:
                    if token in desc_text:
                        logger.error(f"❌ Запрещённый токен '{token}' в описании для {locale}")
                        raise ValueError(f"Запрещённый токен '{token}' в описании товара")
                
                # Проверяем консистентность объёма (исправляем 400 мл на 200 мл для воскоплава)
                if 'воскоплав' in desc_text and '400 мл' in desc_text:
                    logger.warning(f"Исправляем объём воскоплава с 400 мл на 200 мл для {locale}")
                    result['description']['p1'] = [p.replace('400 мл', '200 мл') for p in result['description'].get('p1', [])]
                    result['description']['p2'] = [p.replace('400 мл', '200 мл') for p in result['description'].get('p2', [])]
                
                # Исправляем объём в преимуществах
                if 'advantages' in result and 'воскоплав' in desc_text:
                    for i, advantage in enumerate(result['advantages']):
                        if '400 мл' in advantage:
                            logger.warning(f"Исправляем объём в преимуществе {i+1}: 400 мл → 200 мл для {locale}")
                            result['advantages'][i] = advantage.replace('400 мл', '200 мл')
        
        # Проверяем FAQ на запрещённые токены
        if 'faqs' in result:
            for faq in result['faqs']:
                faq_text = (faq.get('q', '') + ' ' + faq.get('a', '')).lower()
                for token in forbidden_tokens:
                    if token in faq_text:
                        logger.error(f"❌ Запрещённый токен '{token}' в FAQ для {locale}")
                        raise ValueError(f"Запрещённый токен '{token}' в FAQ товара")
        
        logger.debug(f"✅ Идентичность товара валидна для {locale}")
