#!/usr/bin/env python3
"""
Основной скрипт пайплайна с параллельной обработкой RU/UA страниц
"""
import asyncio
import logging
import yaml
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import pandas as pd
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Импорты модулей
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.fetcher.async_client import AsyncFetcher
from src.parsing.extractors import ProductExtractor
from src.parsing.gallery_picker import GalleryPicker
from src.normalize.url_encoding import URLNormalizer
from src.normalize.units_locale import UnitsNormalizer
from src.locale.ru_rules import RULocaleValidator
from src.locale.ua_rules import UALocaleValidator
from src.build.html_blocks import HTMLBuilder
from src.llm.content_generator import LLMContentGenerator

logger = logging.getLogger(__name__)

@dataclass
class ProcessingResult:
    """Результат обработки товара"""
    url: str
    ru_html: Optional[str]
    ua_html: Optional[str]
    ru_data: Optional[Dict[str, Any]]
    ua_data: Optional[Dict[str, Any]]
    ru_hero_image: Optional[str]
    ua_hero_image: Optional[str]
    processing_time: float
    errors: List[str]

class ParallelPipeline:
    """Пайплайн с параллельной обработкой RU/UA страниц"""
    
    def __init__(self, config_path: str = "configs/pipeline.yaml"):
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._setup_components()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Загрузка конфигурации"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            return {}
    
    def _setup_logging(self):
        """Настройка логирования"""
        log_config = self.config.get('logging', {})
        level = getattr(logging, log_config.get('level', 'INFO'))
        
        logging.basicConfig(
            level=level,
            format=log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_config.get('file', 'pipeline.log'))
            ]
        )
    
    def _setup_components(self):
        """Настройка компонентов пайплайна"""
        # HTTP клиент
        perf_config = self.config.get('pipeline', {}).get('performance', {})
        self.fetcher = AsyncFetcher(
            concurrency=perf_config.get('concurrency', 6),
            rps_limit=perf_config.get('rps_limit', 3),
            timeout=perf_config.get('timeout', 15),
            retries=perf_config.get('retries', 2),
            backoff_factor=perf_config.get('backoff_factor', 1.5)
        )
        
        # Валидаторы
        self.ru_validator = RULocaleValidator()
        self.ua_validator = UALocaleValidator()
        
        # Нормализаторы
        self.url_normalizer = URLNormalizer("https://prorazko.com")
        
        # LLM генератор
        self.llm_generator = LLMContentGenerator()
    
    async def process_urls(self, urls: List[str]) -> List[ProcessingResult]:
        """Обработка списка URL с параллельной загрузкой RU/UA"""
        logger.info(f"Начинаем обработку {len(urls)} URL")
        
        # Загружаем пары RU/UA страниц параллельно
        html_pairs = await self.fetcher.fetch_batch(urls)
        
        results = []
        for i, (ua_url, (ua_html, ru_html)) in enumerate(zip(urls, html_pairs)):
            start_time = time.time()
            
            try:
                result = await self._process_single_url(ua_url, ua_html, ru_html)
                result.processing_time = time.time() - start_time
                results.append(result)
                
                logger.info(f"✅ Обработан {i+1}/{len(urls)}: {ua_url}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка обработки {ua_url}: {e}")
                results.append(ProcessingResult(
                    url=ua_url,
                    ru_html=ru_html,
                    ua_html=ua_html,
                    ru_data=None,
                    ua_data=None,
                    ru_hero_image=None,
                    ua_hero_image=None,
                    processing_time=time.time() - start_time,
                    errors=[str(e)]
                ))
        
        return results
    
    async def _process_single_url(self, ua_url: str, ua_html: Optional[str], ru_html: Optional[str]) -> ProcessingResult:
        """Обработка одной пары RU/UA страниц"""
        errors = []
        
        # Обрабатываем UA страницу
        ua_data = None
        ua_hero_image = None
        if ua_html:
            try:
                ua_data = await self._process_locale(ua_html, ua_url, 'ua')
                ua_hero_image = self._extract_hero_image(ua_html, ua_url)
            except Exception as e:
                errors.append(f"UA processing error: {e}")
        
        # Обрабатываем RU страницу
        ru_data = None
        ru_hero_image = None
        if ru_html:
            try:
                ru_data = await self._process_locale(ru_html, ua_url, 'ru')
                ru_hero_image = self._extract_hero_image(ru_html, ua_url)
            except Exception as e:
                errors.append(f"RU processing error: {e}")
        
        return ProcessingResult(
            url=ua_url,
            ru_html=ru_html,
            ua_html=ua_html,
            ru_data=ru_data,
            ua_data=ua_data,
            ru_hero_image=ru_hero_image,
            ua_hero_image=ua_hero_image,
            processing_time=0,  # Будет установлено в process_urls
            errors=errors
        )
    
    async def _process_locale(self, html: str, url: str, locale: str) -> Dict[str, Any]:
        """Обработка страницы для конкретной локали"""
        # Извлекаем данные
        extractor = ProductExtractor(locale)
        data = extractor.extract(html, url)
        
        # Нормализуем единицы измерения
        normalizer = UnitsNormalizer(locale)
        data.specs = normalizer.clean_specs(data.specs)
        
        # Генерируем контент с помощью LLM
        logger.info(f"Генерируем контент для {locale}...")
        llm_content = self.llm_generator.generate_content(data.__dict__, locale)
        
        # Объединяем извлеченные данные с LLM контентом
        enhanced_data = data.__dict__.copy()
        enhanced_data.update(llm_content)
        
        # Валидируем данные
        validator = self.ru_validator if locale == 'ru' else self.ua_validator
        validation_errors = validator.validate(enhanced_data)
        
        if validation_errors:
            logger.warning(f"Ошибки валидации для {locale}: {validation_errors}")
        
        # Строим HTML
        html_builder = HTMLBuilder(locale)
        html_content = html_builder.build_html(enhanced_data)
        
        return {
            'data': enhanced_data,
            'html': html_content,
            'validation_errors': validation_errors
        }
    
    def _extract_hero_image(self, html: str, url: str) -> Optional[str]:
        """Извлечение hero изображения"""
        try:
            picker = GalleryPicker("https://prorazko.com")
            return picker.pick_best_image(html)
        except Exception as e:
            logger.error(f"Ошибка извлечения изображения: {e}")
            return None
    
    def save_results(self, results: List[ProcessingResult], output_file: str = "descriptions.xlsx"):
        """Сохранение результатов в Excel"""
        try:
            data = []
            for result in results:
                row = {
                    'URL': result.url,
                    'Title': result.ua_data.get('data', {}).get('title', '') if result.ua_data else '',
                    'RU_HTML': result.ru_data.get('html', '') if result.ru_data else '',
                    'UA_HTML': result.ua_data.get('html', '') if result.ua_data else '',
                    'RU_Hero_Image': result.ru_hero_image or '',
                    'UA_Hero_Image': result.ua_hero_image or '',
                    'Processing_Time': result.processing_time,
                    'Validation_Status': 'OK' if not result.errors else 'ERROR',
                    'Errors': '; '.join(result.errors) if result.errors else ''
                }
                data.append(row)
            
            df = pd.DataFrame(data)
            df.to_excel(output_file, index=False)
            logger.info(f"✅ Результаты сохранены в {output_file}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения результатов: {e}")
    
    def print_stats(self, results: List[ProcessingResult]):
        """Вывод статистики обработки"""
        total = len(results)
        successful = sum(1 for r in results if not r.errors)
        failed = total - successful
        
        total_time = sum(r.processing_time for r in results)
        avg_time = total_time / total if total > 0 else 0
        
        logger.info("=== СТАТИСТИКА ОБРАБОТКИ ===")
        logger.info(f"Всего URL: {total}")
        logger.info(f"Успешно: {successful}")
        logger.info(f"Ошибок: {failed}")
        logger.info(f"Время обработки: {total_time:.2f} секунд")
        logger.info(f"Среднее время на URL: {avg_time:.2f} секунд")
        
        if failed > 0:
            logger.warning("=== ОШИБКИ ===")
            for result in results:
                if result.errors:
                    logger.warning(f"❌ {result.url}: {'; '.join(result.errors)}")

async def main():
    """Основная функция"""
    # Загружаем URL из файла
    urls_file = Path("urls.txt")
    if not urls_file.exists():
        logger.error("Файл urls.txt не найден")
        return
    
    with open(urls_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]
    
    if not urls:
        logger.error("Нет URL для обработки")
        return
    
    # Создаем и запускаем пайплайн
    pipeline = ParallelPipeline()
    
    start_time = time.time()
    results = await pipeline.process_urls(urls)
    total_time = time.time() - start_time
    
    # Сохраняем результаты
    pipeline.save_results(results)
    
    # Выводим статистику
    pipeline.print_stats(results)
    
    logger.info(f"✅ Обработка завершена за {total_time:.2f} секунд")

if __name__ == "__main__":
    asyncio.run(main())
