"""
Экстрактор характеристик товара с fallback по заголовку и JSON-LD резервом
"""
import json
import re
import logging
from typing import List, Dict, Tuple, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Регулярные выражения для поиска заголовков характеристик
RU_HEAD = re.compile(r'характеристик', re.I)
UA_HEAD = re.compile(r'характеристик', re.I)

# Селекторы для различных типов контейнеров характеристик
LIST_SELECTORS = [
    ".product-features",
    ".product-characteristics", 
    ".product__features",
    ".product-features__list",
    ".characteristics",
    ".features-list",
    ".product-attributes",
    ".attributes-list",
    ".ds-desc .specs",
    ".specs"
]

TABLE_SELECTORS = [
    "table.product-features-table",
    ".product-features table",
    ".characteristics table",
    ".product-attributes table"
]

DL_SELECTORS = [
    ".characteristics dl",
    ".features dl",
    ".product-attributes dl"
]

# Словари нормализации ключей по локалям
RU_KEYS = {
    'бренд': 'Бренд',
    'тип': 'Тип', 
    'материал': 'Материал',
    'объем': 'Объем',
    'объём': 'Объем',
    'мощность': 'Мощность',
    'цвет': 'Цвет',
    'размер': 'Размер',
    'вес': 'Вес',
    'напряжение': 'Напряжение',
    'частота': 'Частота',
    'время нагрева': 'Время нагрева',
    'температура': 'Температура',
    'диаметр': 'Диаметр',
    'высота': 'Высота',
    'ширина': 'Ширина',
    'длина': 'Длина',
    'модель': 'Модель',
    'производитель': 'Производитель',
    'страна': 'Страна'
}

UA_KEYS = {
    'бренд': 'бренд',
    'тип': 'тип',
    'матеріал': 'матеріал', 
    'об\'єм': 'об\'єм',
    'объем': 'об\'єм',
    'потужність': 'потужність',
    'колір': 'колір',
    'розмір': 'розмір',
    'вага': 'вага',
    'напруга': 'напруга',
    'частота': 'частота',
    'час нагріву': 'час нагріву',
    'температура': 'температура',
    'діаметр': 'діаметр',
    'висота': 'висота',
    'ширина': 'ширина',
    'довжина': 'довжина',
    'модель': 'модель',
    'виробник': 'виробник',
    'країна': 'країна'
}

