"""
Специализированный адаптер для Horoshop ProRazko v1
"""
import logging
from bs4 import BeautifulSoup
from src.adapters.content_model import ContentModel
from src.parsing.gallery_picker import GalleryPicker
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class HoroshopProRazkoV1:
    """Парсер для Horoshop ProRazko v1"""
    
    def __init__(self, locale: str = 'ua'):
        self.locale = locale
    
    def parse(self, html: str, base_url: str) -> ContentModel:
        """Парсинг HTML страницы"""
        doc = BeautifulSoup(html or "", "html.parser")
        
        # Определяем локаль по URL
        locale = 'ua'  # По умолчанию
        if '/ru/' in base_url:
            locale = 'ru'
        self.locale = locale
        
        # H1 заголовок
        h1 = self._extract_h1(doc)
        
        # Описание
        description = self._extract_description(doc)
        
        # Характеристики
        specs = self._extract_specs(doc)
        
        # Преимущества
        advantages = self._extract_advantages(doc)
        
        # FAQ
        faq = self._extract_faq(doc)
        
        # Note-buy - генерируем с улучшенным шаблоном
        note_buy = self._generate_note_buy(h1)
        
        # Hero изображение
        hero = self._extract_hero(doc, base_url)
        
        return ContentModel(
            h1=h1,
            description=description,
            specs=specs,
            advantages=advantages,
            faq=faq,
            note_buy=note_buy,
            hero=hero,
            locale=self.locale,
            url=base_url,
            adapter_version="horoshop_pro_razko_v1"
        )
    
    def _extract_h1(self, doc: BeautifulSoup) -> str:
        """Извлечение H1 заголовка"""
        # Пробуем разные селекторы для h1
        selectors = [
            'h1.product-title',
            'h1[itemprop="name"]',
            '.product-header h1',
            'h1'
        ]
        
        for selector in selectors:
            h1_elem = doc.select_one(selector)
            if h1_elem and h1_elem.get_text(strip=True):
                title = h1_elem.get_text(strip=True)
                logger.debug(f"Найден h1: {title}")
                return title
        
        logger.warning("h1 не найден")
        return ""
    
    def _extract_description(self, doc: BeautifulSoup) -> Dict[str, List[str]]:
        """Извлечение описания"""
        p1 = []
        p2 = []
        
        # Ищем параграфы в .product-description
        selectors = [
            ".product-description p",
            ".product-description .text p",
            "[itemprop='description'] p",
            ".description p"
        ]
        
        desc_ps = []
        for selector in selectors:
            desc_ps = doc.select(selector)
            if desc_ps:
                logger.debug(f"Найдено {len(desc_ps)} параграфов описания")
                break
        
        if desc_ps:
            if len(desc_ps) >= 1:
                p1 = [desc_ps[0].get_text(" ", strip=True)]
            if len(desc_ps) >= 2:
                p2 = [desc_ps[1].get_text(" ", strip=True)]
        else:
            logger.warning("Описание не найдено")
        
        return {"p1": p1, "p2": p2}
    
    def _extract_specs(self, doc: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлечение характеристик с fallback по заголовку и JSON-LD резервом"""
        from src.parsing.specs_extractor import extract_specs
        
        # Определяем локаль по URL или содержимому
        locale = 'ua'  # По умолчанию UA для Horoshop
        if hasattr(self, 'locale'):
            locale = self.locale
        
        # Используем новый экстрактор
        html_str = str(doc)
        specs = extract_specs(html_str, locale)
        
        logger.debug(f"Извлечено {len(specs)} характеристик для {locale}")
        return specs
    
    def _extract_advantages(self, doc: BeautifulSoup) -> List[str]:
        """Извлечение преимуществ"""
        advantages = []
        
        # Сначала пробуем .advantages li
        for li in doc.select(".advantages li"):
            text = li.get_text(" ", strip=True)
            if text:
                advantages.append(text)
        
        # Если не нашли, пробуем .cards .card
        if not advantages:
            cards = doc.select(".cards .card")
            for card in cards:
                h4 = card.select_one("h4")
                p = card.select_one("p")
                if h4 and p:
                    text = f"{h4.get_text(' ', strip=True)} — {p.get_text(' ', strip=True)}"
                    advantages.append(text)
                elif h4:
                    advantages.append(h4.get_text(" ", strip=True))
                elif p:
                    advantages.append(p.get_text(" ", strip=True))
        
        return advantages
    
    def _extract_faq(self, doc: BeautifulSoup) -> List[Dict[str, str]]:
        """Извлечение FAQ"""
        faqs = []
        for item in doc.select(".faq .faq-item"):
            q_elem = item.select_one("h4")
            a_elem = item.select_one("p")
            
            if q_elem and a_elem:
                q = q_elem.get_text(" ", strip=True)
                a = a_elem.get_text(" ", strip=True)
                if q and a:
                    faqs.append({"q": q, "a": a})
        
        return faqs
    
    def _generate_note_buy(self, h1: str) -> str:
        """Генерация note-buy с улучшенным шаблоном"""
        from src.processing.enhanced_note_buy_generator import EnhancedNoteBuyGenerator
        
        generator = EnhancedNoteBuyGenerator()
        result = generator.generate_enhanced_note_buy(h1, self.locale)
        
        if result and result.get('content'):
            return result['content']
        else:
            # Fallback к простому шаблону
            if self.locale == 'ru':
                return f"В нашем интернет-магазине ProRazko можно <strong>купить {h1.lower()}</strong> с быстрой доставкой по Украине и гарантией качества."
            else:
                return f"У нашому інтернет-магазині ProRazko можна <strong>купити {h1.lower()}</strong> з швидкою доставкою по Україні та гарантією якості."

    def _extract_note_buy(self, doc: BeautifulSoup) -> str:
        """Извлечение note-buy (deprecated - используйте _generate_note_buy)"""
        note_elem = doc.select_one(".note-buy")
        if note_elem:
            return note_elem.get_text(" ", strip=True)
        return ""
    
    def _extract_hero(self, doc: BeautifulSoup, base_url: str) -> Dict[str, str]:
        """Извлечение hero изображения"""
        try:
            # Ищем активный слайд галереи
            active_slide = doc.select_one('.tmGallery-item.swiper-slide-active')
            if active_slide:
                img = active_slide.select_one('.tmGallery-image img[gallery-image]')
                if img:
                    src = img.get('src') or img.get('data-src', '')
                    if src:
                        hero_url = self._normalize_url(src, base_url)
                        if not self._is_thumbnail(hero_url):
                            return {"url": hero_url, "alt": img.get("alt", "").strip()}
            
            # Ищем первый слайд галереи
            first_slide = doc.select_one('.tmGallery-item')
            if first_slide:
                img = first_slide.select_one('.tmGallery-image img[gallery-image]')
                if img:
                    src = img.get('src') or img.get('data-src', '')
                    if src:
                        hero_url = self._normalize_url(src, base_url)
                        if not self._is_thumbnail(hero_url):
                            return {"url": hero_url, "alt": img.get("alt", "").strip()}
            
            # Fallback на og:image
            og_image = doc.select_one('meta[property="og:image"]')
            if og_image:
                src = og_image.get('content', '')
                if src:
                    hero_url = self._normalize_url(src, base_url)
                    if not self._is_thumbnail(hero_url):
                        return {"url": hero_url, "alt": ""}
            
            return {"url": "", "alt": ""}
        except Exception as e:
            logger.warning(f"Не удалось извлечь hero изображение: {e}")
            return {"url": "", "alt": ""}
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """Нормализация URL"""
        from urllib.parse import urljoin
        return urljoin(base_url, url)
    
    def _is_thumbnail(self, url: str) -> bool:
        """Проверка, является ли URL миниатюрой"""
        import re
        thumbnail_patterns = [
            r'/\d{2,4}x\d{2,4}/',  # /200x200/, /300x300/
            r'/\d{2,4}x/',         # /200x/, /300x/
            r'/l\d{2}n/',          # /l90n/, /l120n/
            r'/l\d{2}nn\d/',       # /l90nn0/, /l120nn1/
            r'/\d{2,4}x\d{2,4}l\d{2}nn\d/',  # /200x44l90nn0/
        ]
        
        for pattern in thumbnail_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.warning(f"Обнаружена миниатюра: {url}")
                return True
        return False
