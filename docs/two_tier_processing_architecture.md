# Двухуровневая Архитектура Обработки Товаров

## 🎯 Концепция

Система использует **двухуровневую обработку** для обеспечения максимальной надёжности при оптимальных затратах:

```
┌─────────────────────────────────────────────────────────┐
│                    Входящий товар                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   УРОВЕНЬ 1: GPT-4o-mini     │
        │   (Быстро и дёшево)          │
        └──────────────┬─────────────────┘
                       │
                       ├─── ✅ Успех → Валидация → Готово
                       │
                       └─── ❌ Провал
                              │
                              ▼
                ┌──────────────────────────────┐
                │ УРОВЕНЬ 2: Claude 3.5 Sonnet │
                │   (Максимальная надёжность)  │
                └──────────────┬───────────────┘
                               │
                               ├─── ✅ Успех → Валидация → Готово
                               │
                               └─── ❌ Провал → Status: failed
```

## 📊 Статистика и Оптимизация

### Ожидаемое распределение:
- **85-90%** товаров обрабатываются GPT-4o-mini (дёшево)
- **10-15%** товаров требуют Claude fallback (дорого)
- **<1%** товаров полностью проваливаются

### Стоимость обработки:
- **GPT-4o-mini:** $0.15/1M input + $0.60/1M output
- **Claude 3.5 Sonnet:** $3.00/1M input + $15.00/1M output

**Экономия:** ~90% по сравнению с использованием только Claude

## 🔧 Реализация

### 1. Первичная Обработка (GPT-4o-mini)

**Файл:** `src/core/async_product_processor.py` → `process_product()`

```python
try:
    # Обработка через GPT-4o-mini
    ru_result = await self._process_locale(ru_html, ru_url, 'ru', ...)
    ua_result = await self._process_locale(ua_html, ua_url, 'ua', ...)
    
    # Валидация результата
    if not self._validate_processing_result(final_result):
        raise ValueError("Неполный результат")
    
    return final_result  # ✅ Успех
    
except Exception as e:
    # Переход на уровень 2
    ...
```

### 2. Fallback Обработка (Claude 3.5 Sonnet)

**Файл:** `src/core/async_product_processor.py` → `_process_product_resilient()`

```python
try:
    # Инициализируем Claude 3.5 Sonnet для recovery
    claude_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    self.llm_recovery.llm = claude_client
    self.llm_recovery.model = "claude-3-5-sonnet-20241022"
    
    # Обработка через Claude 3.5 Sonnet
    recovery_result = await self._process_product_resilient(...)
    
    # ✅ КРИТИЧНО: Валидация ПЕРЕД возвратом
    is_valid, issues = self._validate_content_quality(recovery_result)
    
    if is_valid:
        return recovery_result  # ✅ Успех
    else:
        # ❌ Даже Claude 3.5 Sonnet не справился
        raise ValueError("Recovery не прошёл валидацию")
        
except Exception as e:
    # Финальный провал
    raise ValueError(f"Не удалось обработать товар: {e}")
```

## ✅ Валидация Качества

### Критерии валидации:

```python
def _validate_content_quality(result: Dict[str, Any]) -> tuple[bool, list[str]]:
    """Строгая валидация качества контента"""
    
    # 1. FAQ - критически важно
    if ru_faq < 4: issues.append("RU FAQ: недостаточно")
    if ua_faq < 4: issues.append("UA FAQ: недостаточно")
    
    # 2. Описания
    if ru_html.count('</p>') < 2: issues.append("RU описание неполное")
    if ua_html.count('</p>') < 2: issues.append("UA описание неполное")
    
    # 3. Преимущества
    if ru_benefits < 3: issues.append("RU преимущества: мало")
    if ua_benefits < 3: issues.append("UA преимущества: мало")
    
    # 4. Размер HTML
    if len(ru_html) < 1500: issues.append("RU HTML слишком короткий")
    if len(ua_html) < 1500: issues.append("UA HTML слишком короткий")
    
    # 5. Заглушки
    if 'error-message' in ru_html: issues.append("Заглушки в HTML")
    
    return (len(issues) == 0, issues)
```

## 🔄 Процесс Обработки

### Шаг 1: Попытка через GPT-4o-mini
```
INFO - 🔄 Начинаю обработку товара: <url>
INFO - Генерация контента через GPT-4o-mini...
```

