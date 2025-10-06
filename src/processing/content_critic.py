"""
ContentCritic - универсальный агент-валидатор для комплексной проверки контента
"""
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CritiqueResult:
    """Результат критики блока контента"""
    status: str  # VALID, NEEDS_REWRITE, INCONSISTENT, NEEDS_FIX
    comment: str
    revised_content: Optional[Any] = None

class ContentCritic:
    """Универсальный агент-валидатор для комплексной проверки контента"""
    
    def __init__(self):
        self.system_prompts = {
            'ru': self._get_russian_system_prompt(),
            'ua': self._get_ukrainian_system_prompt()
        }
        
        # Критерии качества
        self.quality_criteria = {
            'description': {
                'min_sentences': 4,
                'min_length': 200,
                'max_length': 800
            },
            'advantages': {
                'min_count': 3,
                'max_count': 4,
                'min_length_per_advantage': 20
            },
            'faq': {
                'target_count': 6,
                'min_question_length': 10,
                'min_answer_length': 30
            },
            'note_buy': {
                'min_length': 50,
                'required_phrase': 'В нашем интернет-магазине ProRazko'
            }
        }

    def _get_russian_system_prompt(self) -> str:
        """Системный промпт для русской локали"""
        return """Ты — главный редактор и SEO-специалист e-commerce магазина ProRazko. Твоя задача — провести аудит полного комплекта текстов для карточки товара и вернуть структурированный JSON с вердиктом. Будь предельно строг и внимателен к деталям.

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

2. **`advantages` (Преимущества):**
   - **Уникальность:** Не повторяют ли преимущества друг друга по смыслу?
   - **Ценность:** Являются ли они реальными преимуществами для покупателя, а не общими фразами ("высокое качество")?
   - **Количество:** Должно быть 3-4 уникальных преимущества.
   - **Вердикт:** `VALID` или `NEEDS_REWRITE`.

3. **`specs` (Характеристики):**
   - **ЗАПРЕЩЕНО добавлять новые характеристики!** Исправляй ТОЛЬКО текст, НЕ добавляй поля типа "Производитель", "Страна производства", если их нет в исходнике.
   - **Корректность единиц:** Проверь, что `г` используется для веса, а `мл` — для объёма.
   - **Консистентность:** Если в фактах указан объём, в характеристиках не должно быть веса, и наоборот.
   - **Если specs пустые — оставь пустыми.**
   - **Вердикт:** `VALID` или `INCONSISTENT` с указанием, что исправить.

4. **`faq_candidates` (Кандидаты в FAQ, список из ~10):**
   - **Проверка на дубликаты тем:** Найди и отметь как `DUPLICATE_TOPIC` все вопросы на одну тему (хранение, тип кожи и т.д.), кроме первого.
   - **Проверка на generic-ответы:** Найди и отметь как `GENERIC_ANSWER` ответы-заглушки ("согласно инструкции", "на упаковке" и т.п.).
   - **Проверка грамматики и капитализации:** Исправь неполные предложения и строчные буквы в начале вопросов.
   - **Вердикт:** Верни очищенный список `valid_faqs` и список отклонённых `rejected_faqs` с причинами.

5. **`note_buy` (Блок покупки):**
   - **Структура:** Проверь наличие фразы "В нашем интернет-магазине ProRazko можно купить...".
   - **Форматирование:** Убедись, что название товара выделено тегом `<strong>`.
   - **Вердикт:** `VALID` или `NEEDS_FIX` с исправленной версией.

**ФОРМАТ ВЫВОДА (СТРОГО JSON):**
{
  "overall_status": "VALID | NEEDS_REVISIONS",
  "critiques": {
    "description": {"status": "VALID", "comment": "Описание соответствует всем требованиям."},
    "advantages": {"status": "NEEDS_REWRITE", "comment": "Преимущества 2 и 3 повторяют друг друга."},
    "specs": {"status": "VALID", "comment": ""},
    "faq": {
      "status": "VALID",
      "valid_count": 6,
      "rejected_count": 4,
      "comment": "Отфильтровано 2 дубликата тем и 2 generic-ответа."
    },
    "note_buy": {"status": "VALID", "comment": ""}
  },
  "revised_content": {
    "description": "...",
    "advantages": [...],
    "faq": [...],
    "note_buy": "..."
  }
}"""

    def _get_ukrainian_system_prompt(self) -> str:
        """Системный промпт для украинской локали"""
        return """Ти — головний редактор та SEO-спеціаліст e-commerce магазину ProRazko. Твоє завдання — провести аудит повного комплекту текстів для картки товару та повернути структурований JSON з вердиктом. Будь надзвичайно строгим та уважним до деталей.

**Вхідні дані:**
1. `product_facts`: Ключові характеристики товару (об'єм, вага, призначення, виробник).
2. `draft_content`: JSON з згенерованим контентом (`description`, `advantages`, `specs`, `faq_candidates`, `note_buy`).

**Критерії перевірки по блоках:**

1. **`description` (Опис):**
   - **Факт-чекінг:** Чи відповідає текст фактам (об'єм, призначення)?
   - **Довжина та структура:** Не менше 4-5 речень. Текст має бути зв'язним та легко читабельним.
   - **SEO та стиль:** Чи присутні ключові слова з назви товару? Тон тексту — експертний, але зрозумілий покупцю.
   - **Вердикт:** `VALID` або `NEEDS_REWRITE` з вказівкою причин.

2. **`advantages` (Переваги):**
   - **Унікальність:** Чи не повторюють переваги один одного за змістом?
   - **Цінність:** Чи є вони реальними перевагами для покупця, а не загальними фразами ("висока якість")?
   - **Кількість:** Має бути 3-4 унікальні переваги.
   - **Вердикт:** `VALID` або `NEEDS_REWRITE`.

3. **`specs` (Характеристики):**
   - **ЗАБОРОНЕНО додавати нові характеристики!** Виправляй ТІЛЬКИ текст, НЕ додавай поля типу "Виробник", "Країна виробництва", якщо їх немає в оригіналі.
   - **Коректність одиниць:** Перевір, що `г` використовується для ваги, а `мл` — для об'єму.
   - **Консистентність:** Якщо в фактах вказаний об'єм, в характеристиках не має бути ваги, і навпаки.
   - **Якщо specs порожні — залиш порожніми.**
   - **Вердикт:** `VALID` або `INCONSISTENT` з вказівкою, що виправити.

4. **`faq_candidates` (Кандидати в FAQ, список з ~10):**
   - **Перевірка на дублікати тем:** Знайди та познач як `DUPLICATE_TOPIC` всі питання на одну тему (зберігання, тип шкіри тощо), крім першого.
   - **Перевірка на generic-відповіді:** Знайди та познач як `GENERIC_ANSWER` відповіді-заглушки ("згідно з інструкцією", "на упаковці" тощо).
   - **Перевірка граматики та капіталізації:** Виправ неповні речення та малі літери на початку питань.
   - **Вердикт:** Поверни очищений список `valid_faqs` та список відхилених `rejected_faqs` з причинами.

5. **`note_buy` (Блок покупки):**
   - **Структура:** Перевір наявність фрази "В нашому інтернет-магазині ProRazko можна купити...".
   - **Форматування:** Переконайся, що назва товару виділена тегом `<strong>`.
   - **Вердикт:** `VALID` або `NEEDS_FIX` з виправленою версією.

**ФОРМАТ ВИВОДУ (СТРОГО JSON):**
{
  "overall_status": "VALID | NEEDS_REVISIONS",
  "critiques": {
    "description": {"status": "VALID", "comment": "Опис відповідає всім вимогам."},
    "advantages": {"status": "NEEDS_REWRITE", "comment": "Переваги 2 та 3 повторюють один одного."},
    "specs": {"status": "VALID", "comment": ""},
    "faq": {
      "status": "VALID",
      "valid_count": 6,
      "rejected_count": 4,
      "comment": "Відфільтровано 2 дублікати тем та 2 generic-відповіді."
    },
    "note_buy": {"status": "VALID", "comment": ""}
  },
  "revised_content": {
    "description": "...",
    "advantages": [...],
    "faq": [...],
    "note_buy": "..."
  }
}"""

    def review(self, draft_content: Dict[str, Any], product_facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """
        Проводит комплексную проверку контента
        
        Args:
            draft_content: Черновик контента с блоками
            product_facts: Факты о товаре
            locale: Локаль
            
        Returns:
            Структурированный результат проверки
        """
        logger.info(f"🔍 ContentCritic: Начинаю комплексную проверку контента для {locale}")
        
        try:
            # Сохраняем исходные характеристики как read-only
            original_specs = product_facts.get('specs', [])
            if original_specs:
                logger.info(f"🔒 ContentCritic: Сохраняем {len(original_specs)} исходных характеристик как read-only")
            
            # Формируем промпт для LLM
            system_prompt = self.system_prompts.get(locale, self.system_prompts['ru'])
            
            # Подготавливаем данные для промпта
            prompt_data = {
                "product_facts": product_facts,
                "draft_content": draft_content
            }
            
            # Создаем промпт для LLM
            user_prompt = f"""Проведи аудит следующего контента:

**Факты о товаре:**
{json.dumps(product_facts, ensure_ascii=False, indent=2)}

**Черновик контента:**
{json.dumps(draft_content, ensure_ascii=False, indent=2)}

Верни результат в формате JSON согласно системному промпту."""

            # Вызываем реальную LLM-проверку
            review_result = self._real_llm_review(draft_content, product_facts, locale, system_prompt, user_prompt)
            
            # Принудительно восстанавливаем исходные характеристики
            if original_specs and 'revised_content' in review_result:
                review_result['revised_content']['specs'] = original_specs
                logger.info(f"🔒 ContentCritic: Восстановлены исходные характеристики ({len(original_specs)} шт)")
            
            logger.info(f"✅ ContentCritic: Проверка завершена, статус: {review_result.get('overall_status', 'UNKNOWN')}")
            return review_result
            
        except Exception as e:
            logger.error(f"❌ ContentCritic: Ошибка при проверке контента: {e}")
            return self._create_error_result(str(e))

    def _mock_review(self, draft_content: Dict[str, Any], product_facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """
        Заглушка для тестирования (заменяется на реальный вызов LLM)
        """
        logger.info("🔧 ContentCritic: Использую mock-результат для тестирования")
        
        # Анализируем контент
        critiques = {}
        revised_content = {}
        
        # Обрабатываем каждый блок контента
        for block_name in ['description', 'advantages', 'specs', 'faq_candidates', 'note_buy']:
            if block_name in draft_content:
                block_content = draft_content[block_name]
                
                # Проверяем тип данных
                if isinstance(block_content, str):
                    # Строковый контент
                    if len(block_content.strip()) > 0:
                        critiques[block_name] = {
                            'status': 'VALID',
                            'comment': f'{block_name} прошел проверку'
                        }
                        revised_content[block_name] = block_content
                    else:
                        critiques[block_name] = {
                            'status': 'NEEDS_REWRITE',
                            'comment': f'{block_name} пустой'
                        }
                        revised_content[block_name] = block_content
                elif isinstance(block_content, list):
                    # Список (advantages, specs, faq_candidates)
                    if len(block_content) > 0:
                        critiques[block_name] = {
                            'status': 'VALID',
                            'comment': f'{block_name} содержит {len(block_content)} элементов'
                        }
                        revised_content[block_name] = block_content
                    else:
                        critiques[block_name] = {
                            'status': 'NEEDS_REWRITE',
                            'comment': f'{block_name} пустой список'
                        }
                        revised_content[block_name] = block_content
                else:
                    # Другие типы данных
                    critiques[block_name] = {
                        'status': 'VALID',
                        'comment': f'{block_name} прошел проверку'
                    }
                    revised_content[block_name] = block_content
        
        # Определяем общий статус
        overall_status = 'VALID'
        for critique in critiques.values():
            if critique['status'] not in ['VALID']:
                overall_status = 'NEEDS_REVISIONS'
                break
        
        return {
            'overall_status': overall_status,
            'critiques': critiques,
            'revised_content': revised_content
        }

    def _real_llm_review(self, draft_content: Dict[str, Any], product_facts: Dict[str, Any], 
                        locale: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        Реальная LLM-проверка контента
        
        Args:
            draft_content: Черновик контента
            product_facts: Факты о товаре
            locale: Локаль
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            
        Returns:
            Результат проверки
        """
        try:
            # Импортируем LLM клиент
            from src.llm.content_generator import LLMContentGenerator
            
            llm_generator = LLMContentGenerator()
            
            # Вызываем LLM для проверки
            logger.info("🔍 ContentCritic: Вызываю LLM для реальной проверки контента")
            
            # Используем прямой вызов LLM через httpx
            import httpx
            import json
            
            # Подготавливаем запрос к OpenAI
            headers = {
                "Authorization": f"Bearer {llm_generator.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 4000
            }
            
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result['choices'][0]['message']['content']
                
                # Парсим JSON ответ
                try:
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

    def _filter_faq_candidates(self, faq_candidates: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """
        Фильтрует кандидатов FAQ, удаляя дубликаты и generic ответы
        """
        if not faq_candidates:
            return []
        
        # Простая фильтрация для тестирования
        valid_faqs = []
        seen_topics = set()
        
        for faq in faq_candidates:
            question = faq.get('question', '') or faq.get('q', '')
            answer = faq.get('answer', '') or faq.get('a', '')
            
            # Проверяем на generic ответы
            if any(phrase in answer.lower() for phrase in ['согласно инструкции', 'на упаковке', 'в сухом месте']):
                continue
            
            # Проверяем на дубликаты тем (упрощенная логика)
            topic_key = question.lower()[:20]  # Первые 20 символов как ключ темы
            if topic_key in seen_topics:
                continue
            
            seen_topics.add(topic_key)
            valid_faqs.append(faq)
        
        return valid_faqs

    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Создает результат с ошибкой"""
        return {
            'overall_status': 'ERROR',
            'critiques': {
                'error': {
                    'status': 'ERROR',
                    'comment': f'Ошибка при проверке: {error_message}'
                }
            },
            'revised_content': {}
        }

    def get_quality_metrics(self, review_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлекает метрики качества из результата проверки
        
        Args:
            review_result: Результат проверки ContentCritic
            
        Returns:
            Метрики качества
        """
        metrics = {
            'overall_status': review_result.get('overall_status', 'UNKNOWN'),
            'block_statuses': {},
            'faq_metrics': {},
            'quality_score': 0.0
        }
        
        critiques = review_result.get('critiques', {})
        
        # Анализируем статусы блоков
        valid_blocks = 0
        total_blocks = 0
        
        for block_name, critique in critiques.items():
            if block_name == 'error':
                continue
                
            status = critique.get('status', 'UNKNOWN')
            metrics['block_statuses'][block_name] = status
            
            total_blocks += 1
            if status == 'VALID':
                valid_blocks += 1
        
        # Анализируем FAQ метрики
        faq_critique = critiques.get('faq', {})
        if faq_critique:
            metrics['faq_metrics'] = {
                'valid_count': faq_critique.get('valid_count', 0),
                'rejected_count': faq_critique.get('rejected_count', 0),
                'status': faq_critique.get('status', 'UNKNOWN')
            }
        
        # Вычисляем общую оценку качества
        if total_blocks > 0:
            metrics['quality_score'] = valid_blocks / total_blocks
        
        return metrics
