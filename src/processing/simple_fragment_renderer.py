"""
Упрощенная версия FragmentRenderer - только рендеринг, без валидации и fallback
"""
import json
import logging
from typing import Dict, Any
from yattag import Doc

from src.schema.jsonld_faq import FAQJSONLD

logger = logging.getLogger(__name__)

class SimpleProductFragmentRenderer:
    """Упрощенный рендерер HTML фрагментов - только рендеринг готовых данных"""
    
    def __init__(self):
        self.templates = {
            'ru': {
                'faq_title': 'FAQ',
                'advantages_title': 'Преимущества',
                'specs_title': 'Характеристики'
            },
            'ua': {
                'faq_title': 'FAQ',
                'advantages_title': 'Переваги', 
                'specs_title': 'Характеристики'
            }
        }
    
    def render(self, blocks: Dict[str, Any], locale: str = 'ru') -> str:
        """Рендерит HTML структуру товара из готовых данных"""
        doc, tag, text, line = Doc().ttl()
        
        with tag('div', klass='ds-desc'):
            # Заголовок
            title = blocks.get('title', '')
            if title:
                line('h2', title, klass='prod-title')
            
            # Описание
            description = blocks.get('description', '')
            if description:
                doc.asis(f"<div class='description'>{description}</div>")
            
            # Note-buy
            note_buy = blocks.get('note_buy', '')
            if note_buy:
                with tag('p', klass='note-buy'):
                    doc.asis(note_buy)
            
            # Характеристики
            specs = blocks.get('specs', [])
            if specs:
                line('h2', self.templates[locale]['specs_title'])
                with tag('ul', klass='specs'):
                    for spec in specs:
                        with tag('li'):
                            line('span', f"{spec.get('name', spec.get('label', ''))}:", klass='spec-label')
                            text(f" {spec.get('value', '')}")
            
            # Преимущества
            advantages = blocks.get('advantages', [])
            if advantages:
                line('h2', self.templates[locale]['advantages_title'])
                with tag('ul', klass='advantages'):
                    for advantage in advantages:
                        line('li', advantage)
            
            # FAQ
            faq = blocks.get('faq', [])
            if faq:
                line('h2', self.templates[locale]['faq_title'])
                with tag('div', klass='faq'):
                    for item in faq:
                        question = item.get('question', item.get('q', ''))
                        answer = item.get('answer', item.get('a', ''))
                        if question and answer:
                            with tag('div', klass='faq-item'):
                                line('h3', question, klass='faq-question')
                                with tag('p', klass='faq-answer'):
                                    text(answer)
            
            # Изображение
            image_url = blocks.get('image_url', '')
            if image_url:
                with tag('figure', klass='hero'):
                    line('img', '', src=image_url, alt=blocks.get('photo_alt', title))
            
            # JSON-LD
            faq_jsonld = FAQJSONLD(locale).build(faq, title)
            if faq_jsonld:
                json_string = json.dumps(faq_jsonld, ensure_ascii=False)
                doc.asis(f'<script type="application/ld+json">{json_string}</script>')
            
            # Стили
            doc.asis("""
            <style>
                .ds-desc { font-family: Arial, sans-serif; line-height: 1.6; }
                .prod-title { color: #333; margin-bottom: 20px; }
                .description { margin-bottom: 20px; }
                .note-buy { background: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0; }
                .specs, .advantages { list-style: none; padding: 0; }
                .specs li, .advantages li { padding: 8px 0; border-bottom: 1px solid #eee; }
                .spec-label { font-weight: bold; color: #555; }
                .faq { margin-top: 20px; }
                .faq-item { margin-bottom: 20px; }
                .faq-question { color: #007bff; margin-bottom: 10px; }
                .faq-answer { margin-left: 20px; }
                .hero img { max-width: 100%; height: auto; }
            </style>
            """)

        return doc.getvalue()
