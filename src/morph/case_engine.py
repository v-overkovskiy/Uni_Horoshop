"""
Гибридный конвейер склонения для коммерческого блока
1) Морфо-анализ (pymorphy2/pymorphy3)
2) Эвристики по окончаниям
3) Минимальный LLM-ремонт для сложных случаев
4) Кэш на токен для экономии бюджета
"""

import re
import logging
from typing import Optional, Dict, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)

# Инициализация морфологических анализаторов
morph_ru = None
morph_ua = None

try:
    import pymorphy2  # RU
    morph_ru = pymorphy2.MorphAnalyzer()
    logger.info("✅ pymorphy2 (RU) загружен")
except Exception as e:
    logger.warning(f"⚠️ pymorphy2 (RU) недоступен: {e}")

# Для украинского языка (опционально)
try:
    # Попытка загрузить украинский словарь
    from pymorphy2 import MorphAnalyzer as MorphUA
    morph_ua = MorphUA(lang='uk')
    logger.info("✅ pymorphy2 (UA) загружен")
except Exception as e:
    logger.warning(f"⚠️ pymorphy2 (UA) недоступен: {e}")

# Исключения - слова, которые не склоняются (только составные/сложные)
RU_EXCEPT = {
    'гель-крем', 'масло-лосьон', 'спрей-тоник', 'скраб-маска'
}

UA_EXCEPT = {
    'гель-крем', 'масло-лосьйон', 'спрей-тонік', 'скраб-маска'
}

# Регулярное выражение для брендов
BRANDS = re.compile(r'^(italwax|ital|wax|top\s*line|pour\s*homme|bilyi|shokolad|aloe|banan|olyva)$', re.I)

# Кэш для LLM-склонений
_llm_cache: Dict[str, str] = {}

def head_token(title: str) -> str:
    """
    Извлекает первое предметное слово из названия товара,
    игнорируя бренды, латиницу и модификаторы
    """
    # Разбиваем по небуквенным символам
    words = re.split(r'[^\w\-]+', title.strip())
    
    for w in words:
        wl = w.lower().strip()
        if not wl:
            continue
            
        # Пропускаем латиницу и цифры
        if re.search(r'[a-z0-9]', wl):
            continue
            
        # Пропускаем бренды
        if BRANDS.match(wl):
            continue
            
        # Пропускаем служебные слова
        if wl in {'в', 'для', 'у', 'на', 'с', 'из', 'от', 'до'}:
            continue
            
        return w
    
    # Если ничего не найдено, возвращаем первое слово
    return words[0] if words else title

@lru_cache(maxsize=1000)
def ru_accusative(word: str) -> str:
    """
    Склоняет слово в винительный падеж (RU)
    """
    if not word:
        return word
        
    wl = word.lower()
    
    # Проверяем исключения (только составные слова)
    if wl in RU_EXCEPT:
        return word
    
    # 1) Морфологический анализ
    if morph_ru:
        try:
            parsed = morph_ru.parse(word)
            if parsed and 'NOUN' in parsed[0].tag:
                inflected = parsed[0].inflect({'accs'})
                if inflected:
                    return inflected.word
        except Exception as e:
            logger.debug(f"Ошибка морфо-анализа RU для '{word}': {e}")
    
    # 2) Эвристики по окончаниям
    if re.search(r'сія$', wl):  # эмульсия -> эмульсию
        return re.sub(r'сія$', 'сию', word, flags=re.I)
    if re.search(r'ия$', wl):   # вода -> воду
        return re.sub(r'ия$', 'ию', word, flags=re.I)
    if re.search(r'ья$', wl):   # вода -> воду
        return re.sub(r'ья$', 'ью', word, flags=re.I)
    if re.search(r'я$', wl):    # пена -> пену
        return re.sub(r'я$', 'ю', word, flags=re.I)
    if re.search(r'а$', wl):    # вода -> воду
        return re.sub(r'а$', 'у', word, flags=re.I)
    
    # Специальные случаи для косметических товаров
    if wl == 'воск':
        return 'воск'  # В.п. = И.п. для неодушевленных мужского рода
    if wl == 'гель':
        return 'гель'  # В.п. = И.п. для неодушевленных мужского рода
    if wl == 'крем':
        return 'крем'  # В.п. = И.п. для неодушевленных мужского рода
    if wl == 'спрей':
        return 'спрей'  # В.п. = И.п. для неодушевленных мужского рода
    if wl == 'скраб':
        return 'скраб'  # В.п. = И.п. для неодушевленных мужского рода
    if wl == 'лосьон':
        return 'лосьон'  # В.п. = И.п. для неодушевленных мужского рода
    
    # Для неодушевленных существительных мужского/среднего рода В.п. = И.п.
    return word

