"""
Асинхронный ContentCritic для универсальной проверки контента
"""
import json
import logging
import os
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

class AsyncContentCritic:
    """Асинхронный универсальный валидатор контента"""
    
    def __init__(self, api_key: Optional[str] = None):
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = "https://api.openai.com/v1/chat/completions"
    
    async def review(self, draft_content: Dict[str, Any], product_facts: Dict[str, Any], 
                    locale: str, client: httpx.AsyncClient) -> Dict[str, Any]:
        """
        Асинхронная комплексная проверка контента
        
        Args:
            draft_content: Черновик контента для проверки
            product_facts: Факты о товаре
            locale: Локаль (ru/ua)
            client: HTTP клиент для запросов
            
        Returns:
            Dict с результатами проверки и исправленным контентом
        """
        try:
            logger.info(f"🔍 ContentCritic: Начинаю комплексную проверку контента для {locale}")
            
            # Сохраняем исходные характеристики как read-only
            original_specs = product_facts.get('specs', [])
            if original_specs:
                logger.info(f"🔒 ContentCritic: Сохраняем {len(original_specs)} исходных характеристик как read-only")
            
            # Создаем промпт для проверки
            system_prompt = self._get_system_prompt(locale)
            user_prompt = self._create_user_prompt(draft_content, product_facts, locale)
            
            # Вызываем LLM для проверки
            review_result = await self._real_llm_review(
                draft_content, product_facts, locale, system_prompt, user_prompt, client
            )
            
            # Принудительно восстанавливаем исходные характеристики
            if original_specs and 'revised_content' in review_result:
                review_result['revised_content']['specs'] = original_specs
                logger.info(f"🔒 ContentCritic: Восстановлены исходные характеристики ({len(original_specs)} шт)")
            
            logger.info(f"✅ ContentCritic: Проверка завершена, статус: {review_result.get('overall_status', 'UNKNOWN')}")
            return review_result
            
        except Exception as e:
            logger.error(f"❌ ContentCritic: Ошибка при проверке контента: {e}")
            # Возвращаем mock-результат в случае ошибки
            return self._mock_review(draft_content, product_facts, locale)
    
    async def _real_llm_review(self, draft_content: Dict[str, Any], product_facts: Dict[str, Any],
                              locale: str, system_prompt: str, user_prompt: str, 
                              client: httpx.AsyncClient) -> Dict[str, Any]:
        """Реальная LLM-проверка контента"""
        try:
            logger.info("🔍 ContentCritic: Вызываю LLM для реальной проверки контента")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 4000
            }
            
            response = await client.post(
                self.base_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result['choices'][0]['message']['content']
                
                try:
                    # Убираем markdown блоки ```json и ```
                    if llm_response.startswith('```json'):
                        llm_response = llm_response[7:]  # Убираем ```json
                    if llm_response.endswith('```'):
                        llm_response = llm_response[:-3]  # Убираем ```
                    llm_response = llm_response.strip()
                    
                    review_result = json.loads(llm_response)
                    logger.info("✅ ContentCritic: LLM вернул валидный JSON")
                    return review_result
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ ContentCritic: LLM вернул невалидный JSON, используем fallback: {e}")
                    return self._mock_review(draft_content, product_facts, locale)
            else:
                logger.warning(f"⚠️ ContentCritic: LLM API ошибка {response.status_code}, используем fallback")
                return self._mock_review(draft_content, product_facts, locale)
                
        except Exception as e:
            logger.error(f"❌ ContentCritic: Ошибка LLM-проверки: {e}")
            logger.info("🔧 ContentCritic: Переключаемся на mock-режим")
            return self._mock_review(draft_content, product_facts, locale)
    
    def _get_system_prompt(self, locale: str) -> str:
        """Получение системного промпта для ContentCritic"""
        if locale == 'ua':
            return """Ти — головний редактор та SEO-спеціаліст e-commerce магазину. Твоє завдання — провести аудит повного комплекту текстів для картки товару та повернути структурований JSON з вердиктом. Будь вкрай строгим та уважним до деталей.

**Вхідні дані:**
1. `product_facts`: Ключові характеристики товару (об'єм, вага, призначення, виробник).
2. `draft_content`: JSON з згенерованим контентом (`description`, `advantages`, `specs`, `faq_candidates`, `note_buy`).

**Критерії перевірки по блоках:**

1. **`title` (Заголовок товару):**
   - **Повнота:** Заголовок повинен містити повну назву товару, включаючи бренд, об'єм/вагу.
   - **Відповідність локалі:** RU заголовки російською мовою, UA — українською.
   - **Вердикт:** `VALID` або `INCOMPLETE` з виправленою версією.

2. **`description` (Опис):**
   - **Факт-чекінг:** Чи відповідає текст фактам (об'єм, призначення)?
   - **Довжина та структура:** Не менше 4-5 речень. Текст повинен бути зв'язним та легко читабельним.
   - **SEO та стиль:** Чи присутні ключові слова з назви товару? Тон тексту — експертний, але зрозумілий покупцю.
   - **Вердикт:** `VALID` або `NEEDS_REWRITE` з вказівкою причин.

3. **`advantages` (Переваги):**
   - **Унікальність:** Чи не повторюють переваги одна одну за змістом?
   - **Цінність:** Чи є вони реальними перевагами для покупця, а не загальними фразами ("висока якість")?
   - **Кількість:** Повинно бути 3-4 унікальні переваги.
   - **Вердикт:** `VALID` або `NEEDS_REWRITE`.

4. **`specs` (Характеристики):**
   - **ЗАБОРОНЕНО змінювати, додавати або генерувати характеристики!** Блок specs є read-only - повертай його без змін.
   - **НЕ додавай 'Країна виробництва', 'Виробник' або будь-які заглушки, якщо їх немає у вихідних даних.**
   - **Вердикт:** `VALID` (завжди, оскільки блок read-only).

5. **`faq_candidates` (Кандидати в FAQ, список з ~10):**
   - **Перевірка на дублікати тем:** Знайди та відміть як `DUPLICATE_TOPIC` всі питання на одну тему (зберігання, тип шкіри тощо), крім першого.
   - **Перевірка на generic-відповіді:** Знайди та відміть як `GENERIC_ANSWER` відповіді-заглушки ("згідно з інструкцією", "на упаковці" тощо).
   - **Вердикт:** `VALID` або `NEEDS_FILTERING` з вказівкою, які елементи видалити.

6. **`note_buy` (Примітка про покупку):**
   - **Повнота:** Чи містить повну назву товару та комерційний заклик?
   - **Відповідність локалі:** UA текст українською мовою.
   - **Вердикт:** `VALID` або `NEEDS_REWRITE`.

**Формат відповіді (строго JSON):**
```json
{
  "overall_status": "VALID|NEEDS_REVISIONS",
  "quality_score": 0.0-1.0,
  "critiques": {
    "title": {"status": "VALID|INCOMPLETE", "issues": [], "suggestions": ""},
    "description": {"status": "VALID|NEEDS_REWRITE", "issues": [], "suggestions": ""},
    "advantages": {"status": "VALID|NEEDS_REWRITE", "issues": [], "suggestions": ""},
    "specs": {"status": "VALID|INCONSISTENT", "issues": [], "suggestions": ""},
    "faq_candidates": {"status": "VALID|NEEDS_FILTERING", "issues": [], "suggestions": ""},
    "note_buy": {"status": "VALID|NEEDS_REWRITE", "issues": [], "suggestions": ""}
  },
  "revised_content": {
    "title": "виправлений заголовок",
    "description": "виправлений опис",
    "advantages": ["перевага1", "перевага2"],
    "specs": [{"key": "value"}],
    "faq": [{"question": "питання", "answer": "відповідь"}],
    "note_buy": "виправлена примітка"
  }
}
```"""
        else:
            return """Ты — главный редактор и SEO-специалист e-commerce магазина. Твоя задача — провести аудит полного комплекта текстов для карточки товара и вернуть структурированный JSON с вердиктом. Будь предельно строг и внимателен к деталям.

**Входные данные:**
1. `product_facts`: Ключевые характеристики товара (объём, вес, назначение, производитель).
2. `draft_content`: JSON с генерированным контентом (`description`, `advantages`, `specs`, `faq_candidates`, `note_buy`).

**Критерии проверки по блокам:**

1. **`title` (Заголовок товара):**
   - **Полнота:** Заголовок должен содержать полное название товара, включая бренд, объём/вес.
   - **Соответствие локали:** RU заголовки на русском языке, UA — на украинском.
   - **Вердикт:** `VALID` или `INCOMPLETE` с исправленной версией.

2. **`description` (Описание):**
   - **Факт-чекинг:** Соответствует ли текст фактам (объём, назначение)?
   - **Длина и структура:** Не менее 4-5 предложений. Текст должен быть связным и легко читаемым.
   - **SEO и стиль:** Присутствуют ли ключевые слова из названия товара? Тон текста — экспертный, но понятный покупателю.
   - **Вердикт:** `VALID` или `NEEDS_REWRITE` с указанием причин.

3. **`advantages` (Преимущества):**
   - **Уникальность:** Не повторяют ли преимущества друг друга по смыслу?
   - **Ценность:** Являются ли они реальными преимуществами для покупателя, а не общими фразами ("высокое качество")?
   - **Количество:** Должно быть 3-4 уникальных преимущества.
   - **Вердикт:** `VALID` или `NEEDS_REWRITE`.

4. **`specs` (Характеристики):**
   - **ЗАПРЕЩЕНО изменять, добавлять или генерировать характеристики!** Блок specs является read-only - возвращай его без изменений.
   - **НЕ добавляй 'Страна производства', 'Производитель' или любые заглушки, если их нет в исходных данных.**
   - **Вердикт:** `VALID` (всегда, так как блок read-only).

5. **`faq_candidates` (Кандидаты в FAQ, список из ~10):**
   - **Проверка на дубликаты тем:** Найди и отметь как `DUPLICATE_TOPIC` все вопросы на одну тему (хранение, тип кожи и т.д.), кроме первого.
   - **Проверка на generic-ответы:** Найди и отметь как `GENERIC_ANSWER` ответы-заглушки ("согласно инструкции", "на упаковке" и т.п.).
   - **Вердикт:** `VALID` или `NEEDS_FILTERING` с указанием, какие элементы удалить.

6. **`note_buy` (Примечание о покупке):**
   - **Полнота:** Содержит ли полное название товара и коммерческий призыв?
   - **Соответствие локали:** RU текст на русском языке.
   - **Вердикт:** `VALID` или `NEEDS_REWRITE`.

**Формат ответа (строго JSON):**
```json
{
  "overall_status": "VALID|NEEDS_REVISIONS",
  "quality_score": 0.0-1.0,
  "critiques": {
    "title": {"status": "VALID|INCOMPLETE", "issues": [], "suggestions": ""},
    "description": {"status": "VALID|NEEDS_REWRITE", "issues": [], "suggestions": ""},
    "advantages": {"status": "VALID|NEEDS_REWRITE", "issues": [], "suggestions": ""},
    "specs": {"status": "VALID|INCONSISTENT", "issues": [], "suggestions": ""},
    "faq_candidates": {"status": "VALID|NEEDS_FILTERING", "issues": [], "suggestions": ""},
    "note_buy": {"status": "VALID|NEEDS_REWRITE", "issues": [], "suggestions": ""}
  },
  "revised_content": {
    "title": "исправленный заголовок",
    "description": "исправленное описание",
    "advantages": ["преимущество1", "преимущество2"],
    "specs": [{"key": "value"}],
    "faq": [{"question": "вопрос", "answer": "ответ"}],
    "note_buy": "исправленная примечание"
  }
}
```"""
    
    def _create_user_prompt(self, draft_content: Dict[str, Any], product_facts: Dict[str, Any], locale: str) -> str:
        """Создание пользовательского промпта"""
        return f"""
**Факты о товаре:**
{json.dumps(product_facts, ensure_ascii=False, indent=2)}

**Черновик контента:**
{json.dumps(draft_content, ensure_ascii=False, indent=2)}

**Локаль:** {locale}

Проведи комплексную проверку и верни результат в указанном JSON формате.
"""
    
    def _mock_review(self, draft_content: Dict[str, Any], product_facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Mock-результат для тестирования"""
        logger.info("🔧 ContentCritic: Использую mock-результат для тестирования")
        
        return {
            "overall_status": "NEEDS_REVISIONS",
            "quality_score": 0.6,
            "critiques": {
                "title": {"status": "VALID", "issues": [], "suggestions": ""},
                "description": {"status": "NEEDS_REWRITE", "issues": ["Слишком короткий"], "suggestions": "Добавить больше деталей"},
                "advantages": {"status": "VALID", "issues": [], "suggestions": ""},
                "specs": {"status": "VALID", "issues": [], "suggestions": ""},
                "faq_candidates": {"status": "NEEDS_FILTERING", "issues": ["Есть дубликаты"], "suggestions": "Удалить повторяющиеся темы"},
                "note_buy": {"status": "VALID", "issues": [], "suggestions": ""}
            },
            "revised_content": {
                "title": draft_content.get('title', ''),
                "description": draft_content.get('description', ''),
                "advantages": draft_content.get('advantages', []),
                "specs": draft_content.get('specs', []),
                "faq": draft_content.get('faq_candidates', [])[:6],  # Берем первые 6
                "note_buy": draft_content.get('note_buy', '')
            }
        }
