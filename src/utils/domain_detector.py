"""
Универсальный детектор домена для работы с любыми интернет-магазинами
"""
import re
import logging
from urllib.parse import urlparse
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

class UniversalDomainDetector:
    """Определяет и работает с доменом из любого URL"""
    
    @staticmethod
    def extract_domain(url: str) -> Tuple[str, str, str]:
        """
        Извлекает полный домен, схему и хост из URL
        
        Returns:
            Tuple[scheme, host, full_domain]
            Например: ('https', 'newday.ua', 'https://newday.ua')
        """
        try:
            # Нормализуем URL
            url = url.strip()
            
            # Исправляем опечатки в протоколе
            url = re.sub(r'h+t+t+p+s*://', 'https://', url, flags=re.IGNORECASE)
            url = re.sub(r'h+t+p://', 'http://', url, flags=re.IGNORECASE)
            
            # Парсим URL
            parsed = urlparse(url)
            
            # Получаем схему и хост
            scheme = parsed.scheme or 'https'
            host = parsed.netloc
            
            if not host:
                # Если не распарсился, пытаемся извлечь вручную
                match = re.match(r'(https?://)?([^/]+)', url)
                if match:
                    host = match.group(2)
            
            # Формируем полный домен
            full_domain = f"{scheme}://{host}"
            
            logger.debug(f"Извлечен домен: {full_domain} из URL: {url}")
            
            return (scheme, host, full_domain)
            
        except Exception as e:
            logger.error(f"Ошибка извлечения домена из {url}: {e}")
            # Fallback - возвращаем безопасные значения
            return ('https', '', 'https://')
    
    @staticmethod
    def is_same_domain(url1: str, url2: str) -> bool:
        """Проверяет, принадлежат ли два URL одному домену"""
        _, host1, _ = UniversalDomainDetector.extract_domain(url1)
        _, host2, _ = UniversalDomainDetector.extract_domain(url2)
        return host1 == host2
    
    @staticmethod
    def make_absolute_url(relative_url: str, base_url: str) -> str:
        """
        Преобразует относительный URL в абсолютный на основе базового URL
        
        Args:
            relative_url: относительный или абсолютный URL
            base_url: базовый URL для определения домена
            
        Returns:
            Абсолютный URL
        """
        # Если уже абсолютный - возвращаем как есть
        if relative_url.startswith('http://') or relative_url.startswith('https://'):
            return relative_url
        
        # Извлекаем домен из базового URL
        _, _, full_domain = UniversalDomainDetector.extract_domain(base_url)
        
        # Проверка на пустой домен
        if not full_domain or full_domain == 'https://':
            logger.warning(f"⚠️ Не удалось извлечь домен из {base_url}, используем относительный URL как есть")
            return relative_url
        
        # Формируем абсолютный URL
        if relative_url.startswith('/'):
            result = f"{full_domain}{relative_url}"
        else:
            result = f"{full_domain}/{relative_url.lstrip('/')}"
        
        # Нормализуем двойные слэши (кроме протокола)
        result = re.sub(r'(?<!:)//+', '/', result)
        
        return result
    
    @staticmethod
    def get_locale_pair(base_url: str, locale_marker: str = '/ru/') -> Tuple[str, str]:
        """
        Генерирует пару URL для разных локалей
        
        Args:
            base_url: базовый URL
            locale_marker: маркер локали (по умолчанию /ru/)
            
        Returns:
            Tuple[ua_url, ru_url]
        """
        try:
            if locale_marker in base_url:
                # Если есть маркер локали - удаляем для UA версии
                ua_url = base_url.replace(locale_marker, '/')
                ru_url = base_url
            else:
                # Добавляем маркер для RU версии
                ua_url = base_url
                parsed = urlparse(base_url)
                ru_url = f"{parsed.scheme}://{parsed.netloc}{locale_marker.rstrip('/')}{parsed.path}"
            
            # Нормализуем двойные слэши
            ru_url = re.sub(r'(?<!:)//+', '/', ru_url)
            ua_url = re.sub(r'(?<!:)//+', '/', ua_url)
            
            return (ua_url, ru_url)
            
        except Exception as e:
            logger.error(f"Ошибка генерации пары локалей: {e}")
            return (base_url, base_url)
    
    @staticmethod
    def normalize_url(url: str, force_https: bool = True) -> str:
        """
        Нормализует URL (исправляет опечатки, форматирование)
        
        Args:
            url: URL для нормализации
            force_https: принудительно использовать HTTPS
            
        Returns:
            Нормализованный URL
        """
        url = url.strip()
        
        # Исправляем опечатки в протоколе
        url = re.sub(r'h+t+t+p+s*://', 'https://', url, flags=re.IGNORECASE)
        url = re.sub(r'h+t+p://', 'http://', url, flags=re.IGNORECASE)
        
        # Принудительно HTTPS если запрошено
        if force_https and url.startswith('http://'):
            url = 'https://' + url[7:]
        
        # Убираем двойные слэши в пути (но не в протоколе)
        url = re.sub(r'(?<!:)//+', '/', url)
        
        # Убираем trailing slash
        if url.endswith('/') and url.count('/') > 3:
            url = url.rstrip('/')
        
        return url

