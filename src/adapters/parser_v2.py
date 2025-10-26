"""
Парсер версии 2 для альтернативных шаблонов
"""
import re
import logging
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from .content_model import ContentModel

logger = logging.getLogger(__name__)

class ParserV2:
    """Парсер версии 2 для альтернативных шаблонов"""
    
    def __init__(self, locale: str):
        self.locale = locale
        self._setup_locale_texts()
    
    def _setup_locale_texts(self):
        """Настройка текстов для локали"""
        if self.locale == 'ru':
            self.texts = {
                'note_buy_prefix': 'В нашем интернет‑магазине можно',
                'note_buy_suffix': 'онлайн, с быстрой доставкой по Украине и гарантией качества.',
                'alt_suffix': '— купить с доставкой по Украине'
            }
        else:  # ua
            self.texts = {
                'note_buy_prefix': 'У нашому інтернет‑магазині можна',
                'note_buy_suffix': 'онлайн зі швидкою доставкою по Україні та гарантією якості.',
                'alt_suffix': '— купити з доставкою по Україні'
            }
    
    def parse(self, html: str, url: str) -> ContentModel:
        """Парсинг HTML в модель контента"""
        soup = BeautifulSoup(html, 'html.parser')
        
        return ContentModel(
            h1=self._extract_h1(soup),
            description=self._extract_description(soup),
            specs=self._extract_specs(soup),
            advantages=self._extract_advantages(soup),
            faq=self._extract_faq(soup),
            note_buy=self._extract_note_buy(soup),
            hero=self._extract_hero(soup),
            locale=self.locale,
            url=url,
            adapter_version='v2',
            raw_html=html
        )
    
    def _extract_h1(self, soup: BeautifulSoup) -> str:
        """Извлечение заголовка h1"""
        # Ищем h1 с классом, содержащим 'title'
        h1 = soup.find('h1', class_=re.compile(r'title', re.IGNORECASE))
        if h1:
            return h1.get_text(strip=True)
        
        # Fallback на обычный h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)
        
        return ""
    
    def _extract_description(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Извлечение описания в 2 абзаца по 3 предложения"""
        # Ищем секцию описания по классу, содержащему 'description'
        desc_section = soup.find('div', class_=re.compile(r'description', re.IGNORECASE))
        if not desc_section:
            return self._create_fallback_description()
        
        # Извлекаем абзацы
        paragraphs = desc_section.find_all('p')
        if len(paragraphs) >= 2:
            p1_sentences = self._split_into_sentences(paragraphs[0].get_text(strip=True))
            p2_sentences = self._split_into_sentences(paragraphs[1].get_text(strip=True))
            
            # Дополняем до 3 предложений если нужно
            while len(p1_sentences) < 3:
                p1_sentences.append(self._get_fallback_sentence())
            while len(p2_sentences) < 3:
                p2_sentences.append(self._get_fallback_sentence())
            
            return {
                'p1': p1_sentences[:3],
                'p2': p2_sentences[:3]
            }
        
        return self._create_fallback_description()
    
    def _extract_specs(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлечение характеристик"""
        specs = []
        
        # Ищем список характеристик по классу, содержащему 'specs'
        specs_list = soup.find('ul', class_=re.compile(r'specs', re.IGNORECASE))
        if not specs_list:
            specs_list = soup.find('div', class_=re.compile(r'specs', re.IGNORECASE))
        
        if specs_list:
            for li in specs_list.find_all('li'):
                text = li.get_text(strip=True)
                if ':' in text:
                    name, value = text.split(':', 1)
                    specs.append({
                        'name': name.strip(),
                        'value': value.strip()
                    })
        
        # Если недостаточно, дополняем
        while len(specs) < 3:
            specs.append(self._get_fallback_spec())
        
        return specs
    
    def _extract_advantages(self, soup: BeautifulSoup) -> List[str]:
        """Извлечение преимуществ"""
        advantages = []
        
        # Ищем список преимуществ по классу, содержащему 'advantages'
        advantages_list = soup.find('ul', class_=re.compile(r'advantages', re.IGNORECASE))
        if not advantages_list:
            advantages_list = soup.find('div', class_=re.compile(r'advantages', re.IGNORECASE))
        
        if advantages_list:
            for li in advantages_list.find_all('li'):
                text = li.get_text(strip=True)
                if text:
                    advantages.append(text)
        
        # Если недостаточно, дополняем
        while len(advantages) < 4:
            advantages.append(self._get_fallback_advantage())
        
        return advantages[:6]  # Максимум 6
    
    def _extract_faq(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлечение FAQ"""
        faq = []
        
        # Ищем FAQ элементы по классу, содержащему 'faq'
        faq_items = soup.find_all('div', class_=re.compile(r'faq', re.IGNORECASE))
        for item in faq_items:
            question_elem = item.find(['h4', 'h5', 'h6'])
            answer_elem = item.find('p')
            
            if question_elem and answer_elem:
                question = question_elem.get_text(strip=True)
                answer = answer_elem.get_text(strip=True)
                
                if question and answer:
                    faq.append({
                        'q': question,
                        'a': answer
                    })
        
        # Если недостаточно, дополняем
        while len(faq) < 6:
            faq.append(self._get_fallback_faq())
        
        return faq[:6]  # Ровно 6
    
    def _extract_note_buy(self, soup: BeautifulSoup) -> str:
        """Извлечение note-buy"""
        # Ищем по классу, содержащему 'note'
        note_buy = soup.find('div', class_=re.compile(r'note', re.IGNORECASE))
        if note_buy:
            return note_buy.get_text(strip=True)
        
        return self._create_fallback_note_buy()
    
    def _extract_hero(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Извлечение hero изображения"""
        # Ищем галерею по классу, содержащему 'gallery'
        gallery_items = soup.find_all('div', class_=re.compile(r'gallery', re.IGNORECASE))
        
        for item in gallery_items:
            img = item.find('img')
            if img:
                src = img.get('src') or img.get('data-src') or img.get('data-origin')
                if src and self._is_valid_image(src):
                    return {
                        'url': self._normalize_url(src),
                        'alt': self._create_alt_text()
                    }
        
        # Fallback на og:image
        og_image = soup.find('meta', property='og:image')
        if og_image:
            src = og_image.get('content')
            if src and self._is_valid_image(src):
                return {
                    'url': self._normalize_url(src),
                    'alt': self._create_alt_text()
                }
        
        return {'url': '', 'alt': ''}
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Разбивка текста на предложения"""
        if not text:
            return []
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _is_valid_image(self, url: str) -> bool:
        """Проверка валидности изображения"""
        if not url:
            return False
        
        bad_patterns = ['sale', 'promo', 'banner', 'action', 'discount', 'stock', 'logo']
        if any(pattern in url.lower() for pattern in bad_patterns):
            return False
        
        valid_extensions = ['.webp', '.avif', '.jpg', '.jpeg', '.png', '.gif']
        return any(url.lower().endswith(ext) for ext in valid_extensions)
    
    def _normalize_url(self, url: str) -> str:
        """Нормализация URL"""
        if not url:
            return url
        
        if url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return 'https://prorazko.com' + url
        elif not url.startswith(('http://', 'https://')):
            return 'https://prorazko.com/' + url
        
        return url
    
    def _create_alt_text(self) -> str:
        """Создание alt текста"""
        return f"Товар {self.texts['alt_suffix']}"
    
    def _create_fallback_description(self) -> Dict[str, List[str]]:
        """❌ ЗАПРЕЩЕНО: Никаких заглушек! Только ошибка"""
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать fallback описание с заглушками!")
        raise ValueError("Не удалось извлечь описание товара из HTML - заглушки запрещены!")
    
    def _get_fallback_sentence(self) -> str:
        """❌ ЗАПРЕЩЕНО: Никаких заглушек! Только ошибка"""
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать fallback предложение!")
        raise ValueError("Не удалось извлечь предложение - заглушки запрещены!")
    
    def _get_fallback_spec(self) -> Dict[str, str]:
        """❌ ЗАПРЕЩЕНО: Никаких заглушек! Только ошибка"""
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать fallback характеристику!")
        raise ValueError("Не удалось извлечь характеристику - заглушки запрещены!")
    
    def _get_fallback_advantage(self) -> str:
        """❌ ЗАПРЕЩЕНО: Никаких заглушек! Только ошибка"""
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать fallback преимущество!")
        raise ValueError("Не удалось извлечь преимущество - заглушки запрещены!")
    
    def _get_fallback_faq(self) -> Dict[str, str]:
        """❌ ЗАПРЕЩЕНО: Никаких заглушек! Только ошибка"""
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать fallback FAQ!")
        raise ValueError("Не удалось извлечь FAQ - заглушки запрещены!")
    
    def _create_fallback_note_buy(self) -> str:
        """❌ ЗАПРЕЩЕНО: Никаких заглушек! Только ошибка"""
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Попытка использовать fallback note-buy!")
        raise ValueError("Не удалось извлечь note-buy - заглушки запрещены!")


