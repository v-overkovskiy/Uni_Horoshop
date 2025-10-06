"""
Асинхронный HTTP клиент для конкурентной загрузки RU/UA страниц
"""
import asyncio
import aiohttp
import logging
from typing import List, Dict, Tuple, Optional
from urllib.parse import urljoin, urlparse
import time

logger = logging.getLogger(__name__)

class AsyncFetcher:
    """Асинхронный HTTP клиент с контролем RPS и ретраями"""
    
    def __init__(self, 
                 concurrency: int = 6,
                 rps_limit: int = 3,
                 timeout: int = 10,  # Жесткий таймаут
                 retries: int = 2,   # Меньше попыток
                 backoff_factor: float = 1.0):
        self.concurrency = concurrency
        self.rps_limit = rps_limit
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        
        # Семафор для контроля конкурентности
        self.semaphore = asyncio.Semaphore(concurrency)
        
        # RPS контроллер
        self.rps_controller = asyncio.Semaphore(rps_limit)
        self.last_request_time = 0
        
        # Настройки сессии с улучшенными параметрами
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        # Улучшенные настройки HTTP клиента
        self.timeout = aiohttp.ClientTimeout(total=60.0, connect=15.0, sock_read=45.0)
        # Настройки для aiohttp (limits настраиваются через connector)
        self.connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    
    async def _rate_limit(self):
        """Контроль RPS"""
        async with self.rps_controller:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            min_interval = 1.0 / self.rps_limit
            
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)
            
            self.last_request_time = time.time()
    
    async def _fetch_with_retry(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """Загрузка с ретраями и экспоненциальным бэк-оффом"""
        for attempt in range(self.retries + 1):
            try:
                await self._rate_limit()
                
                # Улучшенные таймауты с большими значениями
                timeout = aiohttp.ClientTimeout(
                    total=60.0,  # Общий таймаут
                    connect=15.0,  # Таймаут подключения
                    sock_read=45.0,  # Таймаут чтения
                    sock_connect=15.0  # Таймаут подключения сокета
                )
                
                # Дополнительные заголовки для обхода блокировок
                enhanced_headers = self.headers.copy()
                enhanced_headers.update({
                    'Referer': 'https://prorazko.com/',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin'
                })
                
                async with session.get(url, headers=enhanced_headers, timeout=timeout) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Успешно загружено: {url}")
                        return content
                    elif response.status == 429:
                        # Rate limit - увеличиваем задержку
                        delay = self.backoff_factor ** attempt
                        logger.warning(f"⚠️ Rate limit для {url}, задержка {delay}s")
                        await asyncio.sleep(delay)
                    elif response.status >= 500:
                        # Server error - ретрай с большей задержкой
                        delay = 2.0 * (self.backoff_factor ** attempt)
                        logger.warning(f"⚠️ Server error {response.status} для {url}, ретрай {attempt + 1}/{self.retries + 1}, задержка {delay:.1f}s")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"❌ HTTP {response.status} для {url}")
                        return None
                        
            except asyncio.TimeoutError:
                # Увеличенные задержки: 1.0 → 2.0 → 4.0 сек
                delay = 1.0 * (self.backoff_factor ** attempt)
                logger.warning(f"⚠️ Timeout для {url}, ретрай {attempt + 1}/{self.retries + 1}, задержка {delay:.1f}s")
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки {url}: {e}")
                return None
        
        logger.error(f"❌ Не удалось загрузить {url} после {self.retries + 1} попыток")
        return None
    
    async def fetch_single(self, url: str) -> Optional[str]:
        """Загрузка одной страницы"""
        async with self.semaphore:
            async with aiohttp.ClientSession(connector=self.connector, timeout=self.timeout) as session:
                return await self._fetch_with_retry(session, url)
    
    async def fetch_pair(self, ua_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Загрузка пары RU/UA страниц"""
        ru_url = self._to_ru_url(ua_url)
        
        async with self.semaphore:
            async with aiohttp.ClientSession() as session:
                # Запускаем загрузку обеих страниц параллельно
                ua_task = asyncio.create_task(self._fetch_with_retry(session, ua_url))
                ru_task = asyncio.create_task(self._fetch_with_retry(session, ru_url))
                
                ua_html, ru_html = await asyncio.gather(ua_task, ru_task)
                
                return ua_html, ru_html
    
    async def fetch_batch(self, urls: List[str]) -> List[Tuple[Optional[str], Optional[str]]]:
        """Загрузка батча URL пар"""
        tasks = [self.fetch_pair(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка обработки {urls[i]}: {result}")
                processed_results.append((None, None))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def _to_ru_url(self, ua_url: str) -> str:
        """Преобразование UA URL в RU URL"""
        parsed = urlparse(ua_url)
        path = parsed.path
        
        # Добавляем /ru/ префикс к пути
        if path.startswith('/'):
            ru_path = '/ru' + path
        else:
            ru_path = '/ru/' + path
        
        # Собираем URL обратно
        ru_url = f"{parsed.scheme}://{parsed.netloc}{ru_path}"
        if parsed.query:
            ru_url += f"?{parsed.query}"
        if parsed.fragment:
            ru_url += f"#{parsed.fragment}"
        
        return ru_url
    
    def get_stats(self) -> Dict[str, int]:
        """Получение статистики загрузки"""
        return {
            'concurrency': self.concurrency,
            'rps_limit': self.rps_limit,
            'timeout': self.timeout,
            'retries': self.retries
        }
