"""
Асинхронный экспортер результатов
"""
import asyncio
import logging
from typing import Dict, Any, List
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

class AsyncExporter:
    """Асинхронный экспортер результатов обработки"""
    
    def __init__(self, output_file: str = "descriptions.xlsx"):
        self.output_file = output_file
        self.results: List[Dict[str, Any]] = []
        self.write_lock = asyncio.Lock()
    
    async def add_result(self, result: Dict[str, Any]) -> None:
        """Добавление результата с блокировкой"""
        async with self.write_lock:
            self.results.append(result)
            logger.info(f"✅ Результат добавлен: {result.get('url', 'unknown')}")
    
    async def save_product(self, result: Dict[str, Any]) -> None:
        """Сохранение одного товара (алиас для add_result)"""
        await self.add_result(result)
    
    async def export_all(self) -> Dict[str, Any]:
        """Экспорт всех результатов в Excel"""
        async with self.write_lock:
            try:
                if not self.results:
                    logger.warning("⚠️ Нет результатов для экспорта")
                    return {'success': False, 'message': 'No results to export'}
                
                # Подготавливаем данные для Excel
                excel_data = []
                
                # Сортируем результаты по input_index для сохранения порядка из urls.txt
                sorted_results = sorted(self.results, key=lambda x: x.get('input_index', 0))
                
                # Определяем максимальный индекс для создания полного диапазона
                max_index = max([result.get('input_index', 0) for result in self.results])
                
                # Создаем словарь для быстрого поиска результатов по индексу
                results_by_index = {result.get('input_index', 0): result for result in self.results}
                
                # Создаем полный список всех результатов (включая пропущенные позиции)
                all_results = []
                for i in range(1, max_index + 1):
                    if i in results_by_index:
                        all_results.append(results_by_index[i])
                    else:
                        # Создаем пустую строку для пропущенной позиции
                        empty_result = {
                            'input_index': i,
                            'url': f'missing_position_{i}',
                            'status': 'missing',
                            'ru_html': '',
                            'ua_html': '',
                            'ru_title': '',
                            'ua_title': '',
                            'ru_hero_image': '',
                            'ua_hero_image': '',
                            'processing_time': 0.0,
                            'error': f'Position {i} was not processed',
                            'budget_stats': '',
                            'hero_quality': 0.0,
                            'calls_per_locale': 0,
                            'canonical_slug': '',
                            'ru_valid': False,
                            'ua_valid': False
                        }
                        all_results.append(empty_result)
                        logger.warning(f"⚠️ Создана пустая строка для пропущенной позиции {i}")
                
                # Теперь обрабатываем все результаты (включая созданные пустые) в правильном порядке
                for result in all_results:
                    # Извлекаем полные данные
                    ru_html = result.get('ru_html', '')
                    ua_html = result.get('ua_html', '')
                    
                    # ИСПРАВЛЕНИЕ: Используем переведенные названия из результата, НЕ извлекаем из HTML
                    ru_title = result.get('ru_title', '')
                    logger.info(f"📝 ЭКСПОРТЕР: result['ru_title'] = '{ru_title}'")
                    
                    if not ru_title:
                        ru_title = self._extract_title_from_html(ru_html)
                        logger.warning(f"⚠️ Экспортер: ru_title пустой, извлекаем из HTML: '{ru_title}'")
                    
                    ua_title = result.get('ua_title', '')
                    logger.info(f"📝 ЭКСПОРТЕР: result['ua_title'] = '{ua_title}'")
                    
                    if not ua_title:
                        ua_title = self._extract_title_from_html(ua_html)
                        logger.warning(f"⚠️ Экспортер: ua_title пустой, извлекаем из HTML: '{ua_title}'")
                    
                    # ⚠️ КРИТИЧНО: Проверяем капитализацию названий
                    if ru_title and len(ru_title) > 0:
                        if ru_title[0].islower():
                            ru_title = ru_title[0].upper() + ru_title[1:]
                            logger.info(f"🔧 Экспортер: исправлена капитализация RU названия: '{ru_title}'")
                    
                    if ua_title and len(ua_title) > 0:
                        if ua_title[0].islower():
                            ua_title = ua_title[0].upper() + ua_title[1:]
                            logger.info(f"🔧 Экспортер: исправлена капитализация UA названия: '{ua_title}'")
                    
                    # 📝 ФИНАЛЬНОЕ ЛОГИРОВАНИЕ
                    logger.info(f"📝 ЭКСПОРТЕР: Финальный ru_title = '{ru_title}'")
                    logger.info(f"📝 ЭКСПОРТЕР: Финальный ua_title = '{ua_title}'")
                    if ru_title:
                        logger.info(f"📝 ЭКСПОРТЕР: Первая буква RU = '{ru_title[0]}' - {'✅ БОЛЬШАЯ' if ru_title[0].isupper() else '❌ маленькая'}")
                    if ua_title:
                        logger.info(f"📝 ЭКСПОРТЕР: Первая буква UA = '{ua_title[0]}' - {'✅ БОЛЬШАЯ' if ua_title[0].isupper() else '❌ маленькая'}")
                    
                    # Извлекаем изображения
                    ru_hero_image = self._extract_hero_image_from_html(ru_html) or result.get('ru_hero_image', '')
                    ua_hero_image = self._extract_hero_image_from_html(ua_html) or result.get('ua_hero_image', '')
                    
                    # Время обработки
                    processing_time = result.get('processing_time', 0.0)
                    
                    # Ошибки
                    errors = result.get('error', '') or result.get('errors', '')
                    
                    # Статистика бюджета
                    budget_stats = result.get('budget_stats', '')
                    
                    # Валидация HTML
                    ru_valid = self._validate_html_content(ru_html)
                    ua_valid = self._validate_html_content(ua_html)

                    row = {
                        'Input_Index': result.get('input_index', 0),
                        'Status': result.get('status', 'unknown'),
                        'URL': result.get('url', ''),
                        'RU_Title': ru_title,
                        'UA_Title': ua_title,
                        'RU_HTML': ru_html,
                        'UA_HTML': ua_html,
                        'RU_Hero_Image': ru_hero_image,
                        'UA_Hero_Image': ua_hero_image,
                        'Processing_Time': processing_time,
                        'Errors': errors,
                        'Budget_Stats': budget_stats,
                        'Adapter_Version': '2.0',
                        'Hero_Quality': result.get('hero_quality', 0.0),
                        'Calls_Per_Locale': result.get('calls_per_locale', 0),
                        'Canonical_Slug': result.get('canonical_slug', ''),
                        'RU_Valid': 'ИСТИНА' if ru_valid else 'ЛОЖЬ',
                        'UA_Valid': 'ИСТИНА' if ua_valid else 'ЛОЖЬ',
                        'Timestamp': datetime.now().isoformat()
                    }
                    
                    # Добавляем информацию об ошибках
                    if 'error' in result:
                        row['Error'] = result['error']
                    
                    excel_data.append(row)
                
                # Создаем DataFrame и сохраняем
                df = pd.DataFrame(excel_data)
                
                # Пытаемся перезаписать файл с обработкой ошибок
                try:
                    df.to_excel(self.output_file, index=False)
                    logger.info(f"✅ Файл {self.output_file} успешно перезаписан")
                except PermissionError:
                    # Если файл заблокирован, создаем новый с timestamp
                    import time
                    timestamp = int(time.time())
                    fallback_file = f"descriptions_{timestamp}.xlsx"
                    df.to_excel(fallback_file, index=False)
                    logger.warning(f"⚠️ Файл {self.output_file} заблокирован, создана резервная копия: {fallback_file}")
                    self.output_file = fallback_file
                
                logger.info(f"✅ Результаты экспортированы в {self.output_file}")
                logger.info(f"📊 Всего строк: {len(excel_data)}")
                
                return {
                    'success': True,
                    'file': self.output_file,
                    'rows': len(excel_data),
                    'message': f'Exported {len(excel_data)} results to {self.output_file}'
                }
                
            except Exception as e:
                logger.error(f"❌ Ошибка экспорта: {e}")
                return {'success': False, 'error': str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики обработки"""
        if not self.results:
            return {'total': 0, 'successful': 0, 'failed': 0}
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.get('status') == 'success')
        failed = total - successful
        
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'success_rate': successful / total if total > 0 else 0.0
        }
    
    def _extract_title_from_html(self, html: str) -> str:
        """Извлекает заголовок из HTML с автоматической капитализацией"""
        import re
        try:
            # Ищем заголовок в h2 с классом prod-title
            title_match = re.search(r'<h2[^>]*class="prod-title"[^>]*>(.*?)</h2>', html, re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                
                # ⚠️ КРИТИЧНО: Всегда капитализируем
                if title and len(title) > 0:
                    if title[0].islower():
                        logger.warning(f"⚠️ _extract_title_from_html: маленькая буква '{title}'")
                        title = title[0].upper() + title[1:]
                        logger.info(f"✅ _extract_title_from_html: капитализировано '{title}'")
                        
                return title
            
            # Fallback: ищем любой h2
            h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
            if h2_match:
                title = h2_match.group(1).strip()
                
                # ⚠️ КРИТИЧНО: Всегда капитализируем
                if title and len(title) > 0:
                    if title[0].islower():
                        logger.warning(f"⚠️ _extract_title_from_html (fallback): маленькая буква '{title}'")
                        title = title[0].upper() + title[1:]
                        logger.info(f"✅ _extract_title_from_html (fallback): капитализировано '{title}'")
                        
                return title
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения названия из HTML: {e}")
        
        return ""
    
    def _extract_hero_image_from_html(self, html: str) -> str:
        """Извлекает изображение товара из HTML"""
        import re
        # Ищем изображение в div.product-photo
        img_match = re.search(r'<div[^>]*class="product-photo"[^>]*>.*?<img[^>]*src="([^"]*)"', html, re.DOTALL)
        if img_match:
            return img_match.group(1)
        return ""
    
    def _validate_html_content(self, html: str) -> bool:
        """Валидирует HTML контент на полноту"""
        if not html or len(html.strip()) < 100:
            return False
        
        # Проверяем на заглушки
        if 'error-message' in html:
            return False
        
        # Проверяем наличие основных секций
        required_sections = ['<h2>', '<div class="ds-desc">']
        for section in required_sections:
            if section not in html:
                return False
        
        return True