def _normalize_text(text: str) -> str:
    """Нормализация текста"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.strip())

def _extract_pairs_from_list(container) -> List[Tuple[str, str]]:
    """Извлечение пар name/value из списка ul/li"""
    pairs = []
    
    for li in container.select("li"):
        # Ищем ключ в span, .key, .name, strong
        name_elem = li.select_one("span, .key, .name, strong")
        if name_elem:
            name = _normalize_text(name_elem.get_text())
            # Остальной текст - значение
            name_elem.decompose()
            value = _normalize_text(li.get_text())
        else:
            # Если нет отдельного элемента для ключа, разбираем по двоеточию
            text = _normalize_text(li.get_text())
            if ':' in text:
                parts = text.split(':', 1)
                name = parts[0].strip()
                value = parts[1].strip()
            else:
                # Берем весь текст как значение
                name = ""
                value = text
        
        if name or value:
            pairs.append((name, value))
    
    return pairs

def _extract_pairs_from_table(container) -> List[Tuple[str, str]]:
    """Извлечение пар name/value из таблицы"""
    pairs = []
    
    for tr in container.select("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) >= 2:
            name = _normalize_text(cells[0].get_text())
            value = _normalize_text(cells[1].get_text())
            if name or value:
                pairs.append((name, value))
    
    return pairs

def _extract_pairs_from_dl(container) -> List[Tuple[str, str]]:
    """Извлечение пар name/value из описательного списка dl/dt/dd"""
    pairs = []
    
    for dl in container.select("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        
        for dt, dd in zip(dts, dds):
            name = _normalize_text(dt.get_text())
            value = _normalize_text(dd.get_text())
            if name or value:
                pairs.append((name, value))
    
    return pairs

def _extract_pairs_from_container(container) -> List[Tuple[str, str]]:
    """Извлечение пар name/value из контейнера (универсальный метод)"""
    pairs = []
    
    # Пробуем разные методы извлечения
    pairs.extend(_extract_pairs_from_list(container))
    pairs.extend(_extract_pairs_from_table(container))
    pairs.extend(_extract_pairs_from_dl(container))
    
    return pairs

def _find_specs_by_header(doc: BeautifulSoup, locale: str) -> List[Tuple[str, str]]:
    """Поиск характеристик по заголовку"""
    header_pattern = RU_HEAD if locale == 'ru' else UA_HEAD
    
    for header in doc.select("h1, h2, h3, h4, h5, h6"):
        text = _normalize_text(header.get_text())
        if header_pattern.search(text):
            logger.debug(f"Найден заголовок характеристик: {text}")
            
            # Ищем следующий контейнер после заголовка
            next_container = header.find_next(lambda x: x.name in ["ul", "table", "dl", "div"])
            if next_container:
                pairs = _extract_pairs_from_container(next_container)
                if pairs:
                    logger.debug(f"Извлечено {len(pairs)} характеристик по заголовку")
                    return pairs
    
    return []

def _extract_specs_from_jsonld(doc: BeautifulSoup) -> List[Tuple[str, str]]:
    """Извлечение характеристик из JSON-LD Product.additionalProperty"""
    pairs = []
    
    for script in doc.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, AttributeError):
            continue
        
        # Обрабатываем как массив или одиночный объект
        items = data if isinstance(data, list) else [data]
        
        for item in items:
            if item.get("@type") == "Product":
                additional_props = item.get("additionalProperty", [])
                for prop in additional_props:
                    if isinstance(prop, dict):
                        name = _normalize_text(prop.get("name", ""))
                        value = _normalize_text(prop.get("value", ""))
                        if name or value:
                            pairs.append((name, value))
    
    if pairs:
        logger.debug(f"Извлечено {len(pairs)} характеристик из JSON-LD")
    
    return pairs

def _normalize_key(key: str, locale: str) -> str:
    """Нормализация ключа по локали"""
    if not key:
        return ""
    
    key_lower = key.lower().strip()
    key_dict = RU_KEYS if locale == 'ru' else UA_KEYS
    
    # Ищем точное совпадение
    if key_lower in key_dict:
        return key_dict[key_lower]
    
    # Ищем частичное совпадение
    for dict_key, dict_value in key_dict.items():
        if dict_key in key_lower or key_lower in dict_key:
            return dict_value
    
    # Возвращаем оригинал с заглавной буквы
    return key.capitalize()

def _filter_valid_pairs(pairs: List[Tuple[str, str]], locale: str) -> List[Tuple[str, str]]:
    """Фильтрация валидных пар характеристик"""
    valid_pairs = []
    seen_keys = set()
    
    # Запрещенные значения
    forbidden_values = ['не указан', 'не вказано', 'не указано', 'не вказан', 'н/д', 'н/а', '']
    
    for name, value in pairs:
        # Пропускаем пустые или запрещенные значения
        if not value or value.lower() in forbidden_values:
            continue
        
        # Нормализуем ключ
        normalized_name = _normalize_key(name, locale)
        if not normalized_name:
            continue
        
        # Проверяем на дубликаты
        if normalized_name.lower() in seen_keys:
            continue
        
        seen_keys.add(normalized_name.lower())
        valid_pairs.append((normalized_name, value))
    
    return valid_pairs

def strict_filter_fake_characteristics(specs: List[Dict[str, str]], source_facts: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    """
    Жёстко фильтрует specs: оставляет ТОЛЬКО те, что совпадают по ключу и значению с исходником.
    Удаляет все заглушки, выдумки и несовпадения.
    
    Args:
        specs: Список характеристик в формате [{"name": "Тип", "value": "Воскоплав"}]
        source_facts: Исходные факты из HTML в формате [("Тип", "Воскоплав"), ...]
    
    Returns:
        Отфильтрованный список характеристик
    """
    if not source_facts:
        logger.warning("Нет исходных фактов для фильтрации - возвращаем пустой список")
        return []
    
    # Создаем множество для быстрого поиска (нормализованные ключи и значения)
    valid_pairs = set()
    for key, value in source_facts:
        normalized_key = key.strip().lower()
        normalized_value = value.strip().lower()
        valid_pairs.add((normalized_key, normalized_value))
    
    filtered_specs = []
    removed_count = 0
    
    for spec in specs:
        spec_key = spec.get("name", "").strip().lower()
        spec_value = spec.get("value", "").strip().lower()
        
        if (spec_key, spec_value) in valid_pairs:
            filtered_specs.append(spec)
        else:
            removed_count += 1
            logger.warning(f"Удаляем выдуманную характеристику: {spec.get('name', '')}: {spec.get('value', '')}")
    
    if removed_count > 0:
        logger.info(f"Строгий фильтр удалил {removed_count} выдуманных характеристик")
    
    return filtered_specs

def extract_specs(html: str, locale: str = 'ru') -> List[Dict[str, str]]:
    """
    Извлечение характеристик товара с fallback по заголовку и JSON-LD резервом
    
    Args:
        html: HTML страницы
        locale: Локаль ('ru' или 'ua')
    
    Returns:
        Список словарей с характеристиками [{"name": "Тип", "value": "Воскоплав"}]
    """
    if not html:
        return []
    
    doc = BeautifulSoup(html, "html.parser")
    all_pairs = []
    
    # 1. Прямые селекторы контейнеров
    for selector in LIST_SELECTORS + TABLE_SELECTORS + DL_SELECTORS:
        containers = doc.select(selector)
        for container in containers:
            pairs = _extract_pairs_from_container(container)
            if pairs:
                logger.debug(f"Найдены характеристики через селектор {selector}: {len(pairs)} пар")
                all_pairs.extend(pairs)
                break
        if all_pairs:
            break
    
    # 2. Fallback по заголовку
    if not all_pairs:
        all_pairs = _find_specs_by_header(doc, locale)
    
    # 3. JSON-LD резерв
    if not all_pairs:
        all_pairs = _extract_specs_from_jsonld(doc)
    
    # 4. Фильтрация и нормализация
    valid_pairs = _filter_valid_pairs(all_pairs, locale)
    
    # 5. Строгий фильтр против выдуманных характеристик
    source_facts = [(name, value) for name, value in valid_pairs]
    specs = []
    for name, value in valid_pairs:
        specs.append({"name": name, "value": value})
    
    # Применяем строгий фильтр
    filtered_specs = strict_filter_fake_characteristics(specs, source_facts)
    
    logger.info(f"Извлечено {len(filtered_specs)} валидных характеристик для {locale}")
    return filtered_specs


