"""
Универсальный извлекатель компонентов наборов с расширенным поиском и фолбэком
"""
import re
import logging
from bs4 import BeautifulSoup
from typing import List

logger = logging.getLogger(__name__)

# Расширенные индикаторы состава набора на русском и украинском
INDICATORS = [
    r"в\s+комплект\s+входит",
    r"комплектаци(я|я:)",
    r"состав\s+набора",
    r"в\s+стартовый\s+набор\s+входит",
    r"в\s+набір\s+входить",
    r"склад\s+набору",
    r"комплектація",
    r"комплект\s+включает",
    r"набір\s+включає",
    r"в\s+набор\s+входит",
    r"в\s+комплект\s+включено",
    r"комплект\s+содержит",
    r"набір\s+містить",
    r"в\s+комплект\s+входят",
    r"в\s+набір\s+входять"
]

# Компилируем регулярное выражение для поиска индикаторов
INDICATOR_RE = re.compile("|".join(INDICATORS), re.I | re.U)

# Паттерн для поиска компонентов в тексте
COMPONENT_PAT = re.compile(r"([A-Za-zА-Яа-я0-9\s\-,]+(?:\s[0-9]+(?:\s[гмлштВт]+)?))")

# Расширенные бренды и ключевые слова для фильтрации
BRAND_FILTERS = [
    'Pro Wax', 'ItalWAX', 'Epilax', 'Coral', 'Depilax', 
    'ProRazko', 'Wax', 'Gel', 'Foam', 'Cream', 'воскоплав',
    'воск', 'пудра', 'тальк', 'шпатель', 'гель', 'пінка',
    'флюїд', 'флюид', 'крем', 'лосьйон', 'масло', 'спрей'
]

def filter_bundle_only_if_explicit(html: str) -> bool:
    """
    Проверяет, есть ли в HTML явные маркеры состава набора
    
    Args:
        html: HTML страницы товара
        
    Returns:
        True если найдены явные маркеры состава набора
    """
    explicit_phrases = [
        r"состав[:\\-]", r"склад[:\\-]", r"комплект[а-я]*[:\\-]",
        r"набор[а-я]*[:\\-]", r"комплектация[:\\-]",
        r"в\s+наборе\s+входят", r"в\s+комплект[е|ах]?\s+входят",
        r"в\s+набір\s+входять", r"в\s+комплект\s+входить",
        r"склад\s+набору", r"состав\s+набора", r"комплектація"
    ]
    
    for phrase in explicit_phrases:
        if re.search(phrase, html, re.I | re.U):
            logger.info(f"✅ Найден явный маркер состава: {phrase}")
            return True
    
    logger.info("❌ Явные маркеры состава набора не найдены")
    return False

