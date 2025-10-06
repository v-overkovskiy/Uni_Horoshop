"""
Утилита для генерации заголовков товаров на основе фактов
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TitleGenerator:
    """Генератор заголовков товаров на основе фактов"""
    
    def __init__(self):
        self.logger = logger
    
    def create_title_from_facts(self, product_facts: Dict[str, Any], locale: str) -> str:
        """Создает заголовок на основе фактов о товаре"""
        try:
            # Извлекаем ключевые данные
            brand = product_facts.get('brand', 'Epilax')
            volume = product_facts.get('volume', '')
            weight = product_facts.get('weight', '')
            product_type = product_facts.get('product_type', '')
            
            # Определяем размер
            size_info = volume or weight
            if not size_info:
                size_info = product_facts.get('size', '')
            
            # Генерируем заголовок в зависимости от локали
            if locale == 'ua':
                if product_type and size_info:
                    title = f"{product_type} {brand}, {size_info}"
                elif product_type:
                    title = f"{product_type} {brand}"
                else:
                    title = f"{brand}, {size_info}" if size_info else brand
            else:  # ru
                if product_type and size_info:
                    title = f"{product_type} {brand}, {size_info}"
                elif product_type:
                    title = f"{product_type} {brand}"
                else:
                    title = f"{brand}, {size_info}" if size_info else brand
            
            self.logger.info(f"🔧 Создан заголовок из фактов: {title}")
            return title
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка создания заголовка: {e}")
            # Fallback к простому заголовку
            return f"Epilax, {product_facts.get('volume', '') or product_facts.get('weight', '')}"
    
    def extract_title_from_h2_tag(self, html_content: str, locale: str) -> Optional[str]:
        """Извлекает заголовок из H2 тега в HTML"""
        try:
            import re
            
            # Ищем H2 теги с заголовками
            h2_pattern = r'<h2[^>]*class="prod-title"[^>]*>(.*?)</h2>'
            matches = re.findall(h2_pattern, html_content, re.DOTALL)
            
            if matches:
                title = matches[0].strip()
                # Очищаем от HTML тегов
                title = re.sub(r'<[^>]+>', '', title)
                self.logger.info(f"🔧 Извлечен заголовок из H2: {title}")
                return title
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка извлечения заголовка из H2: {e}")
            return None
    
    def validate_title(self, title: str, locale: str) -> bool:
        """Валидирует заголовок на полноту и корректность"""
        if not title or len(title.strip()) < 5:
            return False
        
        # Проверяем наличие ключевых элементов
        has_brand = 'epilax' in title.lower()
        has_size = any(unit in title.lower() for unit in ['мл', 'г', 'ml', 'g'])
        
        return has_brand and has_size
