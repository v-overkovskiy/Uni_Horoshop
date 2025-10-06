"""
Генератор JSON-LD разметки для FAQ
"""
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class JsonLdGenerator:
    """Генератор JSON-LD разметки для различных типов контента"""
    
    def __init__(self):
        pass
    
    def generate_faq_schema(self, faq_list: List[Dict[str, str]], product_name: str, locale: str) -> str:
        """
        Создает JSON-LD разметку для FAQPage на основе списка вопросов и ответов.
        
        Args:
            faq_list: Список FAQ с ключами 'question' и 'answer'
            product_name: Название товара
            locale: Локаль ('ru' или 'ua')
            
        Returns:
            str: HTML с JSON-LD разметкой
        """
        if not faq_list:
            return ""
        
        try:
            # Определяем язык для схемы
            language = "ru" if locale == "ru" else "uk"
            
            # Создаем массив вопросов и ответов
            main_entity = []
            for item in faq_list:
                question_text = item.get("question", "").strip()
                answer_text = item.get("answer", "").strip()
                
                if question_text and answer_text:
                    question_obj = {
                        "@type": "Question",
                        "name": question_text,
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": answer_text
                        }
                    }
                    main_entity.append(question_obj)
            
            if not main_entity:
                logger.warning("Нет валидных FAQ для JSON-LD")
                return ""
            
            # Создаем основную схему FAQPage
            faq_schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "inLanguage": language,
                "name": f"Частые вопросы о {product_name}",
                "mainEntity": main_entity
            }
            
            # Форматируем JSON с отступами
            json_str = json.dumps(faq_schema, ensure_ascii=False, indent=2)
            
            # Оборачиваем в тег script
            result = f'<script type="application/ld+json">\n{json_str}\n</script>'
            
            logger.info(f"✅ Сгенерирован JSON-LD для {len(main_entity)} FAQ")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации JSON-LD для FAQ: {e}")
            return ""
    