def extract_bundle_components(html: str) -> List[str]:
    """
    Универсальный извлекатель компонентов наборов с расширенным поиском и фолбэком
    Теперь извлекает состав ТОЛЬКО при наличии явных маркеров
    
    Args:
        html: HTML страницы товара
        
    Returns:
        Список компонентов набора (пустой если нет явных маркеров)
    """
    if not html:
        return []
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА: извлекаем состав только при явных маркерах
    if not filter_bundle_only_if_explicit(html):
        logger.info("🚫 Состав набора не извлекается - нет явных маркеров")
        return []
    
    soup = BeautifulSoup(html, "html.parser")
    items = []
    
    # 1. Поиск по заголовкам + UL/OL
    headers = soup.find_all(lambda tag: 
        tag.name in ['h2', 'h3', 'h4', 'strong', 'p', 'div'] and 
        INDICATOR_RE.search(tag.get_text(strip=True))
    )
    
    for header in headers:
        logger.debug(f"Найден заголовок с индикатором: {header.get_text()[:50]}...")
        
        # Ищем список после заголовка
        next_list = header.find_next_sibling(['ul', 'ol'])
        if next_list:
            list_items = next_list.find_all('li')
            for li in list_items:
                text = li.get_text(strip=True)
                if text and len(text) > 3:
                    items.append(text)
            if items:
                logger.info(f"Извлечено {len(items)} компонентов через заголовок + список")
                return _remove_duplicates(items)
        
        # Ищем абзац после заголовка
        next_p = header.find_next_sibling('p')
        if next_p:
            text = next_p.get_text(strip=True)
            if text and len(text) > 10:
                components = re.split(r'[;,\n]', text)
                for comp in components:
                    comp = comp.strip()
                    if comp and len(comp) > 3:
                        items.append(comp)
                if items:
                    logger.info(f"Извлечено {len(items)} компонентов через заголовок + абзац")
                    return _remove_duplicates(items)
    
    # 2. Поиск в таблицах
    if not items:
        items = _extract_from_tables(soup)
        if items:
            logger.info(f"Извлечено {len(items)} компонентов из таблиц")
            return _remove_duplicates(items)
    
    # 3. Поиск в структурированных блоках
    if not items:
        items = _extract_from_structured_blocks(soup)
        if items:
            logger.info(f"Извлечено {len(items)} компонентов из структурированных блоков")
            return _remove_duplicates(items)
    
    # 4. Фолбэк: парсинг всего текста на паттерны компонентов
    if not items:
        logger.info("Применяем фолбэк-поиск по всему тексту")
        items = _fallback_text_search(soup)
        if items:
            logger.info(f"Извлечено {len(items)} компонентов через фолбэк-поиск")
            return _remove_duplicates(items)
    
    logger.info(f"Итого извлечено {len(items)} уникальных компонентов")
    return _remove_duplicates(items)

def _extract_from_tables(soup: BeautifulSoup) -> List[str]:
    """Извлекает компоненты из таблиц"""
    items = []
    tables = soup.find_all('table')
    
    for table in tables:
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 2 and INDICATOR_RE.search(cells[0].get_text(strip=True)):
                text = cells[1].get_text(strip=True)
                components = re.split(r'[;,]', text)
                for comp in components:
                    comp = comp.strip()
                    if comp and len(comp) > 3:
                        items.append(comp)
    
    return items

def _extract_from_structured_blocks(soup: BeautifulSoup) -> List[str]:
    """Извлекает компоненты из структурированных блоков"""
    items = []
    
    # Поиск в блоках с классами, указывающими на состав
    structured_blocks = soup.find_all(['div', 'section'], 
        class_=re.compile(r'(composition|bundle|kit|set|комплект|набор|состав)', re.I))
    
    for block in structured_blocks:
        block_text = block.get_text()
        if any(indicator in block_text.lower() for indicator in ['входит', 'включает', 'состав', 'комплект']):
            # Ищем списки внутри блока
            lists = block.find_all(['ul', 'ol'])
            for ul in lists:
                for li in ul.find_all('li'):
                    text = li.get_text(strip=True)
                    if text and len(text) > 3:
                        items.append(text)
    
    return items

def _fallback_text_search(soup: BeautifulSoup) -> List[str]:
    """
    Фолбэк-поиск компонентов по всему тексту страницы
    
    Args:
        soup: BeautifulSoup объект страницы
        
    Returns:
        Список найденных компонентов
    """
    items = []
    full_text = soup.get_text()
    
    # Ищем строки с брендами/единицами типа "Воскоплав ... 100 Вт"
    candidates = COMPONENT_PAT.findall(full_text)
    
    for candidate in candidates:
        candidate = candidate.strip()
        # Фильтруем по длине и наличию брендов/ключевых слов
        if (len(candidate) > 10 and 
            any(brand.lower() in candidate.lower() for brand in BRAND_FILTERS)):
            items.append(candidate)
    
    logger.info(f"Фолбэк-поиск нашел {len(items)} кандидатов")
    return items

def _remove_duplicates(items: List[str]) -> List[str]:
    """Удаляет дубликаты, сохраняя порядок"""
    seen = set()
    unique_items = []
    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)
    return unique_items

def validate_bundle_components(components: List[str], description: str) -> bool:
    """
    Проверяет, что все компоненты присутствуют в описании
    
    Args:
        components: Список компонентов набора
        description: HTML описание товара
        
    Returns:
        True если все компоненты найдены в описании
    """
    if not components:
        return True
    
    missing_components = []
    for component in components:
        # Ищем компонент в описании (без учета регистра)
        if component.lower() not in description.lower():
            missing_components.append(component)
    
    if missing_components:
        logger.warning(f"Не найдены в описании: {missing_components}")
        return False
    
    logger.info("Все компоненты набора присутствуют в описании")
    return True

