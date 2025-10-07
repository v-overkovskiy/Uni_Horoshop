"""
Извлекатель изображений товаров с уникальными URL для каждого продукта
"""
import logging
import re
import requests
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class ProductImageExtractor:
    """Извлекает и генерирует уникальные изображения товаров"""
    
    def __init__(self):
        # КРИТИЧЕСКИЙ СПИСОК ИСКЛЮЧЕНИЙ для блокировки логотипов
        self.logo_blacklist = [
            '87680824850809',      # Конкретный логотип который проходит!
            '200x44',              # Размеры логотипов
            '100x50',
            '150x75',
            '50x50',               # Миниатюры
            '60x25',
            '88x20',
            'logo',
            'brand',
            'header',
            'footer',
            'nav',
            'menu',
            'icon',
            'watermark',
            'stamp',
            'signature',
            'epilax-89712168840516',  # Еще один логотип
        ]
        
        # Карта товаров и их изображений
        self.product_image_map = {
            # Гели для душа
            'gel-dlia-dush': {
                'kokos': 'gel-coconut-250ml.webp',
                'vetiver': 'gel-vetiver-250ml.webp',
                'aqua-blue': 'gel-aqua-blue-250ml.webp',
                'bilyi-chai': 'gel-white-tea-250ml.webp',
                'morska-sil': 'gel-sea-salt-250ml.webp'
            },
            
            # Гели до депиляции
            'hel-do-depiliatsii': {
                'okholodzhuiuchym': 'gel-cooling-effect-250ml.webp',
                'default': 'gel-pre-depilation-250ml.webp'
            },
            
            # Пудры
            'pudra': {
                'enzymna': 'powder-enzymatic-50g.webp',
                'default': 'powder-epilax-50g.webp'
            },
            
            # Пенки
            'pinka': {
                'intymnoi': 'foam-intimate-150ml.webp',
                'zhyrnoi': 'foam-oily-skin-150ml.webp',
                'sukhoi': 'foam-dry-skin-150ml.webp',
                'default': 'foam-cleansing-150ml.webp'
            },
            
            # Флюиды
            'fliuid': {
                'vrosloho-volossia': 'fluid-ingrown-hair-5ml.webp',
                'default': 'fluid-epilax-5ml.webp'
            }
        }

    def is_valid_product_image(self, image_url: str) -> bool:
        """УСИЛЕННАЯ проверка для блокировки логотипов"""
        
        url_lower = image_url.lower()
        
        # ЖЕСТКАЯ БЛОКИРОВКА логотипов
        for blacklist_item in self.logo_blacklist:
            if blacklist_item in url_lower:
                logger.debug(f"🚫 ЗАБЛОКИРОВАНО: {image_url} (найден: {blacklist_item})")
                return False
        
        # Проверка на миниатюры (размеры меньше 200px)
        size_patterns = [
            r'/\d+x\d+[a-z0-9]*/',  # Любые размеры в URL
        ]
        
        for pattern in size_patterns:
            matches = re.findall(pattern, url_lower)
            for match in matches:
                # Извлекаем размеры
                size_match = re.search(r'/(\d+)x(\d+)', match)
                if size_match:
                    width, height = int(size_match.group(1)), int(size_match.group(2))
                    if width < 200 or height < 200:
                        logger.debug(f"🚫 ЗАБЛОКИРОВАНО (миниатюра): {image_url} ({width}x{height})")
                        return False
        
        # ТОЛЬКО качественные изображения товаров
        quality_indicators = [
            'content/images',
            '.webp',
            '.jpg',
            '.png'
        ]
        
        has_quality = any(indicator in url_lower for indicator in quality_indicators)
        
        if has_quality:
            logger.info(f"✅ КАЧЕСТВЕННОЕ ИЗОБРАЖЕНИЕ: {image_url}")
            return True
        
        logger.warning(f"❌ НЕ ПРОШЛО ПРОВЕРКУ: {image_url}")
        return False

    def verify_image_exists(self, image_url: str) -> bool:
        """Проверяет существование изображения по URL"""
        
        try:
            response = requests.head(image_url, timeout=5)
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'image' in content_type:
                    logger.info(f"✅ Изображение доступно: {image_url}")
                    return True
                    
            logger.warning(f"❌ Изображение недоступно: {image_url} (статус: {response.status_code})")
            return False
            
        except Exception as e:
            logger.warning(f"❌ Ошибка проверки изображения {image_url}: {e}")
            return False

    def extract_real_product_image_from_html(self, html_content: str) -> Optional[str]:
        """Извлекает РЕАЛЬНЫЙ URL изображения товара из HTML страницы с высоким разрешением"""

        soup = BeautifulSoup(html_content, 'html.parser')

        image_selectors = [
            'img[src*="/content/images/"]',
            '.product-gallery img',
            '.product__gallery img',
            '.product-image img',
            '.product-photo img',
            'img[alt*="Epilax"]',
            'img[src*=".webp"]',
            'img[src*=".jpg"]',
            'img[src*=".png"]'
        ]

        found_images = []

        for selector in image_selectors:
            try:
                img_elements = soup.select(selector)
                for img in img_elements:
                    src = img.get('src')
                    if not src:
                        continue

                    if src.startswith('/'):
                        src = f"https://prorazko.com{src}"

                    if not src.startswith('http'):
                        src = f"https://prorazko.com/{src.lstrip('/')}"

                    lowered = src.lower()
                    if any(keyword in lowered for keyword in ['content/images', 'epilax', 'product']):
                        # ПРОВЕРЯЕМ ВАЛИДНОСТЬ ИЗОБРАЖЕНИЯ
                        if self.is_valid_product_image(src):
                            found_images.append(src)
                            logger.info(f"✅ Найден ВАЛИДНЫЙ URL изображения: {src}")
                        else:
                            logger.warning(f"🚫 НЕВАЛИДНОЕ изображение: {src}")
            except Exception as selector_error:
                logger.debug(f"❌ Селектор {selector} не сработал: {selector_error}")
                continue

        if not found_images:
            logger.warning("⚠️ Реальное изображение не найдено в HTML")
            return None

        # Теперь пытаемся получить высококачественную версию
        best_image = self._get_high_quality_image(found_images)
        return best_image

    def extract_tmgallery_images_from_js(self, html_content: str) -> Optional[str]:
        """Извлекает изображения из TMGallery JavaScript"""
        
        # Ищем TMGallery JavaScript код
        js_patterns = [
            r'tmGallery.*?images.*?\[(.*?)\]',
            r'gallery.*?images.*?\[(.*?)\]',
            r'productImages.*?\[(.*?)\]',
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                # Ищем URL изображений в найденном коде
                image_urls = re.findall(r'["\']([^"\']*content/images[^"\']*)["\']', match)
                
                for url in image_urls:
                    if self.is_valid_product_image(url):
                        logger.info(f"✅ TMGallery изображение: {url}")
                        return url
        
        return None

    def extract_main_product_image_from_html(self, html_content: str) -> Optional[str]:
        """Ищет ОСНОВНОЕ изображение товара с приоритетом на галерею"""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # ПРИОРИТЕТНЫЕ селекторы для изображений товаров
        priority_selectors = [
            '.tmGallery-image img',           # Основная галерея
            '.tmGallery-main img',            # Главное изображение галереи
            '.product__gallery img',          # Галерея продукта
            '.product-image img',             # Изображение продукта
            '.gallery-item img',              # Элементы галереи
            '.product-photo img',             # Фото продукта
            '.main-image img',                # Главное изображение
        ]
        
        for selector in priority_selectors:
            try:
                images = soup.select(selector)
                logger.info(f"🔍 Селектор '{selector}' найдено изображений: {len(images)}")
                
                for img in images:
                    src = img.get('src')
                    if src:
                        # Преобразовать в абсолютный URL
                        if src.startswith('/'):
                            src = f"https://prorazko.com{src}"
                        
                        logger.info(f"📸 Кандидат: {src}")
                        
                        # ЖЕСТКАЯ ПРОВЕРКА
                        if self.is_valid_product_image(src):
                            logger.info(f"🎯 ВЫБРАНО ИЗОБРАЖЕНИЕ: {src}")
                            return src
                        
            except Exception as e:
                logger.debug(f"❌ Ошибка селектора '{selector}': {e}")
        
        logger.warning(f"🚫 НЕ НАЙДЕНО качественных изображений")
        return None

    def extract_gallery_images_by_priority(self, html_content: str) -> Optional[str]:
        """Резервная логика поиска изображений"""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Найти все изображения в content/images
        all_images = soup.find_all('img', src=True)
        
        candidates = []
        
        for img in all_images:
            src = img.get('src')
            
            if src and 'content/images' in src:
                # Преобразовать в абсолютный URL
                if src.startswith('/'):
                    src = f"https://prorazko.com{src}"
                
                # ЖЕСТКАЯ ПРОВЕРКА каждого кандидата
                if self.is_valid_product_image(src):
                    
                    # Приоритет по размеру в URL (обновленные приоритеты)
                    priority_score = 0
                    
                    if '2048x2048' in src:
                        priority_score = 150  # Максимальный приоритет
                    elif '1800x1800' in src:
                        priority_score = 140  # Очень высокий приоритет
                    elif '1600x1600' in src:
                        priority_score = 130  # Высокий приоритет
                    elif '1280x1280' in src:
                        priority_score = 120  # Хороший приоритет
                    elif '1024x1024' in src:
                        priority_score = 110  # Хороший приоритет
                    elif '800x800' in src:
                        priority_score = 100  # Средний приоритет
                    elif '600x600' in src:
                        priority_score = 90   # Базовый приоритет
                    elif '.webp' in src:
                        priority_score = 50   # Формат WebP
                    elif '.jpg' in src or '.png' in src:
                        priority_score = 30   # Базовый формат
                    
                    candidates.append((src, priority_score))
        
        # Сортировать по приоритету
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        if candidates:
            best_image = candidates[0][0]
            logger.info(f"🏆 ЛУЧШЕЕ ИЗОБРАЖЕНИЕ: {best_image} (приоритет: {candidates[0][1]})")
            return best_image
        
        return None

    def _get_high_quality_image(self, image_urls: List[str]) -> str:
        """Получает изображение высокого качества, проверяя различные варианты разрешения"""
        
        # Берем первое изображение как базовое
        base_url = image_urls[0]
        logger.info(f"🔍 Ищем высококачественную версию для: {base_url}")
        
        # Генерируем варианты высокого качества
        quality_variants = self._generate_quality_variants(base_url)
        
        # Проверяем доступность каждого варианта
        for variant_url in quality_variants:
            if self._check_image_availability(variant_url):
                logger.info(f"✅ Найдено высококачественное изображение: {variant_url}")
                return variant_url
        
        # Если высококачественные варианты недоступны, возвращаем оригинальный
        logger.warning(f"⚠️ Высококачественные варианты недоступны, используем: {base_url}")
        return base_url

    def _generate_quality_variants(self, base_url: str) -> List[str]:
        """Генерирует варианты URL для получения высококачественных изображений"""
        
        variants = []
        
        # Если URL содержит размерную метку (например, /200x44l90nn0/), заменяем её
        if re.search(r'/\d+x\d+[a-z0-9]*/', base_url):
            # Удаляем размерную метку полностью
            no_size_url = re.sub(r'/\d+x\d+[a-z0-9]*/', '/', base_url)
            variants.append(no_size_url)
            
            # Попробуем стандартные высокие разрешения (в порядке приоритета)
            for size in ['2048x2048', '1800x1800', '1600x1600', '1280x1280', '1024x1024', 'original']:
                high_quality_url = re.sub(r'/\d+x\d+[a-z0-9]*/', f'/{size}/', base_url)
                variants.append(high_quality_url)
        
        # Также попробуем добавить размерные метки к URL без них
        if not re.search(r'/\d+x\d+[a-z0-9]*/', base_url):
            for size in ['2048x2048', '1800x1800', '1600x1600', '1280x1280', '1024x1024', '800x800']:
                # Находим позицию перед именем файла
                if '/content/images/' in base_url:
                    parts = base_url.split('/content/images/')
                    if len(parts) == 2:
                        high_quality_url = f"{parts[0]}/content/images/{size}/{parts[1]}"
                        variants.append(high_quality_url)
        
        # Убираем дубликаты, сохраняя порядок
        unique_variants = []
        for variant in variants:
            if variant not in unique_variants:
                unique_variants.append(variant)
        
        logger.info(f"🔍 Сгенерировано {len(unique_variants)} вариантов высокого качества")
        return unique_variants

    def _check_image_availability(self, url: str) -> bool:
        """Проверяет доступность изображения по URL"""
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                # Дополнительная проверка - убеждаемся, что это действительно изображение
                content_type = response.headers.get('content-type', '').lower()
                if any(img_type in content_type for img_type in ['image/', 'jpeg', 'jpg', 'png', 'webp']):
                    logger.debug(f"✅ Изображение доступно: {url} (Content-Type: {content_type})")
                    return True
                else:
                    logger.debug(f"❌ URL не является изображением: {url} (Content-Type: {content_type})")
                    return False
            else:
                logger.debug(f"❌ Изображение недоступно: {url} (Status: {response.status_code})")
                return False
        except Exception as e:
            logger.debug(f"❌ Ошибка проверки изображения {url}: {e}")
            return False

    def generate_fallback_image_url(self, product_url: str) -> str:
        """Возвращает fallback изображение, максимально приближенное к оригиналу"""

        fallback_map = {
            'hel-dlia-dushu': 'https://prorazko.com/content/images/47180_1.webp',
            'pudra-enzymna': 'https://prorazko.com/content/images/47181_1.webp',
            'fliuid-vid-vrosloho': 'https://prorazko.com/content/images/47182_1.webp'
        }

        for slug_part, fallback_url in fallback_map.items():
            if slug_part in product_url:
                logger.info(f"✅ Используем fallback изображение для {slug_part}: {fallback_url}")
                return fallback_url

        # Вместо дефолтного изображения возвращаем None
        logger.warning(f"⚠️ Изображение не найдено для товара: {product_url}")
        return None
    
    def generate_product_image_url(self, product_url: str, product_title: str) -> str:
        """Генерирует URL изображения на основе характеристик товара"""
        
        logger.info(f"🔍 Генерируем изображение для: {product_url}")
        
        # Определить тип товара
        for product_type, variations in self.product_image_map.items():
            if product_type in product_url:
                # Найти конкретный вариант
                for variant_key, image_file in variations.items():
                    if variant_key == 'default':
                        continue
                    if variant_key in product_url:
                        image_url = f"https://prorazko.com/content/images/{image_file}"
                        logger.info(f"✅ Найден специфичный вариант: {variant_key} -> {image_url}")
                        return image_url
                
                # Использовать default вариант
                if 'default' in variations:
                    image_url = f"https://prorazko.com/content/images/{variations['default']}"
                    logger.info(f"✅ Используем default вариант: {image_url}")
                    return image_url
        
        # Fallback изображение
        fallback_url = "https://prorazko.com/content/images/epilax-product-default.webp"
        logger.warning(f"⚠️ Используем fallback изображение: {fallback_url}")
        return fallback_url
    
    def create_product_image_alt(self, product_title: str, locale: str) -> str:
        """Создает правильный ALT-тег для изображения товара"""
        
        if locale == 'ua':
            return f'{product_title} — купити з доставкою по Україні в магазині ProRazko'
        else:  # ru
            return f'{product_title} — купить с доставкой по Украине в магазине ProRazko'
    
    def get_product_image_data(self, html_content: str, product_url: str, product_title: str, locale: str) -> Dict[str, str]:
        """ОПТИМИЗИРОВАННЫЙ метод с приоритетным поиском качественных изображений"""
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🎯 ПОИСК ИЗОБРАЖЕНИЯ ДЛЯ: {product_title}")
        logger.info(f"🌐 URL: {product_url}")
        logger.info(f"{'='*80}")
        
        soup = BeautifulSoup(html_content, 'lxml')
        image_url = None
        
        # ПРИОРИТЕТ 1: Ищем СРАЗУ качественные изображения 600x600, 800x800 и т.д.
        logger.info("🔍 ЭТАП 1: Приоритетный поиск качественных изображений...")
        quality_patterns = ['600x600', '800x800', '1000x1000', '500x500', '1024x1024', '400x400', '300x300']
        
        for pattern in quality_patterns:
            # Ищем в HTML напрямую (быстрее чем перебор)
            quality_images = soup.find_all('img', src=re.compile(f'{pattern}'))
            
            if quality_images:
                for img in quality_images:
                    src = img.get('src')
                    if src and self.is_valid_product_image(src):
                        image_url = self._ensure_absolute_url(src)
                        logger.info(f"✅ ЭТАП 1: Найдено качественное изображение {pattern}: {image_url}")
                        break
                if image_url:
                    break
        
        # ПРИОРИТЕТ 2: Поиск через data-атрибуты и lazy loading
        if not image_url:
            logger.info("🔍 ЭТАП 2: Поиск через data-атрибуты (data-src, data-lazy-src)...")
            data_attrs = ['data-src', 'data-lazy-src', 'data-original', 'data-image']
            
            for attr in data_attrs:
                images_with_data = soup.find_all('img', attrs={attr: True})
                for img in images_with_data:
                    src = img.get(attr)
                    if src and '/content/images/' in src and self.is_valid_product_image(src):
                        image_url = self._ensure_absolute_url(src)
                        logger.info(f"✅ ЭТАП 2: Найдено через {attr}: {image_url}")
                        break
                if image_url:
                    break
        
        # ПРИОРИТЕТ 3: Поиск через специфичные селекторы
        if not image_url:
            logger.info("🔍 ЭТАП 3: Поиск через специфичные селекторы...")
            priority_selectors = [
                'img[src*="600x600"]',
                'img[src*="content/images"]',
                '.product-gallery img',
                '.tmGallery-image img',
                '.tmGallery-main img',
                '.product-photo img',
                '.product-image img',
                '#product-image img'
            ]
            
            for selector in priority_selectors:
                imgs = soup.select(selector)
                for img in imgs:
                    src = img.get('src')
                    if src and not self._is_thumbnail(src) and self.is_valid_product_image(src):
                        image_url = self._ensure_absolute_url(src)
                        logger.info(f"✅ ЭТАП 3: Найдено через селектор {selector}: {image_url}")
                        break
                if image_url:
                    break
        
        # ПРИОРИТЕТ 4: АГРЕССИВНЫЙ поиск ЛЮБЫХ изображений из /content/images/
        if not image_url:
            logger.info("🔍 ЭТАП 4: Агрессивный поиск ВСЕХ изображений из /content/images/...")
            all_images = soup.find_all('img', src=True)
            
            candidates = []
            for img in all_images:
                src = img.get('src', '')
                # Ищем ЛЮБЫЕ изображения из /content/images/
                if src and '/content/images/' in src:
                    # Пропускаем только миниатюры и логотипы
                    if not self._is_thumbnail(src) and self.is_valid_product_image(src):
                        absolute_url = self._ensure_absolute_url(src)
                        # Даём приоритет изображениям с размерами
                        priority = 100 if any(p in src for p in ['600x600', '800x800', '400x400']) else 50
                        candidates.append((absolute_url, priority))
                        logger.info(f"   📸 Кандидат: {absolute_url} (приоритет: {priority})")
            
            if candidates:
                # Сортируем по приоритету и берём лучшее
                candidates.sort(key=lambda x: x[1], reverse=True)
                image_url = candidates[0][0]
                logger.info(f"✅ ЭТАП 4: Найдено изображение из {len(candidates)} кандидатов (приоритет {candidates[0][1]}): {image_url}")
        
        # ПРИОРИТЕТ 5: TMGallery JavaScript (если ничего не найдено)
        if not image_url:
            logger.info("🔍 ЭТАП 5: TMGallery JavaScript...")
            image_url = self.extract_tmgallery_images_from_js(html_content)
            if image_url:
                image_url = self._ensure_absolute_url(image_url)
                logger.info(f"✅ TMGallery УСПЕХ: {image_url}")
        
        # ПРИОРИТЕТ 6: Последний fallback (спецефичные товары с маппингом)
        if not image_url:
            logger.info("🔍 ЭТАП 6: Последний fallback (специфичные товары)...")
            image_url = self.generate_fallback_image_url(product_url)
            if image_url:
                logger.info(f"✅ ЭТАП 6: Используем специфичный fallback: {image_url}")
            else:
                logger.warning(f"⚠️ ЭТАП 6: Fallback тоже не вернул изображение")

        # Создать ALT-тег
        alt_text = self.create_product_image_alt(product_title, locale)
        
        # ФИНАЛЬНАЯ ПРОВЕРКА
        if image_url:
            logger.info(f"🎉 ФИНАЛЬНОЕ ИЗОБРАЖЕНИЕ: {image_url}")
        else:
            logger.warning(f"🚫 ИЗОБРАЖЕНИЕ НЕ НАЙДЕНО - товар будет БЕЗ ФОТО")
            image_url = None
        
        result = {
            'url': image_url,
            'alt': alt_text
        }
        
        logger.info(f"📋 РЕЗУЛЬТАТ: {result}")
        logger.info(f"{'='*80}\n")
        
        return result
    
    def _is_thumbnail(self, src: str) -> bool:
        """Быстрая проверка миниатюр"""
        thumbnail_patterns = [
            '50x50', '60x60', '78x78', '80x80', '100x100',
            '40x', '50x33', '50x25', '50x19', '60x25', '88x20'
        ]
        src_lower = src.lower()
        return any(pattern in src_lower for pattern in thumbnail_patterns)
    
    def _ensure_absolute_url(self, url: str) -> str:
        """Преобразует относительный URL в абсолютный"""
        if url.startswith('/'):
            return f"https://prorazko.com{url}"
        elif not url.startswith('http'):
            return f"https://prorazko.com/{url.lstrip('/')}"
        return url
