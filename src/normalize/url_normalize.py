"""
Нормализация URL для пар RU/UA
"""
import re
import logging
from urllib.parse import urlparse, urlunparse, quote, unquote
from typing import Tuple, Dict

logger = logging.getLogger(__name__)

HOST = "prorazko.com"

def _fix_scheme(u: str) -> str:
    """Исправление схемы URL"""
    original = u
    u = u.strip()
    
    # Исправляем опечатки в протоколе
    u = re.sub(r'ht+t+p+s*://', 'https://', u)  # htttps://, httttps:// → https://
    u = re.sub(r'ht+t+p://', 'http://', u)      # htttp://, httttp:// → http://
    u = re.sub(r'ht+p+s*://', 'https://', u)    # htp://, htps:// → https://
    u = re.sub(r'ht+p://', 'http://', u)        # htp:// → http://
    
    # Исправляем опечатки в домене
    u = re.sub(r'prorazkko\.com', 'prorazko.com', u)  # prorazkko.com → prorazko.com
    u = re.sub(r'prorazko\.co\.', 'prorazko.com', u)  # prorazko.co. → prorazko.com
    u = re.sub(r'prorazko\.comm', 'prorazko.com', u)  # prorazko.comm → prorazko.com
    
    # Принудительно https для prorazko.com
    if u.startswith("http://") and "prorazko.com" in u:
        u = "https://" + u[len("http://"):]
    
    # Логируем исправления
    if original != u:
        logger.info(f"🔧 URL исправлен: '{original}' → '{u}'")
    
    return u

def _fix_path_issues(u: str) -> str:
    """Исправляет проблемы в пути URL БЕЗ удаления дефисов"""
    original = u
    
    # Только безопасные исправления без потери дефисов
    u = re.sub(r'dllia', 'dlia', u)  # dllia → dlia (опечатка)
    
    # Логируем исправления
    if original != u:
        logger.info(f"🔧 Путь исправлен: '{original}' → '{u}'")
    
    return u

def _norm_path(path: str) -> str:
    """Безопасная нормализация пути URL БЕЗ удаления дефисов"""
    if not path:
        return "/"
    
    # Декодируем URL
    decoded = unquote(path)
    
    # Только безопасные исправления
    decoded = decoded.replace('—', '-').replace('–', '-')  # тире → дефис
    decoded = re.sub(r'/+', '/', decoded)                   # // → /
    decoded = re.sub(r'\s*-\s*', '-', decoded)             # пробелы вокруг дефиса
    
    # ВАЖНО: НЕ удаляем дефисы! НЕ заменяем [^a-z0-9-]
    
    # Разбиваем на сегменты и кодируем безопасно
    parts = [seg for seg in decoded.split("/") if seg]
    safe = "/" + "/".join(quote(seg, safe='-._~') for seg in parts)
    
    return safe or "/"

def to_canonical_pair(ua_url: str) -> Tuple[str, Dict[str, str]]:
    """Преобразование UA URL в каноническую пару (slug, {ua, ru})"""
    try:
        ua_url = _fix_scheme(ua_url)
        ua_url = _fix_path_issues(ua_url)
        u = urlparse(ua_url)
        path = _norm_path(u.path)
        ua = urlunparse(("https", HOST, path, "", "", ""))
        ru = urlunparse(("https", HOST, "/ru" + (path if path.startswith("/") else "/" + path), "", "", ""))
        slug = path  # без /ru
        return slug, {"ua": ua, "ru": ru}
    except Exception as e:
        logger.error(f"Ошибка нормализации URL {ua_url}: {e}")
        return ua_url, {"ua": ua_url, "ru": ua_url}

def validate_url(url: str) -> bool:
    """Валидация URL"""
    try:
        fixed_url = _fix_scheme(url)
        parsed = urlparse(fixed_url)
        return (
            parsed.scheme in ['http', 'https'] and
            parsed.netloc == HOST
        )
    except Exception:
        return False

def get_canonical_slug(url: str) -> str:
    """Получение канонического slug из URL"""
    try:
        parsed = urlparse(url)
        path = parsed.path
        
        # Убираем /ru/ если есть
        if path.startswith('/ru/'):
            path = path[4:]  # Убираем '/ru/'
        
        return path or '/'
    except Exception:
        return url