def create_fallback_bundle_text(components: List[str], locale: str) -> str:
    """
    Создает фолбэк-текст с перечислением компонентов
    
    Args:
        components: Список компонентов набора
        locale: Локаль ('ru' или 'ua')
        
    Returns:
        HTML текст с перечислением компонентов
    """
    if not components:
        return ""
    
    if locale == 'ua':
        prefix = "В набір входить: "
    else:
        prefix = "В набор входят: "
    
    components_text = ", ".join(components) + "."
    return f"<p>{prefix}{components_text}</p>"

def validate_bundle_in_description(description_html: str, bundle_components: List[str], locale: str = 'ru') -> str:
    """
    Валидация и фолбэк для гарантии присутствия всех компонентов
    
    Args:
        description_html: HTML описание товара
        bundle_components: Список компонентов набора
        locale: Локаль ('ru' или 'ua')
        
    Returns:
        HTML описание с гарантированным присутствием всех компонентов
    """
    if not bundle_components:
        return description_html
    
    # Для UA переводим компоненты для проверки
    if locale == 'ua':
        translated_components = _translate_bundle_components(bundle_components)
    else:
        translated_components = bundle_components
    
    # Проверяем присутствие каждого компонента
    missing_components = []
    for component in translated_components:
        if component.lower() not in description_html.lower():
            missing_components.append(component)
    
    # Если есть отсутствующие компоненты, добавляем фолбэк
    if missing_components:
        logger.warning(f"Добавляем фолбэк для {len(missing_components)} отсутствующих компонентов")
        if locale == 'ua':
            fallback_text = f"<p>Повний склад: {'; '.join(translated_components)}</p>"
        else:
            fallback_text = f"<p>Полный состав: {'; '.join(translated_components)}</p>"
        description_html += fallback_text
    
    return description_html

def _translate_bundle_components(components: List[str]) -> List[str]:
    """
    ✅ УНИВЕРСАЛЬНЫЙ перевод компонентов набора через LLM
    БЕЗ словарей - работает для ЛЮБЫХ товаров
    
    Args:
        components: Список компонентов на русском
        
    Returns:
        Список компонентов на украинском
    """
    if not components:
        return []
    
    # ✅ Универсальный перевод через LLM
    try:
        import httpx
        import os
        import asyncio
        
        async def translate_with_llm():
            api_key = os.getenv('OPENAI_API_KEY')
            
            # Формируем промпт для пакетного перевода
            components_text = "\n".join([f"{i+1}. {comp}" for i, comp in enumerate(components)])
            
            prompt = f"""Переведи компоненты набора на украинский язык:
{components_text}

Требования:
- Точный перевод каждого компонента
- Сохрани технические термины и единицы измерения
- Сохрани названия брендов
- БЕЗ пояснений

Формат ответа (ТОЛЬКО список):
1. [переведенный компонент 1]
2. [переведенный компонент 2]
..."""

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    response_text = result['choices'][0]['message']['content'].strip()
                    
                    # Парсим ответ
                    lines = [line.strip() for line in response_text.split('\n') if line.strip()]
                    translated = []
                    
                    for line in lines:
                        # Ищем паттерн "1. текст" или просто "текст"
                        if '. ' in line:
                            translated.append(line.split('. ', 1)[1])
                        else:
                            translated.append(line)
                    
                    if len(translated) == len(components):
                        logger.info(f"✅ LLM переведено {len(translated)} компонентов набора на украинский")
                        return translated
                
                logger.error(f"❌ LLM API ошибка: {response.status_code}")
                return components
                
        # Выполняем асинхронный перевод
        translated = asyncio.run(translate_with_llm())
        return translated
        
    except Exception as e:
        logger.error(f"❌ Ошибка LLM перевода компонентов: {e}")
        # Fallback: возвращаем оригинал
        return components
