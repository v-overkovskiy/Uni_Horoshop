#!/usr/bin/env python3
"""
Скрипт для очистки кэша по URL
"""
import os
import sys
import logging
from pathlib import Path

# Добавляем путь к src в PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def clear_cache_for_urls(urls: list):
    """Очищает кэш для указанных URL"""
    logger.info(f"🧹 Очистка кэша для {len(urls)} URL")
    
    # Очищаем L1 кэш (в памяти)
    try:
        from src.morph.case_engine import get_cache_stats, LLM_CACHE
        LLM_CACHE.clear()
        logger.info("✅ L1 кэш (LLM) очищен")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось очистить L1 кэш: {e}")
    
    # Очищаем L2 кэш (файлы)
    cache_dirs = [
        'cache',
        '.cache',
        'temp',
        'tmp'
    ]
    
    for cache_dir in cache_dirs:
        if os.path.exists(cache_dir):
            try:
                import shutil
                shutil.rmtree(cache_dir)
                logger.info(f"✅ L2 кэш очищен: {cache_dir}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось очистить {cache_dir}: {e}")
    
    # Очищаем временные файлы
    temp_files = [
        'progress.json',
        'session.json',
        'urls_processed.json'
    ]
    
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                logger.info(f"✅ Временный файл удален: {temp_file}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось удалить {temp_file}: {e}")
    
    logger.info("✅ Очистка кэша завершена")

def main():
    """Основная функция"""
    # URL для очистки кэша
    urls = [
        "https://prorazko.com/visk-v-hranulakh-dlia-depiliatsii-italwax-full-body-wax-kleopatra-1-kh/",
        "https://prorazko.com/visk-v-hranulakh-dlia-depiliatsii-italwax-pour-homme-dlia-cholovikiv-1-kh/",
        "https://prorazko.com/visk-v-hranulakh-dlia-depiliatsii-italwax-top-line-koral-750-hram/",
        "https://prorazko.com/visk-v-hranulakh-dlia-depiliatsii-italwax-top-line-rozheva-perlyna-750-hram/",
        "https://prorazko.com/visk-v-hranulakh-dlia-depiliatsii-italwax-slyva-1-kh/"
    ]
    
    clear_cache_for_urls(urls)

if __name__ == "__main__":
    main()