@lru_cache(maxsize=1000)
def ua_accusative(word: str) -> str:
    """
    Склоняет слово в знахідний відмінок (UA)
    """
    if not word:
        return word
        
    wl = word.lower()
    
    # Проверяем исключения (только составные слова)
    if wl in UA_EXCEPT:
        return word
    
    # 1) Морфологический анализ
    if morph_ua:
        try:
            parsed = morph_ua.parse(word)
            if parsed and 'NOUN' in parsed[0].tag:
                inflected = parsed[0].inflect({'accs'})
                if inflected:
                    return inflected.word
        except Exception as e:
            logger.debug(f"Ошибка морфо-анализа UA для '{word}': {e}")
    
    # 2) Эвристики по окончаниям
    if re.search(r'сія$', wl):  # емульсія -> емульсію
        return re.sub(r'сія$', 'сію', word, flags=re.I)
    if re.search(r'ія$', wl):   # вода -> воду
        return re.sub(r'ія$', 'ію', word, flags=re.I)
    if re.search(r'я$', wl):    # піна -> піну
        return re.sub(r'я$', 'ю', word, flags=re.I)
    if re.search(r'а$', wl):    # вода -> воду
        return re.sub(r'а$', 'у', word, flags=re.I)
    
    # Специальные случаи для косметических товаров
    if wl == 'віск':
        return 'віск'  # Зн.в. = Наз.в. для неодушевленных мужского рода
    if wl == 'гель':
        return 'гель'  # Зн.в. = Наз.в. для неодушевленных мужского рода
    if wl == 'крем':
        return 'крем'  # Зн.в. = Наз.в. для неодушевленных мужского рода
    if wl == 'спрей':
        return 'спрей'  # Зн.в. = Наз.в. для неодушевленных мужского рода
    if wl == 'скраб':
        return 'скраб'  # Зн.в. = Наз.в. для неодушевленных мужского рода
    if wl == 'лосьйон':
        return 'лосьйон'  # Зн.в. = Наз.в. для неодушевленных мужского рода
    
    # Для неодушевленных существительных мужского/среднего рода Зн.в. = Наз.в.
    return word

def llm_accusative(word: str, locale: str) -> str:
    """
    LLM-ремонт для сложных случаев склонения
    Вызывается только когда морфо-анализ и эвристики не сработали
    """
    cache_key = f"{locale}:{word.lower()}"
    
    # Проверяем кэш
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]
    
    # Проверяем, нужен ли LLM (сложные случаи)
    if not _needs_llm(word):
        _llm_cache[cache_key] = word
        return word
    
    try:
        from src.llm.content_generator import LLMContentGenerator
        llm = LLMContentGenerator()
        
        prompt = f"Склони слово '{word}' в винительный падеж ({'русский' if locale == 'ru' else 'украинский'} язык). Ответь только одним словом без объяснений."
        
        response = llm._call_llm(prompt, max_tokens=10, temperature=0.1)
        
        if response and isinstance(response, str):
            result = response.strip()
            _llm_cache[cache_key] = result
            logger.info(f"LLM склонение: '{word}' -> '{result}' ({locale})")
            return result
            
    except Exception as e:
        logger.warning(f"Ошибка LLM склонения для '{word}': {e}")
    
    # Fallback - возвращаем исходное слово
    _llm_cache[cache_key] = word
    return word

def _needs_llm(word: str) -> bool:
    """
    Определяет, нужен ли LLM для склонения слова
    """
    wl = word.lower()
    
    # Сложные случаи, требующие LLM:
    # 1) Дефисные составные слова
    if '-' in word:
        return True
    
    # 2) Нестандартные окончания
    if re.search(r'[^а-яіїєё]я$', wl):  # нестандартные окончания на -я
        return True
    
    # 3) Иноязычные заимствования
    if re.search(r'[a-z]', wl):  # содержит латиницу
        return True
    
    # 4) Очень короткие или длинные слова
    if len(word) < 3 or len(word) > 20:
        return True
    
    return False

def decline_title_for_buy(title: str, locale: str) -> str:
    """
    Склоняет название товара для коммерческого блока "купить/купити"
    """
    if not title:
        return title
    
    # Извлекаем первое предметное слово
    head = head_token(title)
    
    if not head:
        return title
    
    # Склоняем в винительный падеж
    if locale == 'ru':
        declined = ru_accusative(head)
    else:  # ua
        declined = ua_accusative(head)
    
    # Если морфо-анализ и эвристики не сработали, пробуем LLM
    if declined == head and _needs_llm(head):
        declined = llm_accusative(head, locale)
    
    # Заменяем первое слово в названии на склоненное в нижнем регистре
    if declined != head:
        # Ищем первое вхождение слова в названии
        pattern = re.escape(head)
        # Приводим склоненное слово к нижнему регистру
        declined_lower = declined.lower()
        result = re.sub(pattern, declined_lower, title, count=1, flags=re.I)
        logger.debug(f"Склонение: '{title}' -> '{result}' ({locale})")
        return result
    
    # Если склонение не изменилось, приводим первое слово к нижнему регистру
    pattern = re.escape(head)
    declined_lower = head.lower()
    result = re.sub(pattern, declined_lower, title, count=1, flags=re.I)
    logger.debug(f"Приведение к нижнему регистру: '{title}' -> '{result}' ({locale})")
    return result

def get_cache_stats() -> Dict[str, int]:
    """
    Возвращает статистику кэша
    """
    return {
        'total_cached': len(_llm_cache),
        'ru_cached': len([k for k in _llm_cache.keys() if k.startswith('ru:')]),
        'ua_cached': len([k for k in _llm_cache.keys() if k.startswith('ua:')])
    }

def clear_cache():
    """
    Очищает кэш
    """
    global _llm_cache
    _llm_cache.clear()
    logger.info("Кэш склонений очищен")
