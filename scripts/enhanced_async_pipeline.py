"""
Улучшенный асинхронный пайплайн с качественными FAQ и JSON-LD
"""
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Добавляем путь к src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.async_product_processor import AsyncProductProcessor
from src.export.async_exporter import AsyncExporter
from src.monitoring.progress_monitor import ProgressMonitor
from src.processing.json_ld_generator import JsonLdGenerator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ЭКСПЕРИМЕНТАЛЬНАЯ конфигурация для максимальной производительности
CONCURRENT_PRODUCTS = 8   # Агрессивный параллелизм
LLM_CONCURRENCY = 16      # Максимальное количество LLM запросов
TIMEOUT = 45             # Увеличено для качественной генерации
MAX_RETRIES = 2          # Количество попыток при ошибках

class EnhancedAsyncPipeline:
    """Улучшенный асинхронный пайплайн с качественными FAQ"""
    
    def __init__(self):
        self.processor = AsyncProductProcessor()
        self.exporter = AsyncExporter()
        self.monitor = None  # Будет инициализирован позже
        self.json_ld_gen = JsonLdGenerator()
        
        # Семафоры для контроля нагрузки
        self.llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY)
        self.product_semaphore = asyncio.Semaphore(CONCURRENT_PRODUCTS)
        
        self.results = []
        self.errors = []
        
    async def load_urls_from_file(self, filename: str = "urls.txt") -> List[str]:
        """Загрузка URL из файла"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            logger.info(f"📋 Загружено {len(urls)} URL из файла {filename}")
            return urls
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки URL: {e}")
            return []
    
    async def process_product_worker(
        self,
        product_url: str,
        input_index: int,
        client: httpx.AsyncClient, 
        llm_semaphore: asyncio.Semaphore, 
        exporter: AsyncExporter,
        monitor: ProgressMonitor = None
    ) -> Optional[Dict[str, Any]]:
        """Обработка одного товара с качественными FAQ"""
        async with self.product_semaphore:
            try:
                logger.info(f"🚀 Начинаем обработку: {product_url}")
                
                # Обрабатываем товар через AsyncProductProcessor с валидацией
                write_lock = asyncio.Lock()
                result = await self.processor.process_product_with_validation(
                    product_url, 
                    client, 
                    llm_semaphore, 
                    write_lock
                )
                
                if result and result.get('status') == 'success':
                    # Добавляем input_index к результату
                    result['input_index'] = input_index
                    
                    # Добавляем JSON-LD разметку для FAQ
                    await self._add_json_ld_to_result(result)
                    
                    # Сохраняем результат
                    await exporter.add_result(result)
                    
                    if monitor:
                        monitor.update_progress(1)
                    
                    logger.info(f"✅ Успешно обработан: {product_url} (index {input_index})")
                    return result
                else:
                    error_msg = result.get('error', 'Неизвестная ошибка') if result else 'Нет результата'
                    logger.error(f"❌ Ошибка обработки {product_url}: {error_msg}")
                    self.errors.append({
                        'url': product_url,
                        'input_index': input_index,
                        'error': error_msg,
                        'timestamp': datetime.now().isoformat()
                    })
                    return None
                    
            except Exception as e:
                logger.error(f"❌ Критическая ошибка обработки {product_url} (index {input_index}): {e}")
                self.errors.append({
                    'url': product_url,
                    'input_index': input_index,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
                return None
    
    async def _add_json_ld_to_result(self, result: Dict[str, Any]) -> None:
        """Добавляет JSON-LD разметку к результату"""
        try:
            # Извлекаем FAQ из результата
            ru_faq = result.get('ru_content', {}).get('faq', [])
            ua_faq = result.get('ua_content', {}).get('faq', [])
            
            ru_title = result.get('ru_content', {}).get('title', '')
            ua_title = result.get('ua_content', {}).get('title', '')
            
            # Генерируем JSON-LD для RU
            if ru_faq and ru_title:
                ru_json_ld = self.json_ld_gen.generate_faq_schema(
                    faq_list=ru_faq,
                    product_name=ru_title,
                    locale='ru'
                )
                if ru_json_ld:
                    result['ru_json_ld'] = ru_json_ld
                    logger.info(f"✅ JSON-LD добавлен для RU: {len(ru_json_ld)} символов")
            
            # Генерируем JSON-LD для UA
            if ua_faq and ua_title:
                ua_json_ld = self.json_ld_gen.generate_faq_schema(
                    faq_list=ua_faq,
                    product_name=ua_title,
                    locale='ua'
                )
                if ua_json_ld:
                    result['ua_json_ld'] = ua_json_ld
                    logger.info(f"✅ JSON-LD добавлен для UA: {len(ua_json_ld)} символов")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка добавления JSON-LD: {e}")
    
    async def process_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Обработка списка URL с параллельным выполнением"""
        logger.info(f"🚀 Начинаем обработку {len(urls)} товаров")
        
        # Создаем список кортежей (input_index, url) для сохранения порядка
        indexed_urls = [(i + 1, url) for i, url in enumerate(urls)]
        
        # Инициализируем монитор с количеством товаров
        self.monitor = ProgressMonitor(total_products=len(indexed_urls))
        
        # Создаем HTTP клиент с оптимизированными настройками
        timeout = httpx.Timeout(TIMEOUT, connect=10.0)
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
        
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            # Создаем задачи для параллельной обработки с индексами
            tasks = []
            for input_index, url in indexed_urls:
                task = asyncio.create_task(
                    self.process_product_worker(
                        product_url=url,
                        input_index=input_index,
                        client=client,
                        llm_semaphore=self.llm_semaphore,
                        exporter=self.exporter,
                        monitor=self.monitor
                    )
                )
                tasks.append(task)
            
            # Выполняем все задачи параллельно
            logger.info(f"⚡ Запускаем {len(tasks)} задач параллельно с индексами")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем все результаты (успешные + ошибочные) и сохраняем input_index
            all_results = []
            successful_results = []
            
            for i, result in enumerate(results):
                input_index = indexed_urls[i][0]
                url = indexed_urls[i][1]
                
                if isinstance(result, Exception):
                    logger.error(f"❌ Исключение в задаче {i} (index {input_index}): {result}")
                    error_data = {
                        'url': url,
                        'input_index': input_index,
                        'error': str(result),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'ru_html': '',
                        'ua_html': '',
                        'ru_title': '',
                        'ua_title': '',
                        'ru_hero_image': '',
                        'ua_hero_image': '',
                        'processing_time': 0.0,
                        'errors': str(result),
                        'budget_stats': '',
                        'adapter_version': '2.0',
                        'hero_quality': 0.0,
                        'calls_per_locale': 0,
                        'canonical_slug': '',
                        'ru_valid': False,
                        'ua_valid': False
                    }
                    all_results.append(error_data)
                    # Добавляем товар с ошибкой в экспортер
                    await self.exporter.add_result(error_data)
                    self.errors.append({
                        'url': url,
                        'input_index': input_index,
                        'error': str(result),
                        'timestamp': datetime.now().isoformat()
                    })
                elif result is not None:
                    # Добавляем input_index к результату и отмечаем как успешный
                    result['input_index'] = input_index
                    result['status'] = 'success'
                    all_results.append(result)
                    successful_results.append(result)
                else:
                    # Обрабатываем случай, когда result is None
                    logger.error(f"❌ Результат None для задачи {i} (index {input_index}): {url}")
                    error_data = {
                        'url': url,
                        'input_index': input_index,
                        'error': 'Результат обработки равен None',
                        'timestamp': datetime.now().isoformat(),
                        'status': 'error',
                        'ru_html': '',
                        'ua_html': '',
                        'ru_title': '',
                        'ua_title': '',
                        'ru_hero_image': '',
                        'ua_hero_image': '',
                        'processing_time': 0.0,
                        'errors': 'Результат обработки равен None',
                        'budget_stats': '',
                        'adapter_version': '2.0',
                        'hero_quality': 0.0,
                        'calls_per_locale': 0,
                        'canonical_slug': '',
                        'ru_valid': False,
                        'ua_valid': False
                    }
                    all_results.append(error_data)
                    # Добавляем товар с ошибкой в экспортер
                    await self.exporter.add_result(error_data)
                    self.errors.append({
                        'url': url,
                        'input_index': input_index,
                        'error': 'Результат обработки равен None',
                        'timestamp': datetime.now().isoformat()
                    })
            
            # Сортируем ВСЕ результаты по input_index для сохранения порядка
            all_results.sort(key=lambda x: x.get('input_index', 0))
            successful_results.sort(key=lambda x: x.get('input_index', 0))
            
            self.results = all_results  # Теперь храним ВСЕ результаты
            logger.info(f"✅ Обработано {len(successful_results)} успешных из {len(all_results)} результатов, отсортированных по input_index")
            return all_results  # Возвращаем ВСЕ результаты, включая ошибки
    
    def print_statistics(self) -> None:
        """Выводит статистику обработки"""
        total_processed = len(self.results)
        total_errors = len(self.errors)
        # Исправляем логику подсчета - общее количество URL это количество уникальных результатов
        total_urls = total_processed
        
        logger.info("=" * 60)
        logger.info("📊 СТАТИСТИКА ОБРАБОТКИ")
        logger.info("=" * 60)
        # Считаем успешные результаты (с статусом 'success')
        successful_count = sum(1 for r in self.results if r.get('status') == 'success')
        error_count = sum(1 for r in self.results if r.get('status') == 'error')
        
        logger.info(f"Всего URL: {total_urls}")
        logger.info(f"Успешно обработано: {successful_count}")
        logger.info(f"Ошибок: {error_count}")
        logger.info(f"Процент успеха: {(successful_count/total_urls*100):.1f}%" if total_urls > 0 else "0%")
        
        if self.errors:
            logger.info("\n❌ ОШИБКИ:")
            for error in self.errors:
                logger.info(f"  - {error['url']}: {error['error']}")
        
        # Статистика FAQ
        total_faq_ru = sum(len(r.get('ru_content', {}).get('faq', [])) for r in self.results)
        total_faq_ua = sum(len(r.get('ua_content', {}).get('faq', [])) for r in self.results)
        logger.info(f"\n📝 FAQ СТАТИСТИКА:")
        logger.info(f"  RU FAQ: {total_faq_ru} вопросов")
        logger.info(f"  UA FAQ: {total_faq_ua} вопросов")
        logger.info(f"  Всего FAQ: {total_faq_ru + total_faq_ua} вопросов")
        
        # Статистика JSON-LD
        json_ld_count = sum(1 for r in self.results if r.get('ru_json_ld') or r.get('ua_json_ld'))
        logger.info(f"\n🏷️ JSON-LD СТАТИСТИКА:")
        logger.info(f"  Товаров с JSON-LD: {json_ld_count}")
        logger.info(f"  Покрытие JSON-LD: {(json_ld_count/total_processed*100):.1f}%" if total_processed > 0 else "0%")

