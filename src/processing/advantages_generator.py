"""
Генератор преимуществ товаров
"""
import logging
from typing import Dict, Any, List
from src.llm.smart_llm_client import SmartLLMClient

logger = logging.getLogger(__name__)

class AdvantagesGenerator:
    """Генерирует преимущества товаров"""
    
    def __init__(self):
        self.llm = SmartLLMClient()
        self.advantages_prompt = """
Создай 3-6 преимуществ товара в формате карточек.

ФОРМАТ КАРТОЧКИ:
Заголовок (3-7 слов): Конкретное преимущество
(Без описания — только заголовок)

ТРЕБОВАНИЯ:
- НЕ используй generic-фразы: "высокое качество", "эффективный результат"
- Каждое преимущество должно быть уникальным и полезным
- Основывайся на реальных свойствах товара
- Используй факты из характеристик

ВХОДНЫЕ ДАННЫЕ:
{product_facts}

ПРИМЕРЫ ХОРОШИХ ПРЕИМУЩЕСТВ:
✅ "Подходит для всех типов кожи благодаря гипоаллергенной формуле"
✅ "Предотвращает врастание волос после депиляции"  
✅ "Упаковка 250 мл хватает на 2-3 месяца использования"

ПЛОХИЕ ПРИМЕРЫ (НЕ ИСПОЛЬЗУЙ):
❌ "Высокое качество"
❌ "Эффективный результат" 
❌ "Подходит для ежедневного использования"

ВЕРНИ ТОЛЬКО СПИСОК ЗАГОЛОВКОВ, КАЖДЫЙ С НОВОЙ СТРОКИ.
"""
    
    async def generate_advantages(self, product_facts: Dict[str, Any], locale: str) -> List[str]:
        """Генерирует 3-6 уникальных преимуществ товара"""
        try:
            # Создаем преимущества на основе фактов товара
            advantages = await self._create_structured_advantages(product_facts, locale)
            
            # Убеждаемся, что у нас 3-6 преимуществ
            if len(advantages) < 3:
                advantages.extend(self._generate_additional_advantages(product_facts, locale, 3 - len(advantages)))
            elif len(advantages) > 6:
                advantages = advantages[:6]
            
            logger.info(f"✅ Сгенерировано {len(advantages)} преимуществ для {locale}")
            return advantages
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации преимуществ: {e}")
            return self._create_fallback_advantages(locale)
    
    async def _create_structured_advantages(self, product_facts: Dict[str, Any], locale: str) -> List[str]:
        """Создает структурированные преимущества на основе фактов"""
        advantages = []
        title = product_facts.get('title', '').lower()
        volume = product_facts.get('volume', '')
        product_type = product_facts.get('product_type', '')
        
        # ✅ УНИВЕРСАЛЬНАЯ генерация преимуществ через LLM с fallback
        try:
            # Формируем контекст для LLM
            specs = product_facts.get('specs', {})
            specs_text = ""
            if isinstance(specs, list):
                specs_text = "\n".join([f"- {spec.get('label', '')}: {spec.get('value', '')}" for spec in specs[:5]])
            elif isinstance(specs, dict):
                specs_text = "\n".join([f"- {k}: {v}" for k, v in list(specs.items())[:5]])
            
            locale_name = "украинском" if locale == 'ua' else "русском"
            volume_text = f" Объем: {volume}" if volume else ""
            
            prompt = f"""Создай 5 конкретных преимуществ товара на {locale_name} языке:

Название: {title}{volume_text}
Характеристики:
{specs_text}

Требования:
- 5 конкретных преимуществ (не общих фраз)
- 20-40 символов каждое преимущество
- БЕЗ фраз: "высокое качество", "эффективный результат", "удобно в использовании"
- Основано на реальных характеристиках товара
- БЕЗ пояснений

Формат ответа (ТОЛЬКО список):
1. [преимущество 1]
2. [преимущество 2]
3. [преимущество 3]
4. [преимущество 4]
5. [преимущество 5]"""

            # ✅ Smart Routing: Передаём контекст для маршрутизации
            context = {
                'title': title,
                'locale': locale,
                'type': 'advantages'
            }
            
            # Используем SmartLLMClient с умной маршрутизацией и валидацией
            response_text = await self.llm.generate(
                prompt=prompt,
                context=context,
                max_tokens=300,
                temperature=0.7,
                validate_content=True,  # ✅ ВКЛЮЧИТЬ ВАЛИДАЦИЮ
                locale=locale  # ✅ Для валидации
            )
            
            # Парсим ответ
            lines = [line.strip() for line in response_text.split('\n') if line.strip()]
            advantages = []
            
            for line in lines:
                # Ищем паттерн "1. текст" или просто "текст"
                if '. ' in line:
                    advantage = line.split('. ', 1)[1]
                else:
                    advantage = line
                advantages.append(advantage)
            
            if len(advantages) >= 3:  # Минимум 3 преимущества
                logger.info(f"✅ LLM сгенерировал {len(advantages)} преимуществ для {locale}")
                return advantages[:5]  # Максимум 5
            else:
                logger.warning(f"⚠️ LLM вернул недостаточно преимуществ: {len(advantages)}")
                raise ValueError("Недостаточно преимуществ")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка LLM генерации преимуществ: {e}")
            raise ValueError(f"Не удалось сгенерировать преимущества: {e}")
        
        # ❌ НЕ ДОЛЖНО ДОЙТИ ДО СЮДА - LLM должен генерировать преимущества
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Дошли до fallback блока в генераторе преимуществ!")
        raise ValueError("LLM генерация преимуществ не удалась - система должна быть универсальной!")
    
    def _generate_additional_advantages(self, product_facts: Dict[str, Any], locale: str, count: int) -> List[str]:
        """Генерирует дополнительные преимущества при необходимости"""
        additional = []
        
        if locale == 'ua':
            additional = [
                "Зручна упаковка для зберігання",
                "Швидко дає помітні результати",
                "Безпечний для щоденного використання"
            ]
        else:
            additional = [
                "Удобная упаковка для хранения",
                "Быстро дает заметные результаты",
                "Безопасен для ежедневного использования"
            ]
        
        return additional[:count]
    
    def _create_fallback_advantages(self, locale: str) -> List[str]:
        """Создает fallback преимущества при ошибке"""
        if locale == 'ua':
            return [
                "Якісний склад для професійного догляду",
                "Підходить для щоденного використання",
                "Безпечний для всіх типів шкіри"
            ]
        else:
            return [
                "Качественный состав для профессионального ухода",
                "Подходит для ежедневного использования",
                "Безопасен для всех типов кожи"
            ]
