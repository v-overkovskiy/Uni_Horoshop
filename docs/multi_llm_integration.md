# Интеграция MultiLLMClient с автоматическим fallback

## Обзор

Система теперь поддерживает автоматический fallback между OpenAI GPT-4o-mini и Anthropic Claude для обеспечения 100% обработки товаров, даже при отказе одного из LLM.

## Архитектура

### MultiLLMClient

Унифицированный клиент, который:
1. **Сначала пробует OpenAI GPT-4o-mini** для генерации контента
2. **Автоматически переключается на Claude** при:
   - Отказе OpenAI (content policy)
   - Ошибках API
   - Недоступности OpenAI

### Интеграция в генераторы

Обновлены следующие модули:
- `src/llm/unified_content_generator.py`
- `src/processing/advantages_generator.py`
- `src/processing/faq_generator.py`
- `src/processing/characteristics_translator.py`

## Настройка API ключей

### Переменные окружения

```bash
# OpenAI (основной)
OPENAI_API_KEY=sk-your-openai-key

# Anthropic (fallback)
ANTHROPIC_API_KEY=sk-ant-api03-your-anthropic-key
```

### Автоматическая проверка

Система автоматически:
- Проверяет наличие API ключей
- Предупреждает о недоступности провайдеров
- Переключается на доступный fallback

## Статистика использования

### Методы мониторинга

```python
# Получить статистику
stats = client.get_stats()
print(f"OpenAI успешно: {stats['openai_success']}")
print(f"OpenAI отказов: {stats['openai_failed']}")
print(f"Claude fallback: {stats['claude_used']}")

# Вывести в консоль
client.print_stats()
```

### Пример вывода

```
================================================================================
📊 СТАТИСТИКА ИСПОЛЬЗОВАНИЯ LLM:
================================================================================
   ✅ OpenAI успешно: 45
   ❌ OpenAI отказов: 3
   🔄 Claude fallback: 3
   📈 Процент Claude: 6.3%
================================================================================
```

## Обработка отказов

### Детекция отказов

Система автоматически определяет отказы по:
- Ключевым фразам: "запрещено", "не могу", "cannot"
- Слишком коротким ответам (< 20 символов)
- Шаблонным ответам: "качественный продукт"

### Автоматический fallback

При обнаружении отказа:
1. Логируется причина отказа
2. Автоматически переключается на Claude
3. Генерирует контент через fallback
4. Обновляет статистику

## Примеры использования

### Базовое использование

```python
from src.llm.multi_llm_client import MultiLLMClient

client = MultiLLMClient()

# Генерация с автоматическим fallback
content = await client.generate(
    prompt="Создай описание товара",
    max_tokens=500,
    temperature=0.7
)
```

### В генераторах контента

```python
class AdvantagesGenerator:
    def __init__(self):
        self.llm = MultiLLMClient()
    
    async def generate_advantages(self, product_facts, locale):
        prompt = self._build_prompt(product_facts, locale)
        
        # Автоматический fallback при отказе
        response = await self.llm.generate(prompt, max_tokens=300)
        
        return self._parse_response(response)
```

## Преимущества

### Надежность
- **100% обработка товаров** даже при отказе основного LLM
- **Автоматическое восстановление** при ошибках
- **Гибкая архитектура** для добавления новых провайдеров

### Мониторинг
- **Детальная статистика** использования каждого LLM
- **Логирование** всех переключений и отказов
- **Метрики производительности** для оптимизации

### Качество
- **Claude для чувствительных товаров** (косметика, депиляция)
- **OpenAI для стандартного контента**
- **Единый интерфейс** для всех генераторов

## Настройка модели Claude

По умолчанию используется `claude-instant-1`. Для изменения:

```python
# В src/llm/multi_llm_client.py
response = await self.claude.messages.create(
    model="claude-3-sonnet-20240229",  # Ваша модель
    # ...
)
```

## Логирование

Все операции логируются с соответствующими уровнями:

- `INFO`: Успешные операции
- `WARNING`: Переключения и отказы
- `ERROR`: Критические ошибки

## Заключение

Интеграция MultiLLMClient обеспечивает:
- ✅ 100% обработку товаров
- ✅ Автоматический fallback
- ✅ Детальную статистику
- ✅ Единую архитектуру
- ✅ Легкую расширяемость

Система готова к продакшену и может обрабатывать любые категории товаров без сбоев.
