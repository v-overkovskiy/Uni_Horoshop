# 🤖 ProRazko Product Pipeline

**Автоматизированная система генерации SEO-описаний товаров с двухуровневой LLM архитектурой**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Success Rate](https://img.shields.io/badge/Success%20Rate-85.7%25-brightgreen.svg)](https://github.com/v-overkovskiy/ProRazko_Product_Pipeline)

## 📋 Описание

Универсальный комбайн для автоматической генерации качественных описаний товаров на русском и украинском языках. Система использует двухуровневую архитектуру обработки с умным переключением между моделями для достижения оптимального баланса скорости, качества и стоимости.

### ✨ Ключевые возможности

- 🚀 **Двухуровневая обработка**: GPT-4o-mini для быстрой обработки + Claude 3.5 Sonnet для сложных случаев
- 🌍 **Мультиязычность**: Генерация контента на русском и украинском языках с независимой оптимизацией
- ✅ **Строгая валидация**: Автоматическая проверка качества контента перед публикацией
- 📊 **Умная маршрутизация**: Автоматический выбор оптимальной LLM модели на основе типа контента
- 🔄 **Пакетный перевод**: Эффективный перевод FAQ и контента одним запросом
- 🛡️ **Resilient Recovery**: Автоматическое восстановление при сбоях с переключением на более мощную модель

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    Входящий товар                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │   УРОВЕНЬ 1: GPT-4o-mini     │
        │   (Быстро и дёшево)          │
        │   Success Rate: ~85%         │
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
                │   Success Rate: ~95%         │
                └──────────────┬───────────────┘
                               │
                               ├─── ✅ Успех → Валидация → Готово
                               │
                               └─── ❌ Провал → Status: failed
```

### 🎯 Генерируемый контент

Для каждого товара система генерирует:

- **📝 SEO-описание**: 2-3 параграфа с ключевыми словами
- **✨ Преимущества**: 3-6 уникальных преимуществ товара
- **❓ FAQ**: 4-6 вопросов-ответов для улучшения SEO
- **🔧 Характеристики**: Структурированная таблица параметров
- **📱 Telegram-контент**: Скрытые блоки для каналов
- **🖼️ Изображения**: Автоматический подбор качественных фото

## 🚀 Быстрый старт

### Требования

- Python 3.12+
- OpenAI API Key
- Anthropic API Key

### Установка

```bash
# Клонируем репозиторий
git clone https://github.com/v-overkovskiy/ProRazko_Product_Pipeline.git
cd ProRazko_Product_Pipeline

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Устанавливаем зависимости
pip install -r requirements.txt

# Настраиваем переменные окружения
cp .env.example .env
# Отредактируйте .env и добавьте ваши API ключи
```

### Настройка `.env`

```env
# OpenAI API (для GPT-4o-mini)
OPENAI_API_KEY=sk-...

# Anthropic API (для Claude 3.5 Sonnet)
ANTHROPIC_API_KEY=sk-ant-...

# Конфигурация
DEFAULT_LOCALE=uk
```

### Использование

```bash
# Добавьте URL товаров в urls.txt (по одному на строку)
echo "https://example.com/product-1" >> urls.txt
echo "https://example.com/product-2" >> urls.txt

# Запустите обработку
python3 scripts/enhanced_async_pipeline.py

# Результаты будут сохранены в descriptions.xlsx
```

## 📊 Результаты

**Текущая производительность:**

| Метрика | Значение |
|---------|----------|
| **Успешность обработки** | 85.7% |
| **Среднее время на товар** | ~20 секунд |
| **FAQ на товар** | 4-6 вопросов |
| **Преимущества на товар** | 3-6 карточек |
| **Поддерживаемые языки** | RU, UA |

## 📁 Структура проекта

```
ProRazko_Product_Pipeline/
├── configs/           # Конфигурационные файлы
├── docs/             # Документация архитектуры
├── prompts/          # Промпты для LLM моделей
├── scripts/          # Скрипты запуска
├── src/
│   ├── adapters/     # Адаптеры парсеров
│   ├── core/         # Основная логика обработки
│   ├── export/       # Экспорт результатов
│   ├── fetcher/      # Загрузка контента
│   ├── llm/          # LLM клиенты и генераторы
│   ├── processing/   # Обработка контента
│   ├── recovery/     # Механизмы восстановления
│   └── validation/   # Валидация контента
├── templates/        # HTML шаблоны
├── requirements.txt  # Зависимости Python
└── README.md
```

## 🔧 Конфигурация

### Настройка валидации качества

Отредактируйте `src/core/async_product_processor.py`:

```python
def _validate_content_quality(self, result: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Настройте минимальные требования к контенту"""
    
    # Минимальное количество FAQ
    min_faq = 4  # Измените по необходимости
    
    # Минимальное количество преимуществ
    min_advantages = 3  # Измените по необходимости
    
    # Минимальный размер HTML
    min_html_size = 1500  # байт
```

### Настройка LLM моделей

Отредактируйте `src/llm/smart_llm_client.py`:

```python
# Выбор модели по умолчанию
self.primary_provider = "openai"  # или "claude"

# Настройка температуры генерации
temperature = 0.7  # 0.0 - детерминированно, 1.0 - креативно
```

## 🧪 Тестирование

```bash
# Запуск тестов
python3 -m pytest tests/

# Тестирование на одном товаре
echo "https://example.com/product" > test_urls.txt
python3 scripts/enhanced_async_pipeline.py
```

## 📖 Документация

Полная документация доступна в директории `docs/`:

- [Архитектура двухуровневой обработки](docs/two_tier_processing_architecture.md)
- [Интеграция нескольких LLM](docs/multi_llm_integration.md)
- [Умная маршрутизация запросов](docs/smart_routing_success.md)
- [Универсальные правила генерации](docs/universal_rules.md)

## 🛠️ Разработка

### Добавление нового парсера

```python
# Создайте новый адаптер в src/adapters/
class MyCustomParser:
    async def parse_product(self, html: str, url: str) -> Dict[str, Any]:
        # Ваша логика парсинга
        return {
            'title': '...',
            'specs': [...],
            'description': '...'
        }
```

### Добавление нового языка

```python
# Добавьте правила в src/locale/
class NewLanguageRules:
    def format_text(self, text: str) -> str:
        # Правила форматирования для нового языка
        pass
```

## 🤝 Вклад в проект

Приветствуются любые улучшения! Пожалуйста:

1. Форкните репозиторий
2. Создайте ветку для вашей функции (`git checkout -b feature/AmazingFeature`)
3. Закоммитьте изменения (`git commit -m 'Add some AmazingFeature'`)
4. Отправьте в ветку (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📝 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 🙏 Благодарности

- OpenAI за GPT-4o-mini API
- Anthropic за Claude 3.5 Sonnet API
- Все контрибьюторы проекта

## 📞 Контакты

**Вячеслав Оверковский** - [@v-overkovskiy](https://github.com/v-overkovskiy)

**Ссылка на проект:** https://github.com/v-overkovskiy/ProRazko_Product_Pipeline

---

⭐ Если этот проект был полезен, поставьте звезду!