async def main():
    """Главная функция пайплайна"""
    start_time = datetime.now()
    
    # Создаем пайплайн
    pipeline = EnhancedAsyncPipeline()
    
    # Загружаем URL
    urls = await pipeline.load_urls_from_file("urls.txt")
    if not urls:
        logger.error("❌ Нет URL для обработки")
        return
    
    # Обрабатываем ВСЕ товары из urls.txt
    test_urls = urls  # Обрабатываем все товары
    logger.info(f"🚀 Полная обработка: обрабатываем {len(test_urls)} товаров")
    
    # Обрабатываем товары
    results = await pipeline.process_urls(test_urls)
    
    # Выводим статистику
    pipeline.print_statistics()
    
    # ✅ НОВОЕ: Вывод статистики Smart Routing
    try:
        # Получаем экземпляр SmartLLMClient из любого генератора
        if hasattr(pipeline.processor, 'content_generator') and hasattr(pipeline.processor.content_generator, 'llm'):
            llm_client = pipeline.processor.content_generator.llm
            
            # Выводим детальную статистику
            llm_client.print_stats()
            
            # Сохраняем в лог-файл
            stats = llm_client.get_stats()
            
            import json
            with open('llm_usage_stats.json', 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            
            logger.info("📁 Статистика Smart Routing сохранена в llm_usage_stats.json")
        else:
            logger.warning("⚠️ SmartLLMClient не найден для статистики")
            
    except Exception as e:
        logger.warning(f"⚠️ Не удалось вывести статистику Smart Routing: {e}")
    
    # Сохраняем результаты в Excel
    if results:
        main_file = "descriptions.xlsx"
        
        # Обновляем путь к файлу в экспортере для перезаписи
        pipeline.exporter.output_file = main_file
        # Экспортируем все результаты (перезаписываем файл)
        export_result = await pipeline.exporter.export_all()
        
        if export_result.get('success'):
            logger.info(f"💾 Результаты перезаписаны в {main_file}")
        else:
            logger.error(f"❌ Ошибка сохранения: {export_result.get('error', 'Unknown error')}")
    
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    logger.info(f"⏱️ Общее время выполнения: {total_time:.2f} секунд")
    logger.info(f"⚡ Средняя скорость: {len(urls)/total_time:.2f} товаров/сек")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Выполнение прервано пользователем")
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()
