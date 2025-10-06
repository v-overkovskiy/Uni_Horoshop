"""
Модуль для мониторинга прогресса обработки в реальном времени
"""
import asyncio
import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ProductStatus:
    """Статус обработки одного товара"""
    url: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[str] = None
    progress: Dict[str, str] = None  # {'ru': 'completed', 'ua': 'processing'}
    
    def __post_init__(self):
        if self.progress is None:
            self.progress = {'ru': 'pending', 'ua': 'pending'}

class ProgressMonitor:
    """Мониторинг прогресса обработки"""
    
    def __init__(self, total_products: int):
        self.total_products = total_products
        self.products: Dict[str, ProductStatus] = {}
        self.start_time = time.time()
        self.completed_count = 0
        self.failed_count = 0
        self.monitor_task: Optional[asyncio.Task] = None
        
    def add_product(self, url: str):
        """Добавить товар для мониторинга"""
        self.products[url] = ProductStatus(url=url, status='pending')
        
    def start_processing(self, url: str):
        """Начать обработку товара"""
        if url in self.products:
            self.products[url].status = 'processing'
            self.products[url].start_time = time.time()
            logger.info(f"🔄 Начинаем обработку: {url}")
            
    def update_locale_progress(self, url: str, locale: str, status: str):
        """Обновить прогресс для конкретной локали"""
        if url in self.products:
            self.products[url].progress[locale] = status
            logger.info(f"📊 {locale.upper()} для {url}: {status}")
            
    def update_progress(self, count: int = 1):
        """Обновить счетчик завершенных товаров"""
        self.completed_count += count
        logger.debug(f"📊 Прогресс обновлен: +{count} товаров")
        
    def complete_product(self, url: str, success: bool = True, error: str = None):
        """Завершить обработку товара"""
        if url in self.products:
            self.products[url].status = 'completed' if success else 'failed'
            self.products[url].end_time = time.time()
            if error:
                self.products[url].error = error
                
            if success:
                self.completed_count += 1
                logger.info(f"✅ Завершено: {url}")
            else:
                self.failed_count += 1
                logger.error(f"❌ Ошибка: {url} - {error}")
                
    def get_progress_summary(self) -> Dict:
        """Получить сводку прогресса"""
        processing_count = sum(1 for p in self.products.values() if p.status == 'processing')
        pending_count = sum(1 for p in self.products.values() if p.status == 'pending')
        
        elapsed_time = time.time() - self.start_time
        
        return {
            'total': self.total_products,
            'completed': self.completed_count,
            'failed': self.failed_count,
            'processing': processing_count,
            'pending': pending_count,
            'elapsed_time': elapsed_time,
            'success_rate': (self.completed_count / max(1, self.completed_count + self.failed_count)) * 100
        }
        
    def start_monitoring(self, interval: float = 10.0):
        """Запустить мониторинг в фоне"""
        self.monitor_task = asyncio.create_task(self._monitor_loop(interval))
        
    async def _monitor_loop(self, interval: float):
        """Цикл мониторинга"""
        while True:
            try:
                await asyncio.sleep(interval)
                summary = self.get_progress_summary()
                
                logger.info(f"📊 ПРОГРЕСС: {summary['completed']}/{summary['total']} завершено, "
                          f"{summary['processing']} обрабатывается, "
                          f"{summary['failed']} ошибок, "
                          f"успешность: {summary['success_rate']:.1f}%")
                
                # Показываем детали по обрабатываемым товарам
                processing_products = [p for p in self.products.values() if p.status == 'processing']
                for product in processing_products:
                    ru_status = product.progress.get('ru', 'pending')
                    ua_status = product.progress.get('ua', 'pending')
                    logger.info(f"  🔄 {product.url}: RU={ru_status}, UA={ua_status}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка мониторинга: {e}")
                
    async def stop_monitoring(self):
        """Остановить мониторинг"""
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
                
    def get_final_report(self) -> Dict:
        """Получить финальный отчет"""
        summary = self.get_progress_summary()
        
        # Детали по каждому товару
        product_details = []
        for product in self.products.values():
            processing_time = 0
            if product.start_time and product.end_time:
                processing_time = product.end_time - product.start_time
            elif product.start_time:
                processing_time = time.time() - product.start_time
                
            product_details.append({
                'url': product.url,
                'status': product.status,
                'processing_time': processing_time,
                'ru_status': product.progress.get('ru', 'pending'),
                'ua_status': product.progress.get('ua', 'pending'),
                'error': product.error
            })
            
        return {
            'summary': summary,
            'products': product_details
        }