**Успех:**
```
INFO - ✅ Товар обработан: <url>
INFO - ✅ Товар обработан успешно: <url>
```

**Провал:**
```
ERROR - ❌ КРИТИЧЕСКАЯ ОШИБКА обработки товара: <error>
INFO - 🛡️ Запускаем resilient recovery (Claude fallback)
```

### Шаг 2: Fallback через Claude 3.5 Sonnet
```
INFO - 🟣 Resilient recovery использует Claude 3.5 Sonnet для максимальной надёжности
INFO - 🛡️ Resilient processing: <url>
```

**Успех:**
```
INFO - ✅ Resilient recovery успешен и прошёл валидацию: <url>
```

**Провал:**
```
ERROR - ❌ Resilient recovery НЕ прошёл валидацию: <url>
ERROR -    Проблемы: RU FAQ: 0 (нужно ≥4), UA FAQ: 0 (нужно ≥4)
```

### Шаг 3: Финальный результат
```python
result = {
    'url': product_url,
    'status': 'success' | 'failed',
    'error': '<детали ошибки>' if failed,
    'ru_html': '<html>',
    'ua_html': '<html>',
    ...
}
```

## 📈 Мониторинг

### Ключевые метрики:

1. **Success Rate:**
   - GPT-4o-mini success rate
   - Claude fallback success rate
   - Overall success rate

2. **Стоимость:**
   - Средняя стоимость на товар
   - Общая стоимость обработки
   - Экономия от двухуровневой архитектуры

3. **Качество:**
   - FAQ coverage (среднее количество вопросов)
   - Описания coverage (среднее количество параграфов)
   - Преимущества coverage (среднее количество карточек)

### Пример статистики:
```
📊 СТАТИСТИКА ОБРАБОТКИ
═══════════════════════════════════════════
Всего URL: 100
Успешно обработано: 95
Ошибок: 5
Процент успеха: 95.0%

📝 ДЕТАЛИ ОБРАБОТКИ:
  GPT-4o-mini успех: 85 (85%)
  Claude fallback: 10 (10%)
  Полный провал: 5 (5%)

💰 СТОИМОСТЬ:
  GPT-4o-mini: $2.50
  Claude: $5.00
  Итого: $7.50
  Экономия vs только Claude: 85%
```

## 🚀 Оптимизация

### Настройки параллелизма:

**Файл:** `scripts/enhanced_async_pipeline.py`

```python
CONCURRENT_PRODUCTS = 8   # Параллельная обработка товаров
LLM_CONCURRENCY = 4       # Параллельные LLM запросы (уменьшено для rate limit)
TIMEOUT = 45              # Таймаут обработки
MAX_RETRIES = 2           # Количество попыток
```

### Rate Limit Management:

Для избежания rate limit от API:
1. Уменьшить `LLM_CONCURRENCY` (4-8 вместо 16)
2. Добавить задержки между запросами
3. Использовать экспоненциальный backoff при ошибках 429

## 🎯 Критерии Успеха

### Товар считается успешно обработанным если:

✅ **Обязательные критерии:**
- RU FAQ: ≥4 вопроса
- UA FAQ: ≥4 вопроса
- RU описание: ≥2 параграфа
- UA описание: ≥2 параграфа
- RU преимущества: ≥3 карточки
- UA преимущества: ≥3 карточки
- RU HTML: ≥1500 байт
- UA HTML: ≥1500 байт

✅ **Дополнительные критерии:**
- Нет заглушек (`error-message`)
- Нет пустых блоков (заголовок есть, контента нет)
- Все обязательные поля заполнены

## 📝 Итоги

### Преимущества двухуровневой архитектуры:

1. **Экономия:** ~85-90% снижение затрат на API
2. **Надёжность:** Fallback на Claude для проблемных товаров
3. **Скорость:** GPT-4o-mini быстрее Claude
4. **Качество:** Строгая валидация на обоих уровнях
5. **Масштабируемость:** Готово к обработке тысяч товаров

### Универсальность:

Система спроектирована как **универсальный комбайн** для обработки любых товаров:
- Автоматическое определение проблемных товаров
- Адаптивная маршрутизация LLM
- Строгая валидация качества
- Детальное логирование для анализа
- Гибкие настройки параллелизма
