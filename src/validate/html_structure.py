"""
Валидаторы структуры HTML
"""
import re
import logging
from typing import List, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class HTMLStructureValidator:
    """Валидатор структуры HTML"""
    
    def __init__(self, locale: str):
        self.locale = locale
    
    def validate(self, html: str) -> List[str]:
        """Валидация структуры HTML"""
        errors = []
        
        try:
            doc = BeautifulSoup(html, 'html.parser')
            
            # Проверяем порядок секций
            errors.extend(self._validate_section_order(doc))
            
            # Проверяем количество характеристик
            errors.extend(self._validate_specs_count(doc))
            
            # Проверяем количество преимуществ
            errors.extend(self._validate_advantages_count(doc))
            
            # Проверяем позицию hero
            errors.extend(self._validate_hero_position(doc))
            
            # Проверяем note-buy
            errors.extend(self._validate_note_buy(doc))
            
        except Exception as e:
            errors.append(f"Ошибка парсинга HTML: {e}")
        
        return errors
    
    def _validate_section_order(self, doc: BeautifulSoup) -> List[str]:
        """Проверка порядка секций"""
        errors = []
        
        # Ищем основные элементы
        h1 = doc.find('h2', class_='prod-title')
        description_h2 = doc.find('h2', string=re.compile(r'Описание|Опис'))
        note_buy = doc.find('div', class_='note-buy')
        specs_h2 = doc.find('h2', string=re.compile(r'Характеристики'))
        advantages_h2 = doc.find('h2', string=re.compile(r'Преимущества|Переваги'))
        faq_h2 = doc.find('h2', string=re.compile(r'FAQ'))
        hero = doc.find('figure', class_='hero')
        
        # Проверяем наличие элементов
        if not h1:
            errors.append("Отсутствует h2.prod-title")
        if not description_h2:
            errors.append("Отсутствует секция описания")
        if not note_buy:
            errors.append("Отсутствует note-buy")
        if not specs_h2:
            errors.append("Отсутствует секция характеристик")
        if not advantages_h2:
            errors.append("Отсутствует секция преимуществ")
        if not faq_h2:
            errors.append("Отсутствует секция FAQ")
        if not hero:
            errors.append("Отсутствует figure.hero")
        
        # Проверяем порядок: h1 → описание → note-buy → характеристики → преимущества → FAQ → hero
        elements = [h1, description_h2, note_buy, specs_h2, advantages_h2, faq_h2, hero]
        valid_elements = [el for el in elements if el is not None]
        
        if len(valid_elements) >= 2:
            for i in range(len(valid_elements) - 1):
                if valid_elements[i].sourceline > valid_elements[i + 1].sourceline:
                    errors.append(f"Неправильный порядок секций: {valid_elements[i].name} должен идти перед {valid_elements[i + 1].name}")
        
        return errors
    
    def _validate_specs_count(self, doc: BeautifulSoup) -> List[str]:
        """Проверка количества характеристик"""
        errors = []
        
        specs_ul = doc.find('ul', class_='specs')
        if specs_ul:
            specs_count = len(specs_ul.find_all('li'))
            if specs_count > 8:
                errors.append(f"Слишком много характеристик: {specs_count} (максимум 8)")
            elif specs_count == 0:
                errors.append("Отсутствуют характеристики")
        else:
            errors.append("Отсутствует блок характеристик")
        
        return errors
    
    def _validate_advantages_count(self, doc: BeautifulSoup) -> List[str]:
        """Проверка количества преимуществ"""
        errors = []
        
        advantages_div = doc.find('div', class_='cards')
        if advantages_div:
            advantages_count = len(advantages_div.find_all('div', class_='card'))
            if advantages_count > 4:
                errors.append(f"Слишком много преимуществ: {advantages_count} (максимум 4)")
            elif advantages_count < 3:
                errors.append(f"Недостаточно преимуществ: {advantages_count} (минимум 3)")
            
            # Проверяем на заглушки только в h4 (преимущества не должны иметь p)
            for card in advantages_div.find_all('div', class_='card'):
                # Проверяем h4
                h4 = card.find('h4')
                if h4:
                    h4_text = h4.get_text().strip().lower()
                    placeholders = [
                        'дополнительная информация о преимуществе',
                        'додаткова інформація про перевагу',
                        'подробиці',
                        'подробнее',
                        'детальніше',
                        'дополнительная информация',
                        'додаткова інформація',
                        'заглушка',
                        'преимущество',
                        'перевага',
                        'информация',
                        'інформація',
                        'высокое качество',
                        'висока якість',
                        'удобно в использовании',
                        'зручно у використанні',
                        'проверенная временем рецептура',
                        'перевірена часом рецептура'
                    ]
                    if any(placeholder in h4_text for placeholder in placeholders):
                        errors.append("Обнаружены заглушки в заголовках преимуществ")
                
                # Проверяем, что нет тегов p в преимуществах (только h4)
                p = card.find('p')
                if p:
                    errors.append("В преимуществах не должно быть тегов p, только h4")
        else:
            errors.append("Отсутствует блок преимуществ")
        
        return errors
    
    def validate_volume_consistency(self, html_content: str) -> List[str]:
        """Валидация консистентности объёма в описании и характеристиках"""
        errors = []
        if not html_content:
            return errors
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Извлекаем объёмы из описания
        desc_volumes = []
        desc_div = soup.select_one('h2:contains("Описание") + p, h2:contains("Опис") + p')
        if desc_div:
            import re
            desc_text = desc_div.get_text()
            desc_volumes = re.findall(r'(\d+)\s*мл', desc_text)
        
        # Извлекаем объёмы из характеристик
        specs_volumes = []
        specs_ul = soup.select_one('h2:contains("Характеристики") + ul.specs, h2:contains("Характеристики") + ul.specs')
        if specs_ul:
            import re
            specs_text = specs_ul.get_text()
            specs_volumes = re.findall(r'(\d+)\s*мл', specs_text)
        
        # Проверяем консистентность
        if desc_volumes and specs_volumes:
            if set(desc_volumes) != set(specs_volumes):
                errors.append(f"Несоответствие объёма: описание {desc_volumes} vs характеристики {specs_volumes}")
        
        return errors
    
    def validate_volume_consistency_strict(self, html_content: str) -> List[str]:
        """Универсальная валидация консистентности объёма"""
        errors = []
        if not html_content:
            return errors
        
        from src.processing.volume_manager import VolumeManager
        
        # Создаём менеджер объёма для текущей локали
        volume_manager = VolumeManager(self.locale)
        
        # Извлекаем разрешённые объёмы
        allowed_volumes = volume_manager.extract_allowed_volumes(html_content)
        
        if not allowed_volumes:
            return errors
        
        # Валидируем все текстовые блоки
        soup = BeautifulSoup(html_content, 'html.parser')
        all_text = soup.get_text()
        
        # Проверяем консистентность
        volume_errors = volume_manager.validate_volume_consistency(all_text, allowed_volumes)
        
        if volume_errors:
            errors.append(f"КРИТИЧНО: Найдены несоответствия объёма. Блокировка экспорта.")
            errors.append(f"Разрешённые объёмы: {sorted(allowed_volumes)}")
            
            for i, error in enumerate(volume_errors[:3]):  # Показываем первые 3
                errors.append(f"  {i+1}. Найден '{error['found']}', разрешены: {error['allowed']}")
                errors.append(f"      Контекст: ...{error['context']}...")
        
        return errors
    
    def _validate_hero_position(self, doc: BeautifulSoup) -> List[str]:
        """Проверка позиции hero (должен быть последним)"""
        errors = []
        
        hero = doc.find('figure', class_='hero')
        if hero:
            # Проверяем, что hero идет последним в .ds-desc
            ds_desc = doc.find('div', class_='ds-desc')
            if ds_desc:
                # Находим все дочерние элементы ds_desc
                children = list(ds_desc.children)
                hero_index = -1
                for i, child in enumerate(children):
                    if hasattr(child, 'name') and child.name == 'figure' and 'hero' in child.get('class', []):
                        hero_index = i
                        break
                
                if hero_index != -1 and hero_index < len(children) - 1:
                    # Проверяем, что после hero нет других элементов
                    remaining_children = children[hero_index + 1:]
                    non_empty_remaining = [c for c in remaining_children if hasattr(c, 'strip') and c.strip()]
                    if non_empty_remaining:
                        errors.append("figure.hero должен быть последним элементом в .ds-desc")
        else:
            errors.append("Отсутствует figure.hero")
        
        return errors
    
    def _validate_note_buy(self, doc: BeautifulSoup) -> List[str]:
        """Проверка note-buy на корректность структуры"""
        errors = []
        
        note_buy = doc.find('div', class_='note-buy')
        if note_buy:
            text = note_buy.get_text()
            
            # Проверяем наличие ключевых фраз в зависимости от локали
            if self.locale == 'ru':
                # Проверяем корректность фразы
                if 'интернет-магазине' not in text and 'интернет‑магазине' not in text:
                    errors.append("В note-buy отсутствует фраза 'интернет-магазине'")
            else:  # ua
                # Проверяем корректность фразы
                if 'інтернет-магазині' not in text and 'інтернет‑магазині' not in text:
                    errors.append("В note-buy отсутствует фраза 'інтернет-магазині'")
        else:
            errors.append("Отсутствует note-buy")
        
        return errors
