"""
Модель контента для универсального парсера
"""
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class ContentModel:
    """Универсальная модель контента товара"""
    # Основные поля
    h1: str
    description: Dict[str, List[str]]  # {"p1": [3 предложения], "p2": [3 предложения]}
    specs: List[Dict[str, str]]  # [{"name": "Бренд", "value": "BrandName"}]
    advantages: List[str]  # [4-6 преимуществ]
    faq: List[Dict[str, str]]  # [{"q": "вопрос", "a": "ответ"} x 6]
    note_buy: str  # коммерческий текст
    hero: Dict[str, str]  # {"url": "...", "alt": "..."}
    
    # Метаданные
    locale: str
    url: str
    adapter_version: str
    raw_html: Optional[str] = None
    
    def validate_structure(self) -> List[str]:
        """Валидация структуры контента"""
        errors = []
        
        # H1 должен быть один и не пустой
        if not self.h1 or not self.h1.strip():
            errors.append("Пустой заголовок h1")
        
        # Описание должно быть 2 абзаца по 3 предложения
        if not self.description or len(self.description) != 2:
            errors.append("Описание должно содержать 2 абзаца")
        else:
            for i, (key, sentences) in enumerate(self.description.items(), 1):
                if not isinstance(sentences, list) or len(sentences) != 3:
                    errors.append(f"Абзац {i} должен содержать 3 предложения")
        
        # Спецификации минимум 3
        if not self.specs or len(self.specs) < 3:
            errors.append(f"Недостаточно характеристик: {len(self.specs) if self.specs else 0}/3")
        
        # Преимущества 4-6
        if not self.advantages or len(self.advantages) < 4:
            errors.append(f"Недостаточно преимуществ: {len(self.advantages) if self.advantages else 0}/4")
        
        # FAQ ровно 6
        if not self.faq or len(self.faq) != 6:
            errors.append(f"Недостаточно FAQ: {len(self.faq) if self.faq else 0}/6")
        
        # Note-buy не пустой
        if not self.note_buy or not self.note_buy.strip():
            errors.append("Пустой note-buy")
        
        # Hero изображение
        if not self.hero or not self.hero.get('url'):
            errors.append("Отсутствует hero изображение")
        
        return errors
    
    def to_dict(self) -> Dict:
        """Преобразование в словарь"""
        return {
            'h1': self.h1,
            'description': self.description,
            'specs': self.specs,
            'advantages': self.advantages,
            'faq': self.faq,
            'note_buy': self.note_buy,
            'hero': self.hero,
            'locale': self.locale,
            'url': self.url,
            'adapter_version': self.adapter_version
        }


