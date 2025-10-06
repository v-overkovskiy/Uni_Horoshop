"""
Правила валидации для русской локали
"""
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class RULocaleValidator:
    """Валидатор для русской локали"""
    
    def __init__(self):
        self.locale = 'ru'
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Настройка паттернов для русской локали"""
        # Русские слова и фразы
        self.ru_patterns = {
            'description': [
                'описание', 'товар', 'качественный', 'профессиональный',
                'использование', 'применение', 'рекомендуется', 'подходит'
            ],
            'specs': [
                'бренд', 'тип', 'материал', 'объем', 'вес', 'цвет', 'размер',
                'назначение', 'характеристики', 'параметры'
            ],
            'advantages': [
                'преимущества', 'особенности', 'плюсы', 'достоинства',
                'качество', 'надежность', 'эффективность'
            ],
            'faq': [
                'как использовать', 'как применять', 'как хранить',
                'подходит ли', 'можно ли', 'есть ли', 'какой'
            ]
        }
        
        # Украинские слова, которые не должны быть в русской локали
        self.ua_intrusion_patterns = [
            'тонік', 'депіляції', 'екстрактом', 'ківі', 'масажна', 'свічка',
            'матеріал', 'об\'єм', 'переваги', 'питання', 'відповіді',
            'інтернет-магазині', 'купити', 'швидкою', 'доставкою'
        ]
        
        # Промо-заглушки
        self.promo_patterns = [
            'pro razko', 'интернет-магазин материалов', 'товары для мастеров',
            'качественный продукт для профессионального использования'
        ]
    
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Валидация данных для русской локали"""
        errors = []
        
        # Проверяем заголовок
        title_errors = self._validate_title(data.get('title', ''))
        errors.extend(title_errors)
        
        # Проверяем описание
        desc_errors = self._validate_description(data.get('description', ''))
        errors.extend(desc_errors)
        
        # Проверяем характеристики
        specs_errors = self._validate_specs(data.get('specs', []))
        errors.extend(specs_errors)
        
        # Проверяем преимущества
        advantages_errors = self._validate_advantages(data.get('advantages', []))
        errors.extend(advantages_errors)
        
        # Проверяем FAQ
        faq_errors = self._validate_faq(data.get('faq', []))
        errors.extend(faq_errors)
        
        # Проверяем на украинские интрузии
        intrusion_errors = self._validate_no_ua_intrusion(data)
        errors.extend(intrusion_errors)
        
        return errors
    
    def _validate_title(self, title: str) -> List[str]:
        """Валидация заголовка"""
        errors = []
        
        if not title:
            errors.append("Пустой заголовок")
            return errors
        
        # Проверяем на украинские слова
        for ua_word in self.ua_intrusion_patterns:
            if ua_word in title.lower():
                errors.append(f"Украинское слово в заголовке: {ua_word}")
        
        return errors
    
    def _validate_description(self, description: str) -> List[str]:
        """Валидация описания"""
        errors = []
        
        if not description:
            errors.append("Пустое описание")
            return errors
        
        # Проверяем на промо-заглушки
        for promo in self.promo_patterns:
            if promo.lower() in description.lower():
                errors.append(f"Промо-заглушка в описании: {promo}")
        
        # Проверяем на украинские слова
        for ua_word in self.ua_intrusion_patterns:
            if ua_word in description.lower():
                errors.append(f"Украинское слово в описании: {ua_word}")
        
        # Проверяем структуру (должно быть 2 абзаца)
        paragraphs = [p.strip() for p in description.split('\n') if p.strip()]
        if len(paragraphs) < 2:
            errors.append("Недостаточно абзацев в описании (должно быть 2)")
        
        return errors
    
    def _validate_specs(self, specs: List[Dict[str, str]]) -> List[str]:
        """Валидация характеристик"""
        errors = []
        
        if not specs:
            errors.append("Пустые характеристики")
            return errors
        
        if len(specs) < 3:
            errors.append(f"Недостаточно характеристик: {len(specs)}/3")
        
        # Проверяем на украинские лейблы
        for spec in specs:
            if not isinstance(spec, dict) or 'name' not in spec:
                continue
            
            name = spec['name'].lower()
            for ua_word in self.ua_intrusion_patterns:
                if ua_word in name:
                    errors.append(f"Украинский лейбл в характеристиках: {spec['name']}")
        
        return errors
    
    def _validate_advantages(self, advantages: List[str]) -> List[str]:
        """Валидация преимуществ"""
        errors = []
        
        if not advantages:
            errors.append("Пустые преимущества")
            return errors
        
        if len(advantages) < 4:
            errors.append(f"Недостаточно преимуществ: {len(advantages)}/4")
        
        # Проверяем на украинские слова
        for advantage in advantages:
            for ua_word in self.ua_intrusion_patterns:
                if ua_word in advantage.lower():
                    errors.append(f"Украинское слово в преимуществах: {ua_word}")
        
        return errors
    
    def _validate_faq(self, faq: List[Dict[str, str]]) -> List[str]:
        """Валидация FAQ"""
        errors = []
        
        if not faq:
            errors.append("Пустой FAQ")
            return errors
        
        if len(faq) < 6:
            errors.append(f"Недостаточно FAQ: {len(faq)}/6")
        
        # Проверяем на шаблонные вопросы
        template_questions = [
            'как использовать ароматическую массажную свечу',
            'как использовать тоник до депиляции',
            'как использовать молочко для тела',
            'как использовать дезодорант-стик'
        ]
        
        for item in faq:
            if not isinstance(item, dict) or 'question' not in item:
                continue
            
            question = item['question'].lower()
            for template in template_questions:
                if template in question:
                    errors.append(f"Шаблонный вопрос в FAQ: {item['question']}")
            
            # Проверяем на украинские слова
            for ua_word in self.ua_intrusion_patterns:
                if ua_word in question:
                    errors.append(f"Украинское слово в FAQ: {ua_word}")
        
        return errors
    
    def _validate_no_ua_intrusion(self, data: Dict[str, Any]) -> List[str]:
        """Проверка на отсутствие украинских интрузий"""
        errors = []
        
        # Проверяем все текстовые поля
        text_fields = ['title', 'description']
        for field in text_fields:
            text = data.get(field, '')
            if text:
                for ua_word in self.ua_intrusion_patterns:
                    if ua_word in text.lower():
                        errors.append(f"Украинское слово в {field}: {ua_word}")
        
        return errors
    
    def validate_alt_text(self, alt_text: str, h1_text: str) -> List[str]:
        """Валидация alt текста"""
        errors = []
        
        if not alt_text or not h1_text:
            errors.append("Пустой alt или h1 текст")
            return errors
        
        # Alt должен содержать h1 текст
        if h1_text.lower() not in alt_text.lower():
            errors.append("Alt текст не содержит h1 заголовок")
        
        # Alt должен быть на русском
        for ua_word in self.ua_intrusion_patterns:
            if ua_word in alt_text.lower():
                errors.append(f"Украинское слово в alt: {ua_word}")
        
        return errors


