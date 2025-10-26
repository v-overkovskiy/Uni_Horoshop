"""
SEO-оптимизатор для наборов товаров
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SEOBundleOptimizer:
    """SEO-оптимизатор для улучшения релевантности описаний наборов"""
    
    def __init__(self):
        # Ключевые слова для SEO-оптимизации наборов
        self.seo_keywords = {
            'ru': {
                'набор': ['набор для депиляции', 'комплект для депиляции', 'стартовый набор'],
                'включает': ['включает в себя', 'содержит', 'состоит из'],
                'компоненты': ['компоненты набора', 'состав комплекта', 'элементы набора'],
                'профессиональный': ['профессиональный набор', 'профессиональный комплект'],
                'полный': ['полный набор', 'комплектный набор', 'укомплектованный набор']
            },
            'ua': {
                'набір': ['набір для депіляції', 'комплект для депіляції', 'стартовий набір'],
                'включає': ['включає в себе', 'містить', 'складається з'],
                'компоненти': ['компоненти набору', 'склад комплекту', 'елементи набору'],
                'професійний': ['професійний набір', 'професійний комплект'],
                'повний': ['повний набір', 'комплектний набір', 'укомплектований набір']
            }
        }
    
    def optimize_description_for_bundle(self, description: str, product_facts: Dict[str, Any], 
                                      bundle_components: List[str], locale: str) -> str:
        """
        SEO-оптимизирует описание набора для лучшей релевантности
        
        Args:
            description: Базовое описание
            product_facts: Факты о товаре
            bundle_components: Компоненты набора
            locale: Локаль ('ru' или 'ua')
            
        Returns:
            SEO-оптимизированное описание
        """
        try:
            if not bundle_components:
                return description
            
            # Получаем ключевые слова для локали
            keywords = self.seo_keywords.get(locale, self.seo_keywords['ru'])
            
            # Создаем SEO-оптимизированное введение
            seo_intro = self._create_seo_intro(product_facts, bundle_components, keywords, locale)
            
            # Добавляем SEO-ключевые слова в описание
            optimized_description = self._inject_seo_keywords(description, keywords, locale)
            
            # Объединяем SEO-введение с оптимизированным описанием
            final_description = f"{seo_intro} {optimized_description}"
            
            logger.info(f"✅ SEO-оптимизация применена для {locale}")
            return final_description
            
        except Exception as e:
            logger.error(f"❌ Ошибка SEO-оптимизации: {e}")
            return description
    
    def _create_seo_intro(self, product_facts: Dict[str, Any], bundle_components: List[str], 
                         keywords: Dict[str, List[str]], locale: str) -> str:
        """Создает SEO-оптимизированное введение"""
        title = product_facts.get('title', '')
        
        if locale == 'ua':
            intro_templates = [
                f"{title} - це {keywords['професійний'][0]} з {len(bundle_components)} компонентами для ефективної депіляції.",
                f"Повний {keywords['набір'][0]} {title} {keywords['включає'][0]} всі необхідні елементи для професійної депіляції.",
                f"Комплектний {keywords['набір'][0]} {title} - це все необхідне для якісної депіляції в одному наборі."
            ]
        else:
            intro_templates = [
                f"{title} - это {keywords['профессиональный'][0]} с {len(bundle_components)} компонентами для эффективной депиляции.",
                f"Полный {keywords['набор'][0]} {title} {keywords['включает'][0]} все необходимые элементы для профессиональной депиляции.",
                f"Комплектный {keywords['набор'][0]} {title} - это все необходимое для качественной депиляции в одном наборе."
            ]
        
        # Выбираем наиболее подходящий шаблон
        return intro_templates[0]
    
    def _inject_seo_keywords(self, description: str, keywords: Dict[str, List[str]], locale: str) -> str:
        """Внедряет SEO-ключевые слова в описание"""
        # Добавляем ключевые слова в описание для лучшей релевантности
        if locale == 'ua':
            seo_phrases = [
                "комплектний набір для депіляції",
                "всі необхідні компоненти",
                "професійний комплект"
            ]
        else:
            seo_phrases = [
                "комплектный набор для депиляции",
                "все необходимые компоненты", 
                "профессиональный комплект"
            ]
        
        # Добавляем SEO-фразы в конец описания
        seo_addition = f" {', '.join(seo_phrases)}."
        return description + seo_addition
    
    def create_bundle_meta_description(self, product_facts: Dict[str, Any], 
                                     bundle_components: List[str], locale: str) -> str:
        """
        Создает SEO-оптимизированное мета-описание для набора
        
        Args:
            product_facts: Факты о товаре
            bundle_components: Компоненты набора
            locale: Локаль ('ru' или 'ua')
            
        Returns:
            SEO-оптимизированное мета-описание
        """
        title = product_facts.get('title', '')
        
        if locale == 'ua':
            meta_template = f"{title} - повний набір для депіляції з {len(bundle_components)} компонентами. Купити з доставкою по Україні."
        else:
            meta_template = f"{title} - полный набор для депиляции с {len(bundle_components)} компонентами. Купить с доставкой по Украине."
        
        return meta_template
