"""
JSON-LD схема для FAQ
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class FAQJSONLD:
    """Генератор JSON-LD разметки для FAQ"""
    
    def __init__(self, locale: str):
        self.locale = locale
        self._setup_locale_config()
    
    def _setup_locale_config(self):
        """Настройка конфигурации для локали"""
        if self.locale == 'ru':
            self.language = 'ru'
        else:  # ua
            self.language = 'uk'
    
    def build(self, faq_data: List[Dict[str, str]], product_name: str = "") -> Dict[str, Any]:
        """Построение JSON-LD разметки FAQ"""
        try:
            if not faq_data:
                return {}
            
            # Строим список вопросов и ответов
            main_entity = []
            for item in faq_data:
                if isinstance(item, dict) and 'question' in item and 'answer' in item:
                    main_entity.append({
                        "@type": "Question",
                        "name": item['question'],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": item['answer'],
                            "inLanguage": self.language
                        }
                    })
            
            if not main_entity:
                return {}
            
            jsonld = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "inLanguage": self.language,
                "mainEntity": main_entity
            }
            
            # Добавляем название страницы если есть
            if product_name:
                jsonld["name"] = f"Часто задаваемые вопросы о {product_name}"
            
            return jsonld
            
        except Exception as e:
            logger.error(f"Ошибка построения FAQ JSON-LD: {e}")
            return {}
    
    def build_question_answer(self, question: str, answer: str) -> Dict[str, Any]:
        """Построение отдельного вопроса и ответа"""
        return {
            "@type": "Question",
            "name": question,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": answer,
                "inLanguage": self.language
            }
        }
    
    def build_how_to(self, steps: List[str], name: str = "Как использовать") -> Dict[str, Any]:
        """Построение инструкции по использованию"""
        if not steps:
            return {}
        
        how_to_steps = []
        for i, step in enumerate(steps, 1):
            how_to_steps.append({
                "@type": "HowToStep",
                "position": i,
                "text": step,
                "inLanguage": self.language
            })
        
        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": name,
            "inLanguage": self.language,
            "step": how_to_steps
        }
    
    def build_article(self, title: str, content: str, author: str = "ProRazko") -> Dict[str, Any]:
        """Построение статьи"""
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "articleBody": content,
            "inLanguage": self.language,
            "author": {
                "@type": "Organization",
                "name": author
            },
            "publisher": {
                "@type": "Organization",
                "name": "ProRazko",
                "url": "https://prorazko.com"
            }
        }


