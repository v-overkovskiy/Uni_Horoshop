"""
Умный загрузчик с retry и fallback логикой для гарантированной обработки
"""
import asyncio
import httpx
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class ResilientFetcher:
    """Умный загрузчик с retry и fallback"""
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
    
    async def fetch_with_retry(
        self, 
        url: str, 
        max_retries: Optional[int] = None
    ) -> Optional[str]:
        """Загрузка с повторными попытками и экспоненциальным backoff"""
        
        if max_retries is None:
            max_retries = self.max_retries
            
        for attempt in range(max_retries):
            try:
                logger.info(f"🌐 Попытка {attempt+1}/{max_retries}: {url}")
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    logger.info(f"✅ Успешно загружено: {url}")
                    return response.text
                    
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
                logger.warning(f"⚠️ Попытка {attempt+1}/{max_retries} не удалась: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Экспоненциальный backoff: 1s, 2s, 4s
                    logger.info(f"⏳ Ожидание {wait_time}с перед повтором")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Все попытки исчерпаны для {url}")
                    raise Exception(f"Не удалось загрузить {url} после {max_retries} попыток: {e}")
        
        return None
    
    async def fetch_with_fallback_locale(
        self, 
        primary_url: str, 
        fallback_url: str
    ) -> Tuple[str, str]:
        """Попытка загрузки с альтернативной локали"""
        
        try:
            logger.info(f"🎯 Пробуем primary URL: {primary_url}")
            content = await self.fetch_with_retry(primary_url)
            return content, 'primary'
            
        except Exception as e:
            logger.warning(f"⚠️ Primary URL failed: {e}")
            logger.info(f"🔄 Пробуем fallback URL: {fallback_url}")
            
            try:
                content = await self.fetch_with_retry(fallback_url)
                logger.info(f"✅ Fallback успешен: {fallback_url}")
                return content, 'fallback'
            except Exception as fallback_error:
                logger.error(f"❌ И primary, и fallback URL не работают:")
                logger.error(f"   Primary: {e}")
                logger.error(f"   Fallback: {fallback_error}")
                raise Exception(f"Оба URL недоступны: primary={e}, fallback={fallback_error}")
    
    async def fetch_product_with_locales(
        self, 
        base_url: str
    ) -> Tuple[str, str, str]:
        """Загрузка товара для обеих локалей с fallback"""
        
        # Определяем URLs для обеих локалей
        if '/ru/' in base_url:
            ru_url = base_url
            ua_url = base_url.replace('/ru/', '/')
        else:
            ua_url = base_url
            ru_url = base_url.replace('prorazko.com/', 'prorazko.com/ru/')
        
        logger.info(f"🔄 Загружаем товар для обеих локалей:")
        logger.info(f"   RU: {ru_url}")
        logger.info(f"   UA: {ua_url}")
        
        # Загружаем UA версию
        try:
            ua_content = await self.fetch_with_retry(ua_url)
            logger.info(f"✅ UA версия загружена успешно")
        except Exception as e:
            logger.error(f"❌ UA версия недоступна: {e}")
            ua_content = None
        
        # Загружаем RU версию
        try:
            ru_content = await self.fetch_with_retry(ru_url)
            logger.info(f"✅ RU версия загружена успешно")
        except Exception as e:
            logger.error(f"❌ RU версия недоступна: {e}")
            ru_content = None
        
        # Если одна из версий недоступна, возвращаем то что есть
        if ua_content and ru_content:
            logger.info(f"✅ Обе локали загружены успешно")
            return ua_content, ru_content, 'both'
        elif ua_content:
            logger.warning(f"⚠️ Только UA версия доступна")
            return ua_content, None, 'ua_only'
        elif ru_content:
            logger.warning(f"⚠️ Только RU версия доступна")
            return None, ru_content, 'ru_only'
        else:
            raise Exception(f"Ни одна из локалей недоступна: UA={ua_url}, RU={ru_url}")
    
    def get_fallback_urls(self, url: str) -> Tuple[str, str]:
        """Получает fallback URLs для разных локалей"""
        if '/ru/' in url:
            ru_url = url
            ua_url = url.replace('/ru/', '/')
        else:
            ua_url = url
            ru_url = url.replace('prorazko.com/', 'prorazko.com/ru/')
        
        return ua_url, ru_url
