"""
Система отслеживания прогресса с no-exclude режимом
"""
import json
import os
import logging
from typing import Dict, Set, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Отслеживание прогресса обработки с возможностью resume"""
    
    def __init__(self, progress_file: str = "progress.json"):
        self.progress_file = progress_file
        self.progress = self._load_progress()
    
    def _load_progress(self) -> Dict[str, Any]:
        """Загружает прогресс из файла"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Ошибка загрузки прогресса: {e}")
        
        return {
            "processed": {},
            "pending": {},
            "failed": {},
            "session_start": datetime.now().isoformat(),
            "total_urls": 0,
            "completed": 0
        }
    
    def _save_progress(self):
        """Сохраняет прогресс в файл"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")
    
    def is_processed(self, url: str, locale: str) -> bool:
        """Проверяет, обработан ли URL для локали"""
        key = f"{url}:{locale}"
        return key in self.progress["processed"]
    
    def mark_processed(self, url: str, locale: str, result: Dict[str, Any]):
        """Отмечает URL как обработанный"""
        key = f"{url}:{locale}"
        self.progress["processed"][key] = {
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        self._save_progress()
    
    def add_to_pending(self, url: str, locale: str, reason: str, retry_count: int = 0):
        """Добавляет URL в очередь повторной обработки"""
        key = f"{url}:{locale}"
        self.progress["pending"][key] = {
            "url": url,
            "locale": locale,
            "reason": reason,
            "retry_count": retry_count,
            "added_at": datetime.now().isoformat()
        }
        self._save_progress()
    
    def get_pending(self) -> List[Dict[str, Any]]:
        """Возвращает список URL для повторной обработки"""
        return list(self.progress["pending"].values())
    
    def remove_from_pending(self, url: str, locale: str):
        """Удаляет URL из очереди повторной обработки"""
        key = f"{url}:{locale}"
        if key in self.progress["pending"]:
            del self.progress["pending"][key]
            self._save_progress()
    
    def mark_failed(self, url: str, locale: str, reason: str):
        """Отмечает URL как окончательно неудачный"""
        key = f"{url}:{locale}"
        self.progress["failed"][key] = {
            "url": url,
            "locale": locale,
            "reason": reason,
            "failed_at": datetime.now().isoformat()
        }
        self._save_progress()
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику прогресса"""
        total_processed = len(self.progress["processed"])
        total_pending = len(self.progress["pending"])
        total_failed = len(self.progress["failed"])
        
        return {
            "processed": total_processed,
            "pending": total_pending,
            "failed": total_failed,
            "total": total_processed + total_pending + total_failed,
            "completion_rate": total_processed / (total_processed + total_pending + total_failed) if (total_processed + total_pending + total_failed) > 0 else 0
        }
    
    def reset_session(self):
        """Сбрасывает сессию для нового запуска"""
        self.progress = {
            "processed": {},
            "pending": {},
            "failed": {},
            "session_start": datetime.now().isoformat(),
            "total_urls": 0,
            "completed": 0
        }
        self._save_progress()


