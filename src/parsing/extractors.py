"""
Извлечение данных с страниц товаров по локали
"""
import re
import logging
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ProductData:
    """Структура данных товара"""
    url: str
    locale: str
    title: str
    description: str
    specs: List[Dict[str, str]]
    advantages: List[str]
    faq: List[Dict[str, str]]
    hero_image: Optional[str] = None
    brand: Optional[str] = None
    product_type: Optional[str] = None
    volume: Optional[str] = None

class ProductExtractor:
    """Извлечение данных товара с учетом локали"""
    
    def __init__(self, locale: str):
        self.locale = locale
        self._setup_locale_patterns()
    
    def _setup_locale_patterns(self):
        """Настройка паттернов для конкретной локали"""
        if self.locale == 'ru':
            self.section_patterns = {
                'description': ['Описание', 'Описание товара'],
                'specs': ['Характеристики', 'Спецификация', 'Параметры'],
                'advantages': ['Преимущества', 'Плюсы', 'Особенности'],
                'faq': ['FAQ', 'Часто задаваемые вопросы', 'Вопросы и ответы']
            }
            self.note_buy_patterns = [
                'В нашем интернет-магазине можно',
                'купить в интернет-магазине',
                'с быстрой доставкой'
            ]
        else:  # ua
            self.section_patterns = {
                'description': ['Опис', 'Опис товару'],
                'specs': ['Характеристики', 'Специфікація', 'Параметри'],
                'advantages': ['Переваги', 'Плюси', 'Особливості'],
                'faq': ['FAQ', 'Часті питання', 'Питання та відповіді']
            }
            self.note_buy_patterns = [
                'У нашому інтернет-магазині можна',
                'купити в інтернет-магазині',
                'зі швидкою доставкою'
            ]
    
    def extract(self, html: str, url: str) -> ProductData:
        """Извлечение всех данных товара"""
        if not html:
            return self._create_empty_data(url)
        
        soup = BeautifulSoup(html, 'html.parser')
        
        return ProductData(
            url=url,
            locale=self.locale,
            title=self._extract_title(soup),
            description=self._extract_description(soup),
            specs=self._extract_specs(soup),
            advantages=self._extract_advantages(soup),
            faq=self._extract_faq(soup),
            hero_image=None,  # Будет установлено отдельно
            brand=self._extract_brand(soup),
            product_type=self._extract_product_type(soup),
            volume=self._extract_volume(soup)
        )
    
    def _create_empty_data(self, url: str) -> ProductData:
        """Создание пустой структуры данных"""
        return ProductData(
            url=url,
            locale=self.locale,
            title="",
            description="",
            specs=[],
            advantages=[],
            faq=[]
        )
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлечение заголовка h1"""
        h1 = soup.find('h1', class_='prod-title')
        if h1:
            return h1.get_text(strip=True)
        
        # Fallback на обычный h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return ""
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Извлечение описания товара"""
        # Ищем секцию описания
        desc_section = self._find_section(soup, 'description')
        if not desc_section:
            return ""
        
        # Извлекаем текст из абзацев
        paragraphs = desc_section.find_all('p')
        if paragraphs:
            return ' '.join(p.get_text(strip=True) for p in paragraphs)
        
        # Fallback на весь текст секции
        return desc_section.get_text(strip=True)
    
    def _extract_specs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлечение характеристик"""
        specs_section = self._find_section(soup, 'specs')
        if not specs_section:
            return []
        
        specs = []
        
        # Ищем списки характеристик
        for ul in specs_section.find_all(['ul', 'ol']):
            for li in ul.find_all('li'):
                text = li.get_text(strip=True)
                if ':' in text:
                    name, value = text.split(':', 1)
                    specs.append({
                        'name': name.strip(),
                        'value': value.strip()
                    })
        
        return specs
    
    def _extract_advantages(self, soup: BeautifulSoup) -> List[str]:
        """Извлечение преимуществ"""
        advantages_section = self._find_section(soup, 'advantages')
        if not advantages_section:
            return []
        
        advantages = []
        
        # Ищем списки преимуществ
        for ul in advantages_section.find_all(['ul', 'ol']):
            for li in ul.find_all('li'):
                text = li.get_text(strip=True)
                if text:
                    advantages.append(text)
        
        return advantages
    
    def _extract_faq(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлечение FAQ"""
        faq_section = self._find_section(soup, 'faq')
        if not faq_section:
            return []
        
        faq = []
        
        # Ищем FAQ элементы
        for item in faq_section.find_all(['div', 'li'], class_=re.compile(r'faq|question')):
            question_elem = item.find(['h3', 'h4', 'h5', 'h6', 'strong'])
            answer_elem = item.find(['p', 'div'])
            
            if question_elem and answer_elem:
                question = question_elem.get_text(strip=True)
                answer = answer_elem.get_text(strip=True)
                
                if question and answer:
                    faq.append({
                        'question': question,
                        'answer': answer
                    })
        
        return faq
    
    def _extract_brand(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение бренда"""
        # Ищем в мета-тегах
        brand_meta = soup.find('meta', property='product:brand')
        if brand_meta:
            return brand_meta.get('content', '').strip()
        
        # Ищем в характеристиках
        specs = self._extract_specs(soup)
        for spec in specs:
            if spec['name'].lower() in ['бренд', 'brand', 'бренд:', 'brand:']:
                return spec['value']
        
        return None
    
    def _extract_product_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Определение типа товара по заголовку и характеристикам"""
        title = self._extract_title(soup).lower()
        specs = self._extract_specs(soup)
        
        # Ключевые слова для определения типа
        type_keywords = {
            'свеча': ['свеча', 'свічка', 'candle', 'воск', 'віск'],
            'тоник': ['тоник', 'тонік', 'tonic', 'депиляция', 'депіляція'],
            'молочко': ['молочко', 'молочко', 'мilk', 'spf', 'солнцезащитный'],
            'дезодорант': ['дезодорант', 'дезодорант', 'deodorant', 'стик', 'стік']
        }
        
        for product_type, keywords in type_keywords.items():
            if any(keyword in title for keyword in keywords):
                return product_type
        
        return None
    
    def _extract_volume(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение объема/веса"""
        specs = self._extract_specs(soup)
        
        volume_keywords = ['объем', 'об\'єм', 'объем:', 'об\'єм:', 'вес', 'вага', 'ml', 'мл', 'г', 'грам']
        
        for spec in specs:
            if any(keyword in spec['name'].lower() for keyword in volume_keywords):
                return spec['value']
        
        return None
    
    def _find_section(self, soup: BeautifulSoup, section_type: str) -> Optional[BeautifulSoup]:
        """Поиск секции по типу"""
        patterns = self.section_patterns.get(section_type, [])
        
        # Ищем заголовки секций
        for pattern in patterns:
            # Ищем h2 с текстом
            h2 = soup.find('h2', string=re.compile(pattern, re.IGNORECASE))
            if h2:
                # Возвращаем следующий элемент после заголовка
                next_elem = h2.find_next_sibling()
                if next_elem:
                    return next_elem
                # Или родительский контейнер
                return h2.parent
        
        return None


