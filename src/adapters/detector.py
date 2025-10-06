"""
Детектор структуры страницы для выбора адаптера
"""
import re
import logging
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class StructureDetector:
    """Детектор структуры страницы для выбора версии адаптера"""
    
    def __init__(self):
        self.signatures = {
            'horoshop_pro_razko_v1': {
                'required_selectors': [
                    'h1.product-title'
                ],
                'optional_selectors': [
                    '.tmGallery-item',
                    '.tmGallery-header',
                    '.product-description',
                    '[itemprop="name"]',
                    '[itemprop="description"]'
                ],
                'markers': [
                    'tmGallery',
                    'product-title',
                    'product-description'
                ]
            },
            'v1': {
                'required_selectors': [
                    'h1.product-title',
                    '.product-description',
                    '.tmGallery-rating'
                ],
                'optional_selectors': [
                    '.tmGallery-item',
                    '.tmGallery-header',
                    '[itemprop="description"]',
                    '[itemprop="name"]'
                ],
                'markers': [
                    'tmGallery',
                    'product-title',
                    'product-description'
                ]
            },
            'v2': {
                'required_selectors': [
                    'h1[class*="title"]',
                    '[class*="description"]',
                    '[class*="specs"]',
                    '[class*="advantages"]',
                    '[class*="faq"]'
                ],
                'optional_selectors': [
                    '[class*="gallery"]',
                    '[class*="note"]'
                ],
                'markers': [
                    'product-card',
                    'item-title'
                ]
            }
        }
    
    def detect_version(self, html: str) -> str:
        """Определение версии адаптера по структуре страницы"""
        if not html:
            return 'generic'
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Проверяем Horoshop ProRazko v1
        has_title = bool(soup.select_one("h1.product-title"))
        has_gallery = bool(soup.select_one(".tmGallery-item")) or bool(soup.select_one("meta[property='og:image']"))
        
        if has_title and has_gallery:
            logger.info("Выбран адаптер horoshop_pro_razko_v1")
            return "horoshop_pro_razko_v1"
        
        # Fallback на generic
        logger.warning("Не найдена подходящая версия адаптера, используется generic")
        return 'generic'
    
    def _calculate_score(self, soup: BeautifulSoup, signature: Dict[str, Any]) -> float:
        """Расчет совпадения с сигнатурой"""
        total_checks = 0
        passed_checks = 0
        
        # Проверяем обязательные селекторы
        for selector in signature['required_selectors']:
            total_checks += 1
            if self._check_selector(soup, selector):
                passed_checks += 1
        
        # Проверяем опциональные селекторы (половина веса)
        for selector in signature['optional_selectors']:
            total_checks += 0.5
            if self._check_selector(soup, selector):
                passed_checks += 0.5
        
        # Проверяем маркеры в классах
        for marker in signature['markers']:
            total_checks += 0.3
            if self._check_marker(soup, marker):
                passed_checks += 0.3
        
        if total_checks == 0:
            return 0.0
        
        return passed_checks / total_checks
    
    def _check_selector(self, soup: BeautifulSoup, selector: str) -> bool:
        """Проверка наличия селектора"""
        try:
            elements = soup.select(selector)
            return len(elements) > 0
        except Exception:
            return False
    
    def _check_marker(self, soup: BeautifulSoup, marker: str) -> bool:
        """Проверка наличия маркера в классах"""
        try:
            # Ищем элементы с классом, содержащим маркер
            elements = soup.find_all(class_=re.compile(marker, re.IGNORECASE))
            return len(elements) > 0
        except Exception:
            return False
    
    def get_parser_class(self, version: str):
        """Получение класса парсера по версии"""
        if version == 'horoshop_pro_razko_v1':
            from .horoshop_pro_razko_v1 import HoroshopProRazkoV1
            return HoroshopProRazkoV1
        elif version == 'v1':
            from .parser_v1 import ParserV1
            return ParserV1
        elif version == 'v2':
            from .parser_v2 import ParserV2
            return ParserV2
        else:
            from .parser_generic import ParserGeneric
            return ParserGeneric
