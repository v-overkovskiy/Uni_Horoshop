"""
Быстрая валидация контента - 1 сек вместо 15 сек
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class QuickValidator:
    """Быстрая валидация только критичных элементов"""
    
    def __init__(self):
        pass
    
    def validate_content(self, content: Dict[str, Any], locale: str) -> bool:
        """Быстрая валидация контента (1 сек вместо 15 сек)"""
        try:
            errors = []
            
            # Критичные проверки
            if not content.get('title') or len(str(content.get('title', '')).strip()) < 3:
                errors.append("Missing or too short title")
                
            if not content.get('description') or len(str(content.get('description', '')).strip()) < 10:
                errors.append("Missing or too short description")
                
            if not content.get('faq') or len(content.get('faq', [])) != 6:
                errors.append(f"FAQ count != 6, got {len(content.get('faq', []))}")
                
            if 'error-message' in str(content):
                errors.append("Contains error message")
                
            if not content.get('note_buy') or len(str(content.get('note_buy', '')).strip()) < 5:
                errors.append("Missing or too short note_buy")
            
            # Логируем результат
            if errors:
                logger.warning(f"⚠️ Быстрая валидация не пройдена для {locale}: {errors}")
                return False
            else:
                logger.info(f"✅ Быстрая валидация пройдена для {locale}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка быстрой валидации: {e}")
            return False
    
    def validate_html(self, html: str, locale: str) -> bool:
        """Быстрая валидация HTML (1 сек вместо 10 сек)"""
        try:
            # Только критичные проверки HTML
            if not html or len(html.strip()) < 100:
                logger.warning(f"⚠️ HTML слишком короткий для {locale}")
                return False
                
            if 'error-message' in html:
                logger.warning(f"⚠️ HTML содержит error-message для {locale}")
                return False
                
            # Проверяем наличие основных элементов
            required_elements = ['<h2>', '<div class="ds-desc">']
            for element in required_elements:
                if element not in html:
                    logger.warning(f"⚠️ HTML не содержит {element} для {locale}")
                    return False
            
            logger.info(f"✅ HTML валидация пройдена для {locale}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации HTML: {e}")
            return False
