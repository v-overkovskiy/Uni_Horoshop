"""
Каноническая нормализация URL для RU/UA пар
"""
import re
import logging
from urllib.parse import urlparse, urlunparse, quote, unquote
from typing import Tuple, Dict

logger = logging.getLogger(__name__)

class URLCanonicalizer:
    """Каноническая нормализация URL"""
    
    def __init__(self, base_domain: str = "prorazko.com"):
        self.base_domain = base_domain
        self.scheme = "https"
    
    def to_canonical_pair(self, ua_url: str) -> Tuple[str, Dict[str, str]]:
        """Преобразование UA URL в каноническую пару (slug, {ua, ru})"""
        try:
            # Исправляем опечатки в схеме
            fixed_url = re.sub(r'ht+tps?://', 'https://', ua_url)
            
            # Парсим URL
            parsed = urlparse(fixed_url)
            
            # Нормализуем путь
            path = self._normalize_path(parsed.path)
            
            # Строим канонические URL
            ua_canonical = urlunparse((
                self.scheme,
                self.base_domain,
                path,
                '',
                '',
                ''
            ))
            
            ru_canonical = urlunparse((
                self.scheme,
                self.base_domain,
                '/ru' + path,
                '',
                '',
                ''
            ))
            
            # Канонический slug (без /ru/)
            canonical_slug = path
            
            logger.debug(f"Канонизирован URL: {ua_url} -> {canonical_slug}")
            
            return canonical_slug, {
                'ua': ua_canonical,
                'ru': ru_canonical
            }
            
        except Exception as e:
            logger.error(f"Ошибка канонизации URL {ua_url}: {e}")
            # Fallback на исходный URL
            return ua_url, {'ua': ua_url, 'ru': ua_url}
    
    def _normalize_path(self, path: str) -> str:
        """Нормализация пути URL"""
        if not path:
            return '/'
        
        # Декодируем и кодируем заново для корректной обработки кириллицы
        try:
            decoded_segments = unquote(path).split('/')
            normalized_segments = []
            
            for segment in decoded_segments:
                if segment:
                    # Кодируем каждый сегмент
                    encoded_segment = quote(segment, safe='')
                    normalized_segments.append(encoded_segment)
            
            # Собираем путь
            normalized_path = '/' + '/'.join(normalized_segments)
            
            # Убираем двойные слеши
            normalized_path = re.sub(r'/+', '/', normalized_path)
            
            return normalized_path
            
        except Exception as e:
            logger.warning(f"Ошибка нормализации пути {path}: {e}")
            return path
    
    def validate_url(self, url: str) -> bool:
        """Валидация URL"""
        try:
            # Исправляем опечатки в схеме
            fixed_url = re.sub(r'ht+tps?://', 'https://', url)
            parsed = urlparse(fixed_url)
            
            return (
                parsed.scheme in ['http', 'https'] and
                parsed.netloc and
                parsed.netloc == self.base_domain  # Проверяем домен
            )
        except Exception:
            return False
    
    def get_canonical_slug(self, url: str) -> str:
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
