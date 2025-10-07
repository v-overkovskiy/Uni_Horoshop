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
            
            # ✅ ИСПРАВЛЕНО: ОБНОВЛЯЕМ существующие результаты вместо перезаписи
            # Это позволяет сохранить результаты предыдущих раундов
            for new_result in all_results:
                url = new_result.get('url')
                # Ищем существующий результат для этого URL
                existing_index = next((i for i, r in enumerate(self.results) if r.get('url') == url), None)
                
                if existing_index is not None:
                    # Обновляем существующий результат
                    self.results[existing_index] = new_result
                else:
                    # Добавляем новый результат
                    self.results.append(new_result)
            
            logger.info(f"✅ Обработано {len(successful_results)} успешных из {len(all_results)} результатов, отсортированных по input_index")
            logger.info(f"📊 Всего результатов в базе: {len(self.results)}")
            return all_results  # Возвращаем результаты текущего раунда
    
    def get_failed_urls(self) -> List[str]:
        """Извлекает URL товаров со статусом 'error' для повторной обработки"""
        failed_urls = []
        for result in self.results:
            if result.get('status') == 'error':
                url = result.get('url', '')
                if url and url not in failed_urls:
                    failed_urls.append(url)
        
        logger.info(f"🔄 Найдено {len(failed_urls)} товаров с ошибками для переобработки")
        return failed_urls
    
    def clear_errors_for_urls(self, urls: List[str]) -> None:
        """Очищает ТОЛЬКО ошибки для указанных URL перед повторной обработкой
        
        ВАЖНО: НЕ удаляем результаты из self.results, только ошибки!
        Результаты будут заменены при успешной переобработке через add_result в процессоре
        """
        # Удаляем записи об ошибках для этих URL
        self.errors = [e for e in self.errors if e.get('url') not in urls]
        
        # ✅ ИСПРАВЛЕНО: НЕ удаляем результаты! Только помечаем для переобработки
        # Результаты останутся в self.results и будут обновлены если товар успешно обработается
        
        logger.info(f"🧹 Очищены ошибки для {len(urls)} товаров (результаты сохранены для обновления)")
    
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
        
        # ✅ НОВОЕ: Статистика по моделям
        model_stats = {}
        for r in self.results:
            model = r.get('processed_by_model', 'unknown')
            model_stats[model] = model_stats.get(model, 0) + 1
        
        if model_stats:
            logger.info(f"\n🤖 СТАТИСТИКА ПО МОДЕЛЯМ:")
            for model, count in sorted(model_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / successful_count * 100) if successful_count > 0 else 0
                # Выделяем дорогую модель GPT-4o
                if 'gpt-4o' in model.lower() and 'mini' not in model.lower():
                    logger.info(f"  💰 {model}: {count} товаров ({percentage:.1f}%) ⚠️ ДОРОГАЯ МОДЕЛЬ")
                else:
                    logger.info(f"  🤖 {model}: {count} товаров ({percentage:.1f}%)")
        
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
    """Главная функция пайплайна с автоматической переобработкой ошибок"""
    start_time = datetime.now()
    
    # Создаем пайплайн
    pipeline = EnhancedAsyncPipeline()
    
    # Загружаем URL
    urls = await pipeline.load_urls_from_file("urls.txt")
    if not urls:
        logger.error("❌ Нет URL для обработки")
        return
    
    logger.info(f"🚀 Полная обработка: обрабатываем {len(urls)} товаров")
    
    # ===== РАУНД 1: Первичная обработка всех товаров =====
    logger.info("=" * 80)
    logger.info("🔵 РАУНД 1: Первичная обработка всех товаров")
    logger.info("=" * 80)
    logger.info(f"📋 Обрабатываем ВСЕ {len(urls)} товаров из urls.txt")
    results = await pipeline.process_urls(urls)
    
    # Помечаем все успешные результаты раунда 1
    for result in pipeline.results:
        if result.get('status') == 'success' and 'processed_by_model' not in result:
            result['processed_by_model'] = 'gpt-4o-mini (Primary Round 1)'
    
    pipeline.print_statistics()
    
    # ===== РАУНД 2: Переобработка ошибочных товаров =====
    failed_urls = pipeline.get_failed_urls()
    if failed_urls:
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"🟡 РАУНД 2: Переобработка {len(failed_urls)} ошибочных товаров")
        logger.info("=" * 80)
        logger.info(f"📋 URL для переобработки: {failed_urls[:3]}..." if len(failed_urls) > 3 else f"📋 URL для переобработки: {failed_urls}")
        
        # Очищаем ошибки для этих URL
        pipeline.clear_errors_for_urls(failed_urls)
        
        # Переобрабатываем
        retry_results = await pipeline.process_urls(failed_urls)
        
        # Помечаем все успешные результаты раунда 2
        for result in pipeline.results:
            if result.get('url') in failed_urls and result.get('status') == 'success' and 'processed_by_model' not in result:
                result['processed_by_model'] = 'claude-3-haiku (Fallback Round 2)'
        
        pipeline.print_statistics()
        
        # ===== РАУНД 3: Финальная попытка с GPT-4o для оставшихся ошибок =====
        failed_urls_round_2 = pipeline.get_failed_urls()
        if failed_urls_round_2:
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"🔴 РАУНД 3: Финальная попытка с GPT-4o для {len(failed_urls_round_2)} товаров")
            logger.info("=" * 80)
            logger.info(f"📋 URL для переобработки: {failed_urls_round_2[:3]}..." if len(failed_urls_round_2) > 3 else f"📋 URL для переобработки: {failed_urls_round_2}")
            logger.info("🔥 Используем мощную модель GPT-4o для финальной попытки")
            
            # Очищаем ошибки для этих URL
            pipeline.clear_errors_for_urls(failed_urls_round_2)
            
            # ✅ Переключаем Resilient Recovery на GPT-4o для финального раунда
            from openai import OpenAI
            openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            pipeline.processor.llm_recovery.llm = openai_client
            pipeline.processor.llm_recovery.model = "gpt-4o"
            logger.info("🔥 Resilient Recovery переключен на GPT-4o")
            
            # ✅ СМЯГЧАЕМ ВАЛИДАЦИЮ для Round 3 (если GPT-4o не может - принимаем что есть)
            pipeline.processor.relaxed_validation = True
            logger.info("🔵 Включена СМЯГЧЕННАЯ ВАЛИДАЦИЯ для Round 3 (FAQ≥2, advantages≥2, HTML≥800 байт)")
            
            # Помечаем что это раунд с GPT-4o
            pipeline.processor.current_model = "gpt-4o"
            
            # Финальная попытка с мощной моделью
            final_results = await pipeline.process_urls(failed_urls_round_2)
            
            # Помечаем все результаты этого раунда как обработанные GPT-4o
            for result in pipeline.results:
                if result.get('url') in failed_urls_round_2 and result.get('status') == 'success':
                    result['processed_by_model'] = 'gpt-4o (Resilient Recovery Round 3)'
            
            pipeline.print_statistics()
    
    # ===== ФИНАЛЬНАЯ СТАТИСТИКА =====
    logger.info("")
    logger.info("=" * 80)
    logger.info("🏁 ФИНАЛЬНАЯ СТАТИСТИКА ПОСЛЕ ВСЕХ РАУНДОВ")
    logger.info("=" * 80)
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
    if pipeline.results:
        main_file = "descriptions.xlsx"
        
        logger.info(f"💾 Сохраняем {len(pipeline.results)} результатов в Excel...")
        
        # ⚠️ КРИТИЧЕСКИ ВАЖНО: Очищаем экспортер и добавляем только актуальные результаты
        # Это предотвращает дублирование записей между раундами
        pipeline.exporter.results = []
        for result in pipeline.results:
            await pipeline.exporter.add_result(result)
        
        # Обновляем путь к файлу в экспортере для перезаписи
        pipeline.exporter.output_file = main_file
        # Экспортируем все результаты (перезаписываем файл)
        export_result = await pipeline.exporter.export_all()
        
        if export_result.get('success'):
            logger.info(f"💾 Результаты перезаписаны в {main_file}")
            logger.info(f"📊 Экспортировано {len(pipeline.results)} товаров")
        else:
            logger.error(f"❌ Ошибка сохранения: {export_result.get('error', 'Unknown error')}")
    else:
        logger.warning("⚠️ Нет результатов для экспорта")
    
    # ===== ИТОГОВОЕ САММАРИ =====
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    avg_time_per_product = total_time / len(urls) if urls else 0
    
    # Подсчет статистики по моделям
    model_stats = {}
    for r in pipeline.results:
        model = r.get('processed_by_model', 'unknown')
        model_stats[model] = model_stats.get(model, 0) + 1
    
    # Подсчет успешных/ошибок
    successful_count = sum(1 for r in pipeline.results if r.get('status') == 'success')
    error_count = sum(1 for r in pipeline.results if r.get('status') == 'error')
    
    logger.info("")
    logger.info("")
    logger.info("╔" + "═" * 98 + "╗")
    logger.info("║" + " " * 35 + "🎯 ИТОГОВОЕ САММАРИ ОБРАБОТКИ" + " " * 35 + "║")
    logger.info("╚" + "═" * 98 + "╝")
    logger.info("")
    logger.info("📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ:")
    logger.info(f"   ├─ Всего товаров в обработке: {len(urls)}")
    logger.info(f"   ├─ ✅ Успешно обработано: {successful_count} ({successful_count/len(urls)*100:.1f}%)" if urls else "   ├─ ✅ Успешно обработано: 0")
    logger.info(f"   └─ ❌ Ошибок: {error_count} ({error_count/len(urls)*100:.1f}%)" if urls else "   └─ ❌ Ошибок: 0")
    logger.info("")
    logger.info("⏱️  ПРОИЗВОДИТЕЛЬНОСТЬ:")
    logger.info(f"   ├─ Общее время обработки: {int(total_time//60)} мин {int(total_time%60)} сек ({total_time:.2f} сек)")
    logger.info(f"   ├─ Среднее время на товар: {int(avg_time_per_product//60)} мин {int(avg_time_per_product%60)} сек ({avg_time_per_product:.2f} сек)")
    logger.info(f"   └─ Скорость обработки: {len(urls)/total_time:.3f} товаров/сек" if total_time > 0 else "   └─ Скорость обработки: N/A")
    logger.info("")
    logger.info("🤖 ИСПОЛЬЗОВАНИЕ LLM МОДЕЛЕЙ:")
    
    if model_stats:
        # Сортируем по количеству (от большего к меньшему)
        sorted_models = sorted(model_stats.items(), key=lambda x: x[1], reverse=True)
        
        for i, (model, count) in enumerate(sorted_models):
            percentage = (count / successful_count * 100) if successful_count > 0 else 0
            is_last = (i == len(sorted_models) - 1)
            prefix = "   └─" if is_last else "   ├─"
            
            # Выделяем дорогую модель GPT-4o
            if 'gpt-4o' in model.lower() and 'mini' not in model.lower():
                logger.info(f"{prefix} 💰 {model}: {count} товаров ({percentage:.1f}%) ⚠️  ДОРОГАЯ МОДЕЛЬ!")
            elif 'claude' in model.lower():
                logger.info(f"{prefix} 🟣 {model}: {count} товаров ({percentage:.1f}%) - Fallback")
            elif 'mini' in model.lower():
                logger.info(f"{prefix} 💚 {model}: {count} товаров ({percentage:.1f}%) - Основная (дешево)")
            else:
                logger.info(f"{prefix} 🤖 {model}: {count} товаров ({percentage:.1f}%)")
    else:
        logger.info("   └─ Нет данных о моделях")
    
    logger.info("")
    logger.info("=" * 100)
    logger.info(f"✅ ОБРАБОТКА ЗАВЕРШЕНА! Результаты сохранены в Excel")
    logger.info("=" * 100)
    logger.info("")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Выполнение прервано пользователем")
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()
