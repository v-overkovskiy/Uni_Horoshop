"""
Извлечение изображений из галереи Swiper с фильтрацией баннеров
"""
import re
import logging
from urllib.parse import urljoin, urlparse, urlunparse, quote, unquote
from bs4 import BeautifulSoup
from typing import Optional, List

logger = logging.getLogger(__name__)

class GalleryPicker:
    """Извлечение главного изображения из галереи Swiper"""
    
    # Паттерны для фильтрации нежелательных изображений
    BAD_PATTERNS = re.compile(r'(sale|promo|banner|action|discount|stock|logo|реклама|акция)', re.IGNORECASE)
    
    # Паттерны для фильтрации миниатюр CDN
    THUMBNAIL_PATTERNS = re.compile(r'/(\d+x\d+|200x|300x|400x|500x|l90nn0|thumb|mini|small)', re.IGNORECASE)
    
    # Поддерживаемые расширения
    SUPPORTED_EXTENSIONS = {'.webp', '.avif', '.jpg', '.jpeg', '.png', '.gif'}
    
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    def pick_best_image(self, html: str) -> Optional[str]:
        """Выбор лучшего изображения из галереи"""
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Приоритет 1: активный слайд Swiper
        active_image = self._get_active_slide_image(soup)
        if active_image:
            # Сначала пытаемся получить оригинальную версию
            original = self._get_original_image(active_image)
            if original and self._is_valid_image(original):
                logger.info(f"Найдена оригинальная версия активного слайда: {original}")
                return self._normalize_url(original)
            elif self._is_valid_image(active_image):
                logger.info(f"Найдено изображение из активного слайда: {active_image}")
                return self._normalize_url(active_image)
        
        # Приоритет 2: первый слайд галереи
        first_image = self._get_first_slide_image(soup)
        if first_image:
            if self._is_valid_image(first_image):
                logger.info(f"Найдено изображение из первого слайда: {first_image}")
                return self._normalize_url(first_image)
            else:
                # Пытаемся получить оригинальную версию
                original = self._get_original_image(first_image)
                if original and self._is_valid_image(original):
                    logger.info(f"Найдена оригинальная версия первого слайда: {original}")
                    return self._normalize_url(original)
        
        # Приоритет 3: og:image
        og_image = self._get_og_image(soup)
        if og_image:
            if self._is_valid_image(og_image):
                logger.info(f"Найдено изображение из og:image: {og_image}")
                return self._normalize_url(og_image)
            else:
                # Пытаемся получить оригинальную версию
                original = self._get_original_image(og_image)
                if original and self._is_valid_image(original):
                    logger.info(f"Найдена оригинальная версия og:image: {original}")
                    return self._normalize_url(original)
        
        logger.warning("Не найдено подходящего изображения")
        return None
    
    def _get_active_slide_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение изображения из активного слайда Swiper"""
        # Ищем активный слайд
        active_slide = soup.select_one('.tmGallery-item.swiper-slide-active .tmGallery-image img[gallery-image]')
        if not active_slide:
            return None
        
        return self._extract_src(active_slide)
    
    def _get_first_slide_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение изображения из первого слайда галереи"""
        # Ищем первый слайд
        first_slide = soup.select_one('.tmGallery-item .tmGallery-image img[gallery-image]')
        if not first_slide:
            return None
        
        return self._extract_src(first_slide)
    
    def _get_og_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечение изображения из og:image"""
        og_meta = soup.find('meta', property='og:image')
        if not og_meta:
            return None
        
        return og_meta.get('content', '').strip()
    
    def _extract_src(self, img_tag) -> Optional[str]:
        """Извлечение src из img тега с приоритетом атрибутов"""
        # Приоритет атрибутов: src -> data-src -> data-origin
        for attr in ['src', 'data-src', 'data-origin']:
            src = img_tag.get(attr)
            if src:
                return src.strip()
        return None
    
    def _get_original_image(self, thumbnail_url: str) -> Optional[str]:
        """Получение оригинальной версии изображения из миниатюры"""
        if not thumbnail_url:
            return None
        
        # Убираем параметры миниатюры из URL
        original_url = thumbnail_url
        
        # Удаляем размеры из пути
        original_url = re.sub(r'/\d+x\d+l90nn0/', '/', original_url)
        original_url = re.sub(r'/\d+x\d+/', '/', original_url)
        original_url = re.sub(r'/\d+x/', '/', original_url)
        
        # Удаляем другие параметры миниатюр
        original_url = re.sub(r'/(thumb|mini|small)/', '/', original_url)
        
        # Если URL изменился, возвращаем оригинальную версию
        if original_url != thumbnail_url:
            logger.debug(f"Преобразован миниатюра {thumbnail_url} -> {original_url}")
            return original_url
        
        return None
    
    def _is_valid_image(self, url: str) -> bool:
        """Проверка валидности изображения"""
        if not url:
            return False
        
        # Проверяем на нежелательные паттерны
        if self.BAD_PATTERNS.search(url):
            logger.debug(f"Изображение отфильтровано по паттерну: {url}")
            return False
        
        # Проверяем на миниатюры CDN
        if self.THUMBNAIL_PATTERNS.search(url):
            logger.debug(f"Изображение отфильтровано как миниатюра: {url}")
            return False
        
        # Проверяем расширение
        parsed = urlparse(url)
        path = parsed.path.lower()
        if not any(path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS):
            logger.debug(f"Неподдерживаемое расширение: {url}")
            return False
        
        return True
    
    def _normalize_url(self, url: str) -> str:
        """Нормализация URL с percent-encoding для кириллицы"""
        if not url:
            return url
        
        try:
            # Если URL относительный, делаем абсолютным
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = urljoin(self.base_url, url)
            elif not url.startswith(('http://', 'https://')):
                url = urljoin(self.base_url, url)
            
            # Парсим URL
            parsed = urlparse(url)
            
            # Нормализуем путь с percent-encoding для кириллицы
            path_segments = parsed.path.split('/')
            normalized_segments = []
            
            for segment in path_segments:
                if segment:
                    # Декодируем и кодируем заново для корректной обработки кириллицы
                    decoded = unquote(segment)
                    encoded = quote(decoded, safe='')
                    normalized_segments.append(encoded)
                else:
                    normalized_segments.append(segment)
            
            # Собираем URL обратно
            normalized_path = '/'.join(normalized_segments)
            normalized_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                normalized_path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            return normalized_url
            
        except Exception as e:
            logger.error(f"Ошибка нормализации URL {url}: {e}")
            return url
