"""
HTML-санитайзер для очистки описаний от мусора
"""
import re
import logging
from typing import List

logger = logging.getLogger(__name__)

class HTMLSanitizer:
    """Санитайзер для очистки HTML-контента от мусора"""
    
    def __init__(self):
        # Паттерны для удаления HTML-мусора
        self.html_cleanup_patterns = [
            # Удаляем вложенные div внутри p
            (r'<div[^>]*>', ''),
            (r'</div>', ''),
            
            # Удаляем script и style блоки
            (r'<script[^>]*>.*?</script>', '', re.DOTALL),
            (r'<style[^>]*>.*?</style>', '', re.DOTALL),
            
            # Удаляем markdown-блоки
            (r'```.*?```', '', re.DOTALL),
            (r'`[^`]+`', ''),
            
            # Удаляем управляющие символы
            (r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ''),
            
            # Удаляем лишние пробелы и переносы
            (r'\s+', ' '),
            (r'\n\s*\n', '\n'),
            
            # Удаляем пустые теги
            (r'<[^>]+>\s*</[^>]+>', ''),
            (r'<[^>]+>\s*$', ''),
        ]
        
        # Разрешенные HTML теги для описаний
        self.allowed_tags = ['p', 'br', 'strong', 'em', 'b', 'i', 'u']
        
        # Паттерны для очистки от HTML-тегов (кроме разрешенных)
        self.tag_cleanup_pattern = re.compile(r'<(?!\/?(?:' + '|'.join(self.allowed_tags) + ')\b)[^>]*>', re.IGNORECASE)
    
    def sanitize_text(self, text: str) -> str:
        """
        Очищает текст от HTML-мусора
        
        Args:
            text: Исходный текст
            
        Returns:
            Очищенный текст
        """
        if not text:
            return ""
        
        # Применяем паттерны очистки
        cleaned_text = text
        for pattern, replacement, *flags in self.html_cleanup_patterns:
            flags = flags[0] if flags else 0
            cleaned_text = re.sub(pattern, replacement, cleaned_text, flags=flags)
        
        # Удаляем неразрешенные HTML теги
        cleaned_text = self.tag_cleanup_pattern.sub('', cleaned_text)
        
        # Финальная очистка
        cleaned_text = cleaned_text.strip()
        
        # Удаляем множественные пробелы
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        logger.debug(f"Текст очищен: {len(text)} -> {len(cleaned_text)} символов")
        return cleaned_text
    
    def sanitize_paragraphs(self, paragraphs: list) -> list:
        """
        Очищает список параграфов от HTML-мусора
        
        Args:
            paragraphs: Список параграфов
            
        Returns:
            Очищенный список параграфов
        """
        if not paragraphs:
            return []
        
        cleaned_paragraphs = []
        for paragraph in paragraphs:
            if paragraph and paragraph.strip():
                cleaned = self.sanitize_text(paragraph)
                if cleaned:
                    cleaned_paragraphs.append(cleaned)
        
        logger.info(f"Очищено параграфов: {len(paragraphs)} -> {len(cleaned_paragraphs)}")
        return cleaned_paragraphs
    
    def create_clean_description_html(self, paragraphs: list, bundle_html: str = "") -> str:
        """
        Создает чистый HTML описания без мусора
        
        Args:
            paragraphs: Список очищенных параграфов
            bundle_html: HTML секции состава набора
            
        Returns:
            Чистый HTML описания
        """
        if not paragraphs:
            return f'<div class="description">{bundle_html}</div>'
        
        # Создаем чистые параграфы
        clean_paragraphs = []
        for paragraph in paragraphs:
            if paragraph and paragraph.strip():
                clean_paragraphs.append(f'<p>{self.sanitize_text(paragraph)}</p>')
        
        # Объединяем параграфы и секцию состава
        description_content = ''.join(clean_paragraphs)
        if bundle_html:
            description_content += bundle_html
        
        # Оборачиваем в контейнер
        final_html = f'<div class="description">{description_content}</div>'
        
        logger.info(f"Создан чистый HTML описания: {len(final_html)} символов")
        return final_html
    
    def validate_html_structure(self, html: str) -> bool:
        """
        Проверяет корректность HTML структуры
        
        Args:
            html: HTML для проверки
            
        Returns:
            True если структура корректна
        """
        # Проверяем отсутствие вложенных div в p
        if re.search(r'<p[^>]*>.*?<div[^>]*>.*?</div>.*?</p>', html, re.DOTALL):
            logger.warning("❌ Найдены вложенные div в p тегах")
            return False
        
        # Проверяем отсутствие script/style
        if re.search(r'<(script|style)[^>]*>', html, re.IGNORECASE):
            logger.warning("❌ Найдены script/style теги")
            return False
        
        # Проверяем корректность структуры
        if not re.search(r'<div class="description">', html):
            logger.warning("❌ Отсутствует контейнер description")
            return False
        
        logger.info("✅ HTML структура корректна")
        return True
