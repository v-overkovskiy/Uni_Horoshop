"""
Fetcher с fallback на исходный URL при 404
"""
import asyncio
import logging
from typing import Optional
import httpx
from src.normalize.url_normalize import _fix_scheme, _fix_path_issues

logger = logging.getLogger(__name__)

class FallbackFetcher:
    """HTTP клиент с fallback на исходный URL"""
    
    def __init__(self, timeout: int = 15, retries: int = 2):
        self.timeout = timeout
        self.retries = retries
        self.session = None
    
    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.aclose()
    
    async def fetch_with_fallback(self, raw_url: str, locale: str = 'ru') -> Optional[str]:
        """Загружает URL с fallback на исходный при 4xx/тайм-ауте"""
        # Нормализуем URL
        normalized_url = self._normalize_url(raw_url)
        
        # Логируем нормализацию
        if normalized_url != raw_url:
            logger.info(f"🔧 URL нормализован: '{raw_url}' → '{normalized_url}'")
        
        # Проверяем количество дефисов (защита от регрессии)
        original_dashes = raw_url.count('-')
        normalized_dashes = normalized_url.count('-')
        
        if normalized_dashes < original_dashes:
            logger.warning(f"⚠️ Нормализация удалила дефисы! Исходный: {original_dashes}, нормализованный: {normalized_dashes}")
            logger.warning(f"   Исходный: {raw_url}")
            logger.warning(f"   Нормализованный: {normalized_url}")
        
        # Пробуем оба URL (нормализованный, затем raw)
        urls_to_try = [normalized_url, raw_url]
        
        last_exception = None
        
        for attempt, url in enumerate(urls_to_try):
            try:
                logger.info(f"🔄 Попытка {attempt + 1}: {url}")
                
                # Устанавливаем заголовки в зависимости от локали
                headers = self._get_locale_headers(locale)
                
                response = await self.session.get(url, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"✅ Успешно загружено: {url} (locale: {locale})")
                    return response.text
                else:
                    logger.warning(f"⚠️ HTTP {response.status_code} для {url}")
                    # Продолжаем к следующему URL при 4xx/5xx
                    
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки {url}: {e}")
                last_exception = e
                # Продолжаем к следующему URL при тайм-ауте/сетевых ошибках
        
        # Если дошли сюда, все URL не сработали
        if last_exception:
            logger.error(f"❌ Все URL не сработали. Последняя ошибка: {last_exception}")
        else:
            logger.error(f"❌ Все URL вернули не-200 статус")
        
        return None
    
    def _get_locale_headers(self, locale: str) -> dict:
        """Возвращает заголовки HTTP в зависимости от локали"""
        if locale == 'ua':
            return {
                'Accept-Language': 'uk,ru;q=0.3',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        else:  # ru
            return {
                'Accept-Language': 'ru,uk;q=0.3',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
    
    def _normalize_url(self, url: str) -> str:
        """Безопасная нормализация URL с жёсткой схемой"""
        # Жёсткая нормализация схемы
        url = self._normalize_scheme_strict(url)
        
        # Исправляем проблемы в пути (БЕЗ удаления дефисов)
        url = _fix_path_issues(url)
        
        return url
    
    def _normalize_scheme_strict(self, url: str) -> str:
        """Жёсткая нормализация схемы - исправляет htttps и любые варианты"""
        import re
        original = url
        url = url.strip()
        
        # Исправляем все варианты htttps
        url = re.sub(r'^h+t+t+tps?://', 'https://', url, flags=re.I)
        
        # Принудительно https для prorazko.com
        if url.startswith("http://") and "prorazko.com" in url:
            url = "https://" + url[len("http://"):]
        
        if original != url:
            logger.info(f"🔧 URL схема исправлена: '{original}' → '{url}'")
        
        return url
    
    async def fetch_single(self, url: str, locale: str = 'ru') -> Optional[str]:
        """Загружает один URL с fallback"""
        return await self.fetch_with_fallback(url, locale)

