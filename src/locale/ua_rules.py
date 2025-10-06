"""
Правила валидации для украинской локали
"""
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class UALocaleValidator:
    """Валидатор для украинской локали"""
    
    def __init__(self):
        self.locale = 'ua'
        self._setup_patterns()
    
    def _setup_patterns(self):
        """Настройка паттернов для украинской локали"""
        # Украинские слова и фразы
        self.ua_patterns = {
            'description': [
                'опис', 'товар', 'якісний', 'професійний',
                'використання', 'застосування', 'рекомендується', 'підходить'
            ],
            'specs': [
                'бренд', 'тип', 'матеріал', 'об\'єм', 'вага', 'колір', 'розмір',
                'призначення', 'характеристики', 'параметри'
            ],
            'advantages': [
                'переваги', 'особливості', 'плюси', 'достоїнства',
                'якість', 'надійність', 'ефективність'
            ],
            'faq': [
                'як використовувати', 'як застосовувати', 'як зберігати',
                'чи підходить', 'чи можна', 'чи є', 'який'
            ]
        }
        
        # Русские слова, которые не должны быть в украинской локали
        self.ru_intrusion_patterns = [
            'тоник', 'депиляции', 'экстрактом', 'киви', 'массажная', 'свеча',
            'материал', 'объем', 'преимущества', 'вопросы', 'ответы',
            'интернет-магазине', 'купить', 'быстрой', 'доставкой'
        ]
        
        # Промо-заглушки
        self.promo_patterns = [
            'pro razko', 'інтернет-магазин матеріалів', 'товари для майстрів',
            'якісний продукт для професійного використання'
        ]
    
    def validate(self, data: Dict[str, Any]) -> List[str]:
        """Валидация данных для украинской локали"""
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
        
        # Проверяем на русские интрузии
        intrusion_errors = self._validate_no_ru_intrusion(data)
        errors.extend(intrusion_errors)
        
        return errors
    
    def _validate_title(self, title: str) -> List[str]:
        """Валидация заголовка"""
        errors = []
        
        if not title:
            errors.append("Пустий заголовок")
            return errors
        
        # Проверяем на русские слова
        for ru_word in self.ru_intrusion_patterns:
            if ru_word in title.lower():
                errors.append(f"Русское слово в заголовке: {ru_word}")
        
        return errors
    
    def _validate_description(self, description: str) -> List[str]:
        """Валидация описания"""
        errors = []
        
        if not description:
            errors.append("Пустий опис")
            return errors
        
        # Проверяем на промо-заглушки
        for promo in self.promo_patterns:
            if promo.lower() in description.lower():
                errors.append(f"Промо-заглушка в описі: {promo}")
        
        # Проверяем на русские слова
        for ru_word in self.ru_intrusion_patterns:
            if ru_word in description.lower():
                errors.append(f"Русское слово в описі: {ru_word}")
        
        # Проверяем структуру (должно быть 2 абзаца)
        paragraphs = [p.strip() for p in description.split('\n') if p.strip()]
        if len(paragraphs) < 2:
            errors.append("Недостатньо абзаців в описі (має бути 2)")
        
        return errors
    
    def _validate_specs(self, specs: List[Dict[str, str]]) -> List[str]:
        """Валидация характеристик"""
        errors = []
        
        if not specs:
            errors.append("Пусті характеристики")
            return errors
        
        if len(specs) < 3:
            errors.append(f"Недостатньо характеристик: {len(specs)}/3")
        
        # Проверяем на русские лейблы
        for spec in specs:
            if not isinstance(spec, dict) or 'name' not in spec:
                continue
            
            name = spec['name'].lower()
            for ru_word in self.ru_intrusion_patterns:
                if ru_word in name:
                    errors.append(f"Русский лейбл в характеристиках: {spec['name']}")
        
        # Проверяем на дубликаты
        seen_values = set()
        for spec in specs:
            if not isinstance(spec, dict) or 'value' not in spec:
                continue
            
            value = spec['value']
            if value in seen_values:
                errors.append(f"Дубликат в характеристиках: {value}")
            seen_values.add(value)
        
        return errors
    
    def _validate_advantages(self, advantages: List[str]) -> List[str]:
        """Валидация преимуществ"""
        errors = []
        
        if not advantages:
            errors.append("Пусті переваги")
            return errors
        
        if len(advantages) < 4:
            errors.append(f"Недостатньо переваг: {len(advantages)}/4")
        
        # Проверяем на русские слова
        for advantage in advantages:
            for ru_word in self.ru_intrusion_patterns:
                if ru_word in advantage.lower():
                    errors.append(f"Русское слово в перевагах: {ru_word}")
        
        return errors
    
    def _validate_faq(self, faq: List[Dict[str, str]]) -> List[str]:
        """Валидация FAQ"""
        errors = []
        
        if not faq:
            errors.append("Пустий FAQ")
            return errors
        
        if len(faq) < 6:
            errors.append(f"Недостатньо FAQ: {len(faq)}/6")
        
        # Проверяем на шаблонные вопросы
        template_questions = [
            'як використовувати ароматичну масажну свічку',
            'як використовувати тонік до депіляції',
            'як використовувати молочко для тіла',
            'як використовувати дезодорант-стік'
        ]
        
        for item in faq:
            if not isinstance(item, dict) or 'question' not in item:
                continue
            
            question = item['question'].lower()
            for template in template_questions:
                if template in question:
                    errors.append(f"Шаблонне питання в FAQ: {item['question']}")
            
            # Проверяем на русские слова
            for ru_word in self.ru_intrusion_patterns:
                if ru_word in question:
                    errors.append(f"Русское слово в FAQ: {ru_word}")
        
        return errors
    
    def _validate_no_ru_intrusion(self, data: Dict[str, Any]) -> List[str]:
        """Проверка на отсутствие русских интрузий"""
        errors = []
        
        # Проверяем все текстовые поля
        text_fields = ['title', 'description']
        for field in text_fields:
            text = data.get(field, '')
            if text:
                for ru_word in self.ru_intrusion_patterns:
                    if ru_word in text.lower():
                        errors.append(f"Русское слово в {field}: {ru_word}")
        
        return errors
    
    def validate_alt_text(self, alt_text: str, h1_text: str) -> List[str]:
        """Валидация alt текста"""
        errors = []
        
        if not alt_text or not h1_text:
            errors.append("Пустий alt або h1 текст")
            return errors
        
        # Alt должен содержать h1 текст
        if h1_text.lower() not in alt_text.lower():
            errors.append("Alt текст не містить h1 заголовок")
        
        # Alt должен быть на украинском
        for ru_word in self.ru_intrusion_patterns:
            if ru_word in alt_text.lower():
                errors.append(f"Русское слово в alt: {ru_word}")
        
        return errors


