"""
LSI (Latent Semantic Indexing) Enhancer
Обогащает контент релевантными семантическими ключами для улучшения SEO
"""
import logging
import re
from typing import Dict, List, Any, Optional
from src.llm.smart_llm_client import SmartLLMClient

logger = logging.getLogger(__name__)

class LSIEnhancer:
    """Обогащает контент LSI-ключами естественным образом"""
    
    def __init__(self):
        self.llm = SmartLLMClient()
        
    async def enhance_with_lsi(self, content: Dict[str, Any], product_facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """
        Обогащает контент LSI-ключами
        
        Args:
            content: сгенерированный контент (description, advantages, faq)
            product_facts: факты о товаре
            locale: язык (ru/ua)
            
        Returns:
            Обогащенный контент с естественно интегрированными LSI-ключами
        """
        try:
            logger.info(f"🔍 LSI Enhancement: начинаем обогащение для {locale}")
            
            # Извлекаем основной ключ (название товара)
            main_keyword = product_facts.get('title', '')
            product_type = product_facts.get('product_type', '')
            category = product_facts.get('category', '')
            
            # Генерируем LSI-ключи
            lsi_keywords = await self._generate_lsi_keywords(
                main_keyword=main_keyword,
                product_type=product_type,
                category=category,
                locale=locale
            )
            
            if not lsi_keywords:
                logger.warning("⚠️ LSI-ключи не сгенерированы, возвращаем исходный контент")
                return content
            
            logger.info(f"✅ Сгенерировано {len(lsi_keywords)} LSI-ключей")
            
            # Обогащаем описание
            if content.get('description'):
                content['description'] = await self._inject_lsi_into_description(
                    description=content['description'],
                    lsi_keywords=lsi_keywords,
                    locale=locale
                )
            
            # Обогащаем преимущества (опционально, если нужно)
            if content.get('advantages'):
                content['advantages'] = await self._inject_lsi_into_advantages(
                    advantages=content['advantages'],
                    lsi_keywords=lsi_keywords,
                    locale=locale
                )
            
            # FAQ обычно НЕ трогаем - они должны быть естественными вопросами
            
            logger.info("✅ LSI Enhancement: контент успешно обогащен")
            return content
            
        except Exception as e:
            logger.error(f"❌ Ошибка LSI Enhancement: {e}")
            # Возвращаем исходный контент при ошибке
            return content
    
    async def _generate_lsi_keywords(
        self, 
        main_keyword: str, 
        product_type: str,
        category: str,
        locale: str
    ) -> List[str]:
        """Генерирует релевантные LSI-ключи"""
        
        system_prompt = self._get_lsi_generation_prompt(locale)
        
        user_message = f"""
ОСНОВНОЙ КЛЮЧ: {main_keyword}
ТИП ТОВАРА: {product_type}
КАТЕГОРИЯ: {category}

Сгенерируй 10-15 релевантных LSI-ключей для SEO-оптимизации.
"""
        
        # Объединяем system prompt и user message
        full_prompt = f"{system_prompt}\n\n{user_message}"
        
        try:
            response = await self.llm.generate(
                prompt=full_prompt,
                context={'type': 'lsi_generation', 'locale': locale},
                max_tokens=200,
                temperature=0.7
            )
            
            # Парсим ответ - ожидаем список ключей
            lsi_keywords = self._parse_lsi_response(response)
            
            logger.info(f"🔍 LSI-ключи: {lsi_keywords[:5]}..." if len(lsi_keywords) > 5 else f"🔍 LSI-ключи: {lsi_keywords}")
            
            return lsi_keywords
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации LSI-ключей: {e}")
            return []
    
    def _get_lsi_generation_prompt(self, locale: str) -> str:
        """Возвращает промпт для генерации LSI-ключей"""
        
        if locale == 'ru':
            return """Ты — SEO-эксперт, специализирующийся на латентно-семантической индексации (LSI).

ЗАДАЧА: Сгенерировать релевантные LSI-ключи для товара.

LSI-КЛЮЧИ — это связанные термины и фразы, которые:
1. Семантически близки к основному ключу
2. Помогают поисковым системам понять контекст
3. Используются естественно в тексте о товаре
4. НЕ являются точными синонимами, но логически связаны

ТРЕБОВАНИЯ:
✅ Генерируй ТОЛЬКО релевантные ключи
✅ Ключи должны быть естественными для контекста товара
✅ Избегай спама и переоптимизации
✅ Фокус на пользовательский опыт

ФОРМАТ ОТВЕТА:
Верни список ключей через запятую, БЕЗ нумерации.
Пример: йога-мат, коврик для фитнеса, занятия йогой, асаны, пилатес

ГЕНЕРИРУЙ ТОЛЬКО КЛЮЧИ, НИЧЕГО БОЛЬШЕ."""

        else:  # ua
            return """Ти — SEO-експерт, який спеціалізується на латентно-семантичній індексації (LSI).

ЗАВДАННЯ: Згенерувати релевантні LSI-ключі для товару.

LSI-КЛЮЧІ — це пов'язані терміни та фрази, які:
1. Семантично близькі до основного ключа
2. Допомагають пошуковим системам зрозуміти контекст
3. Використовуються природно в тексті про товар
4. НЕ є точними синонімами, але логічно пов'язані

ВИМОГИ:
✅ Генеруй ЛИШЕ релевантні ключі
✅ Ключі мають бути природними для контексту товару
✅ Уникай спаму та переоптимізації
✅ Фокус на користувацький досвід

ФОРМАТ ВІДПОВІДІ:
Поверни список ключів через кому, БЕЗ нумерації.
Приклад: йога-мат, килимок для фітнесу, заняття йогою, асани, пілатес

ГЕНЕРУЙ ТІЛЬКИ КЛЮЧІ, НІЧОГО БІЛЬШЕ."""
    
    def _parse_lsi_response(self, response: str) -> List[str]:
        """Парсит ответ LLM и извлекает LSI-ключи"""
        
        # Удаляем лишние пробелы и переносы
        response = response.strip()
        
        # Разбиваем по запятым
        keywords = [k.strip() for k in response.split(',')]
        
        # Фильтруем пустые и слишком длинные
        keywords = [k for k in keywords if k and len(k) < 100]
        
        # Ограничиваем до 15 ключей
        return keywords[:15]
    
    async def _inject_lsi_into_description(
        self, 
        description: str, 
        lsi_keywords: List[str],
        locale: str
    ) -> str:
        """Естественно вплетает LSI-ключи в описание"""
        
        system_prompt = self._get_lsi_injection_prompt(locale)
        
        user_message = f"""
ИСХОДНОЕ ОПИСАНИЕ:
{description}

LSI-КЛЮЧИ ДЛЯ ВПЛЕТЕНИЯ:
{', '.join(lsi_keywords)}

Перепиши описание, естественно интегрируя LSI-ключи.
"""
        
        # Объединяем system prompt и user message
        full_prompt = f"{system_prompt}\n\n{user_message}"
        
        try:
            enhanced_description = await self.llm.generate(
                prompt=full_prompt,
                context={'type': 'lsi_injection', 'locale': locale},
                max_tokens=1000,
                temperature=0.5
            )
            
            # Проверяем, что описание не стало слишком коротким или длинным
            if len(enhanced_description) < len(description) * 0.8:
                logger.warning("⚠️ Обогащенное описание слишком короткое, возвращаем исходное")
                return description
            
            if len(enhanced_description) > len(description) * 1.5:
                logger.warning("⚠️ Обогащенное описание слишком длинное, возвращаем исходное")
                return description
            
            logger.info("✅ Описание успешно обогащено LSI-ключами")
            return enhanced_description
            
        except Exception as e:
            logger.error(f"❌ Ошибка инъекции LSI в описание: {e}")
            return description
    
    def _get_lsi_injection_prompt(self, locale: str) -> str:
        """Возвращает промпт для инъекции LSI-ключей"""
        
        if locale == 'ru':
            return """Ты — SEO-копирайтер, специалист по естественной интеграции ключевых слов.

ЗАДАЧА: Переписать описание товара, естественно интегрируя LSI-ключи.

КРИТИЧЕСКИ ВАЖНО:
✅ Сохрани ВЕСЬ смысл исходного описания
✅ Интегрируй LSI-ключи ЕСТЕСТВЕННО, как бы они появились в обычном тексте
✅ НЕ делай текст спамным или переоптимизированным
✅ Сохрани структуру (2 абзаца)
✅ Сохрани длину описания (±20% от исходного)
✅ Пиши естественно, как для человека

ЗАПРЕЩЕНО:
❌ Перечислять ключи списком
❌ Использовать все ключи насильно
❌ Нарушать естественность текста
❌ Делать текст длиннее чем нужно

Используй ТОЛЬКО те ключи, которые естественно вписываются в контекст.

ВЕРНИ ТОЛЬКО ОБОГАЩЕННОЕ ОПИСАНИЕ, БЕЗ КОММЕНТАРИЕВ."""

        else:  # ua
            return """Ти — SEO-копірайтер, спеціаліст з природної інтеграції ключових слів.

ЗАВДАННЯ: Переписати опис товару, природно інтегруючи LSI-ключі.

КРИТИЧНО ВАЖЛИВО:
✅ Збережи ВЕСЬ зміст вихідного опису
✅ Інтегруй LSI-ключі ПРИРОДНО, як би вони з'явилися в звичайному тексті
✅ НЕ роби текст спамним або переоптимізованим
✅ Збережи структуру (2 абзаци)
✅ Збережи довжину опису (±20% від вихідного)
✅ Пиши природно, як для людини

ЗАБОРОНЕНО:
❌ Перелічувати ключі списком
❌ Використовувати всі ключі насильно
❌ Порушувати природність тексту
❌ Робити текст довшим ніж потрібно

Використовуй ЛИШЕ ті ключі, які природно вписуються в контекст.

ПОВЕРНИ ТІЛЬКИ ЗБАГАЧЕНИЙ ОПИС, БЕЗ КОМЕНТАРІВ."""
    
    async def _inject_lsi_into_advantages(
        self, 
        advantages: List[str], 
        lsi_keywords: List[str],
        locale: str
    ) -> List[str]:
        """
        Опционально обогащает преимущества LSI-ключами
        Используется осторожно, чтобы не перегрузить
        """
        
        # Выбираем только 2-3 ключа для преимуществ
        selected_keywords = lsi_keywords[:3]
        
        if not selected_keywords:
            return advantages
        
        # Обогащаем только первые 2 преимущества
        enhanced_advantages = advantages.copy()
        
        try:
            for i in range(min(2, len(enhanced_advantages))):
                if i < len(selected_keywords):
                    keyword = selected_keywords[i]
                    
                    # Проверяем, нет ли уже ключа в преимуществе
                    if keyword.lower() not in enhanced_advantages[i].lower():
                        # Естественно добавляем ключ
                        enhanced_advantages[i] = await self._enhance_advantage_with_keyword(
                            advantage=enhanced_advantages[i],
                            keyword=keyword,
                            locale=locale
                        )
            
            return enhanced_advantages
            
        except Exception as e:
            logger.error(f"❌ Ошибка обогащения преимуществ: {e}")
            return advantages
    
    async def _enhance_advantage_with_keyword(
        self, 
        advantage: str, 
        keyword: str,
        locale: str
    ) -> str:
        """Естественно добавляет ключ в преимущество"""
        
        if locale == 'ru':
            prompt = f"""Перепиши преимущество товара, естественно интегрировав ключевое слово "{keyword}".

ИСХОДНОЕ ПРЕИМУЩЕСТВО: {advantage}

Требования:
- Сохрани смысл
- Интегрируй ключ естественно
- Не делай текст длиннее чем на 30%
- Пиши для человека, не для робота

Верни ТОЛЬКО переписанное преимущество."""
        else:
            prompt = f"""Перепиши перевагу товару, природно інтегрувавши ключове слово "{keyword}".

ВИХІДНА ПЕРЕВАГА: {advantage}

Вимоги:
- Збережи зміст
- Інтегруй ключ природно
- Не роби текст довшим ніж на 30%
- Пиши для людини, не для робота

Поверни ТІЛЬКИ переписану перевагу."""
        
        # Объединяем в полный промпт
        full_prompt = f"Ти — SEO-копірайтер.\n\n{prompt}"
        
        try:
            enhanced = await self.llm.generate(
                prompt=full_prompt,
                context={'type': 'lsi_advantage', 'locale': locale},
                max_tokens=200,
                temperature=0.5
            )
            
            # Проверяем длину
            if len(enhanced) > len(advantage) * 1.5:
                return advantage
            
            return enhanced.strip()
            
        except Exception as e:
            logger.error(f"❌ Ошибка обогащения преимущества: {e}")
            return advantage

