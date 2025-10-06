"""
Нормализация URL с percent-encoding для кириллицы
"""
import re
import logging
from urllib.parse import urljoin, urlparse, urlunparse, quote, unquote
from typing import Optional

logger = logging.getLogger(__name__)

class URLNormalizer:
    """Нормализация URL с поддержкой кириллицы"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def normalize(self, url: str) -> str:
        """Нормализация URL с percent-encoding"""
        if not url:
            return url
        
        try:
            # Если URL относительный, делаем абсолютным
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = urljoin(self.base_url, url)
            elif not url.startswith(('http://', 'https://')):
                url = urljoin(self.base_url, url)
            
            # Парсим URL
            parsed = urlparse(url)
            
            # Нормализуем путь с percent-encoding для кириллицы
            normalized_path = self._normalize_path(parsed.path)
            
            # Собираем URL обратно
            normalized_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                normalized_path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            return normalized_url
            
        except Exception as e:
            logger.error(f"Ошибка нормализации URL {url}: {e}")
            return url
    
    def _normalize_path(self, path: str) -> str:
        """Нормализация пути с percent-encoding"""
        if not path:
            return path
        
        # Разбиваем путь на сегменты
        segments = path.split('/')
        normalized_segments = []
        
        for segment in segments:
            if segment:
                # Декодируем и кодируем заново для корректной обработки кириллицы
                decoded = unquote(segment)
                encoded = quote(decoded, safe='')
                normalized_segments.append(encoded)
            else:
                normalized_segments.append(segment)
        
        return '/'.join(normalized_segments)
    
    def is_valid_url(self, url: str) -> bool:
        """Проверка валидности URL"""
        if not url:
            return False
        
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def get_domain(self, url: str) -> Optional[str]:
        """Извлечение домена из URL"""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None


