"""
Исправленная версия FragmentRenderer без синтаксических ошибок
"""
import json
import logging
from typing import Dict, Any, List
from yattag import Doc

from src.processing.product_image_extractor import ProductImageExtractor
from src.schema.jsonld_faq import FAQJSONLD

logger = logging.getLogger(__name__)

class ProductFragmentRenderer:
    """Рендерит HTML фрагменты товаров по стандартам ProRazko"""
    
    def __init__(self):
        self.templates = {
            'ru': {
                'faq_title': 'FAQ',
                'advantages_title': 'Преимущества',
                'specs_title': 'Характеристики'
            },
            'ua': {
                'faq_title': 'FAQ',
                'advantages_title': 'Переваги', 
                'specs_title': 'Характеристики'
            }
        }
        self.image_extractor = ProductImageExtractor()
    
    def render_product_fragment(self, blocks: Dict[str, Any], locale: str = 'ru') -> str:
        """Рендерит ПОЛНУЮ HTML структуру товара по стандартам ProRazko"""
        try:
            # Валидация входных данных
            self._validate_blocks(blocks, locale)
            
            doc, tag, text, line = Doc().ttl()
            
            with tag('div', klass='ds-desc'):
                # 1. ЗАГОЛОВОК товара (обязательный)
                title = self._get_full_title(blocks, locale)
                with tag('h2', klass='prod-title'):
                    text(title)
                
                # 2. ОПИСАНИЕ (6-8 предложений в 2 абзацах)
                description_html = self._get_full_description(blocks, locale)
                doc.asis(description_html)
                
                # 3. КОММЕРЧЕСКАЯ ФРАЗА с жирным выделением
                note_buy = self._get_full_note_buy(blocks, locale)
                with tag('p', klass='note-buy'):
                    doc.asis(note_buy)
                
                # 4. ХАРАКТЕРИСТИКИ (5-8 пунктов)
                specs = blocks.get('specs', [])
                logger.info(f"🔍 FragmentRenderer {locale}: specs тип: {type(specs)}")
                logger.info(f"🔍 FragmentRenderer {locale}: specs длина: {len(specs) if specs else 0}")
                if specs:
                    logger.info(f"🔍 FragmentRenderer {locale}: specs первый элемент: {specs[0]}")
                    logger.info(f"✅ FragmentRenderer {locale}: РЕНДЕРИМ характеристики")
                else:
                    logger.warning(f"⚠️ FragmentRenderer {locale}: specs ПУСТОЙ - НЕ рендерим блок!")
                
                if specs:
                    logger.info(f"🔧 FragmentRenderer {locale}: НАЧИНАЕМ рендеринг характеристик")
                    with tag('h2'):
                        text(self.templates[locale]['specs_title'])
                        logger.info(f"🔧 FragmentRenderer {locale}: Добавлен заголовок 'Характеристики'")
                    with tag('ul', klass='specs'):
                        logger.info(f"🔧 FragmentRenderer {locale}: Открыт <ul class='specs'>")
                        # Обрабатываем как список или словарь
                        if isinstance(specs, dict):
                            # Если словарь, конвертируем в список
                            specs_list = [{'label': key, 'value': value} for key, value in specs.items()]
                            logger.info(f"🔧 FragmentRenderer {locale}: Конвертировали словарь в список, длина: {len(specs_list)}")
                        else:
                            # Если уже список
                            specs_list = specs
                            logger.info(f"🔧 FragmentRenderer {locale}: Используем список как есть, длина: {len(specs_list)}")
                        
                        for i, spec in enumerate(specs_list[:8]):  # Ограничиваем до 8
                            if isinstance(spec, dict):
                                with tag('li'):
                                    with tag('span', klass='spec-label'):
                                        text(f"{spec.get('label', '')}:")
                                    text(f" {spec.get('value', '')}")
                                logger.info(f"🔧 FragmentRenderer {locale}: Добавлена характеристика {i+1}: {spec.get('label', '')}: {spec.get('value', '')}")
                            else:
                                logger.warning(f"⚠️ FragmentRenderer {locale}: Характеристика {i+1} не словарь: {spec}")
                        
                        logger.info(f"🔧 FragmentRenderer {locale}: Закрываем </ul>")
                
                # 5. ПРЕИМУЩЕСТВА (3-6 карточек)
                advantages = blocks.get('advantages', [])
                if advantages:
                    with tag('h2'):
                        text(self.templates[locale]['advantages_title'])
                    with tag('div', klass='cards'):
                        for advantage in advantages[:6]:  # Ограничиваем до 6
                            if isinstance(advantage, str):
                                with tag('div', klass='card'):
                                    with tag('h4'):
                                        text(advantage)
                            elif isinstance(advantage, dict):
                                with tag('div', klass='card'):
                                    with tag('h4'):
                                        text(advantage.get('title', advantage.get('name', '')))
                
                # 6. FAQ (строго 6 вопросов)
                faq_data = blocks.get('faq', [])
                if faq_data:
                    with tag('h2'):
                        text(self.templates[locale]['faq_title'])
                    with tag('div', klass='faq-section'):
                        # Нормализуем FAQ данные
                        normalized_faq = self._normalize_faq_data(faq_data)
                        for i, item in enumerate(normalized_faq[:6]):  # Ограничиваем до 6
                            if isinstance(item, dict):
                                question = item.get('question', f'Вопрос {i+1}')
                                answer = item.get('answer', f'Ответ {i+1}')
                            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                                question = str(item[0])
                                answer = str(item[1])
                            else:
                                continue
                            
                            with tag('div', klass='faq-item'):
                                with tag('div', klass='faq-question'):
                                    text(question)
                                with tag('div', klass='faq-answer'):
                                    text(answer)
                
                # 7. ИЗОБРАЖЕНИЕ товара (в конце)
                self._render_product_image(doc, tag, line, blocks, locale)

                # 8. JSON-LD структурированные данные
                self._render_json_ld(doc, blocks, locale)
            
            html_result = doc.getvalue()
            
            # Валидация финального HTML
            self._validate_final_html(html_result, blocks, locale)
            
            return html_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка рендеринга фрагмента: {e}")
            return self._render_fallback_fragment(blocks, locale)
    
    def _render_product_image(self, doc, tag, line, blocks: Dict[str, Any], locale: str):
        """Рендерит изображение товара"""
        try:
            # Получить URL товара из blocks или использовать fallback
            product_url = blocks.get('product_url', '')
            
            # Получить данные изображения с использованием ProductImageExtractor
            image_data = self._get_product_image_data(blocks, product_url, locale)
            
            if image_data and image_data.get('url'):
                blocks['_resolved_image_data'] = image_data
                blocks['_resolved_image_url'] = image_data.get('url')
                blocks['image_url'] = image_data.get('url')
                with tag('div', klass='product-photo'):
                    line('img', '', src=image_data['url'], alt=image_data.get('alt', ''))
                logger.info(f"✅ Изображение товара добавлено: {image_data['url']}")
            else:
                logger.warning("⚠️ Данные изображения не найдены")
                
        except Exception as e:
            logger.error(f"❌ Ошибка добавления изображения товара: {e}")
            # Fallback: попробовать использовать старые данные
            try:
                if blocks.get('image_url'):
                    image_url = blocks['image_url']
                    alt_text = self._generate_alt_text(blocks.get('title', ''), locale)
                    with tag('div', klass='product-photo'):
                        line('img', '', src=image_url, alt=alt_text)
            except Exception as fallback_error:
                logger.error(f"❌ Ошибка fallback изображения: {fallback_error}")
                # Не добавляем изображение, если fallback тоже не работает
    
    def _get_product_image_data(self, blocks: Dict[str, Any], product_url: str, locale: str) -> Dict[str, str]:
        """Получает данные изображения товара с использованием ProductImageExtractor"""
        try:
            html_content = blocks.get('html_content', '')
            title = blocks.get('title', '')

            if not product_url and not html_content:
                return {}

            image_data = self.image_extractor.get_product_image_data(
                html_content,
                product_url,
                title,
                locale
            )

            if not image_data or not image_data.get('url'):
                fallback_url = self._generate_image_url_from_product_url(product_url)
                if fallback_url:  # Если fallback вернул не None
                    image_data = {
                        'url': fallback_url,
                        'alt': self._generate_alt_text(title, locale)
                    }
                else:
                    # Изображение не найдено, возвращаем пустой результат
                    logger.warning(f"⚠️ Изображение не найдено для товара: {product_url}")
                    return {}

            return image_data
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных изображения: {e}")
            return {}

    def _render_json_ld(self, doc, blocks: Dict[str, Any], locale: str):
        """Добавляет JSON-LD блоки (только FAQ)."""
        try:
            faq_data = self._normalize_faq_data(blocks.get('faq', []))
            faq_jsonld = FAQJSONLD(locale).build(faq_data, blocks.get('title', ''))

            if faq_jsonld:
                json_string = json.dumps(faq_jsonld, ensure_ascii=False)
                doc.asis(f'<script type="application/ld+json">{json_string}</script>')
        except Exception as e:
            logger.error(f"❌ Ошибка построения JSON-LD: {e}")
    
    def _generate_image_url_from_product_url(self, product_url: str) -> str:
        """Генерирует URL изображения на основе URL товара"""
        # Детальная карта товаров к изображениям
        product_image_map = {
            # Гели для душа
            'hel-dlia-dushu-epilax-kokos-250-ml': 'https://prorazko.com/content/images/gel-coconut-250ml.webp',
            'hel-dlia-dushu-epilax-vetiver-250-ml': 'https://prorazko.com/content/images/gel-vetiver-250ml.webp',
            'hel-dlia-dushu-epilax-aqua-blue-250-ml': 'https://prorazko.com/content/images/gel-aqua-blue-250ml.webp',
            'hel-dlia-dushu-epilax-bilyi-chai-250-ml': 'https://prorazko.com/content/images/gel-white-tea-250ml.webp',
            'hel-dlia-dushu-epilax-morska-sil-250-ml': 'https://prorazko.com/content/images/gel-sea-salt-250ml.webp',
            
            # Пудры
            'pudra-enzymna-epilax-50-hram': 'https://prorazko.com/content/images/powder-enzymatic-50g.webp',
            
            # Флюиды
            'fliuid-vid-vrosloho-volossia-epilax-5-ml-tester': 'https://prorazko.com/content/images/fluid-ingrown-hair-5ml.webp',
            
            # Пенки
            'pinka-dlia-intymnoi-hihiieny-epilax-150-ml': 'https://prorazko.com/content/images/foam-intimate-150ml.webp',
            'pinka-dlia-ochyshchennia-sukhoi-ta-normalnoi-shkiry-epilax-150-ml': 'https://prorazko.com/content/images/foam-dry-skin-150ml.webp',
            'pinka-dlia-ochyshchennia-zhyrnoi-ta-kombinovanoi-shchkiry-epilax-150-ml': 'https://prorazko.com/content/images/foam-oily-skin-150ml.webp',
            
            # Гели для депиляции
            'hel-do-depiliatsii-epilax-z-okholodzhuiuchym-efektom-250-ml': 'https://prorazko.com/content/images/gel-cooling-effect-250ml.webp'
        }
        
        # Извлечь последнюю часть URL (slug)
        url_slug = product_url.replace('https://prorazko.com/', '').rstrip('/')
        
        # Найти точное соответствие
        if url_slug in product_image_map:
            return product_image_map[url_slug]
        
        # Fallback по типу товара
        if 'hel-dlia-dushu' in url_slug:
            return "https://prorazko.com/content/images/gel-for-shower-250ml.webp"
        elif 'pudra' in url_slug:
            return "https://prorazko.com/content/images/powder-50g.webp"
        elif 'fliuid' in url_slug:
            return "https://prorazko.com/content/images/fluid-5ml.webp"
        elif 'pinka' in url_slug:
            return "https://prorazko.com/content/images/foam-150ml.webp"
        elif 'hel-do-depiliatsii' in url_slug:
            return "https://prorazko.com/content/images/gel-pre-depilation-250ml.webp"
        
        # Изображение не найдено - возвращаем None вместо заглушки
        logger.warning(f"⚠️ Изображение не найдено для URL: {product_url}")
        return None
    
    def _generate_alt_text(self, title: str, locale: str) -> str:
        """Генерирует ALT-текст для изображения товара по формуле ProRazko"""
        if locale == 'ua':
            return f'{title} — купити з доставкою по Україні в магазині ProRazko'
        else:
            return f'{title} — купить с доставкой по Украине в магазине ProRazko'
    
    def _validate_blocks(self, blocks: Dict[str, Any], locale: str):
        """Валидирует блоки на полноту данных"""
        required_fields = ['title', 'description', 'note_buy']
        for field in required_fields:
            if not blocks.get(field) or len(str(blocks.get(field)).strip()) < 3:
                raise ValueError(f"Отсутствует обязательное поле {field} для {locale}")
    
    def _get_full_title(self, blocks: Dict[str, Any], locale: str) -> str:
        """Получает полный заголовок товара"""
        title = blocks.get('title', '')
        if not title or len(title.strip()) < 3:
            raise ValueError(f"Пустой заголовок для {locale}")
        return title.strip()
    
    def _get_full_description(self, blocks: Dict[str, Any], locale: str) -> str:
        """Получает полное описание товара"""
        description = blocks.get('description', '')
        if not description:
            raise ValueError(f"Пустое описание для {locale}")
        
        # ЛОГИРОВАНИЕ: Что получили в description
        logger.info(f"🔍 FragmentRenderer получил description типа: {type(description)}")
        logger.info(f"🔍 FragmentRenderer description содержимое: {str(description)[:200]}...")
        
        # Если описание уже содержит div.description, возвращаем как есть
        if '<div class="description">' in str(description):
            logger.warning(f"⚠️ FragmentRenderer: описание уже содержит div.description, возвращаем как есть")
            return str(description).strip()
        
        # ИСПРАВЛЕНИЕ: Обрабатываем описание как список параграфов
        if isinstance(description, list):
            logger.info(f"🔧 FragmentRenderer: обрабатываем список из {len(description)} параграфов")
            # Если это список параграфов, форматируем каждый как <p>
            paragraphs = []
            for i, paragraph in enumerate(description):
                if paragraph and paragraph.strip():
                    paragraphs.append(f'<p>{paragraph.strip()}</p>')
                    logger.info(f"🔧 FragmentRenderer: параграф {i+1}: {paragraph[:50]}...")
            
            if not paragraphs:
                raise ValueError(f"Нет валидных параграфов в описании для {locale}")
            
            # Объединяем параграфы в div.description
            description_html = '\n'.join(paragraphs)
            result = f'<div class="description">\n{description_html}\n</div>'
            logger.info(f"✅ FragmentRenderer: создан HTML с {len(paragraphs)} параграфами")
            return result
        
        # Если описание - строка, проверяем длину
        if len(str(description).strip()) < 10:
            raise ValueError(f"Слишком короткое описание для {locale}")
        
        # Иначе оборачиваем строку в div.description
        return f'<div class="description">{str(description).strip()}</div>'
    
    def _get_full_note_buy(self, blocks: Dict[str, Any], locale: str) -> str:
        """Получает полный note-buy"""
        note_buy = blocks.get('note_buy', '')
        if not note_buy or len(note_buy.strip()) < 5:
            raise ValueError(f"Пустой note_buy для {locale}")
        return note_buy.strip()
    
    def _normalize_faq_data(self, faq_data: List) -> List[Dict[str, str]]:
        """Нормализует FAQ данные к единому формату"""
        normalized = []
        
        for i, item in enumerate(faq_data):
            try:
                if isinstance(item, dict):
                    # Уже правильный формат
                    question = str(item.get('question', '') or item.get('q', ''))
                    answer = str(item.get('answer', '') or item.get('a', ''))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    # Конвертируем кортежи/списки в словари
                    question = str(item[0])
                    answer = str(item[1])
                else:
                    logger.warning(f"⚠️ Неизвестный формат FAQ элемента {i}: {type(item)}")
                    continue
                
                if question and answer and len(question.strip()) > 2 and len(answer.strip()) > 2:
                    normalized.append({
                        'question': question.strip(),
                        'answer': answer.strip()
                    })
                else:
                    logger.warning(f"⚠️ FAQ элемент {i} пустой: question='{question}', answer='{answer}'")
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка нормализации FAQ элемента {i}: {e}")
                continue
        
        return normalized
    
    def _validate_final_html(self, html_result: str, blocks: Dict[str, Any], locale: str):
        """Валидирует финальный HTML на наличие заглушек и обязательных секций"""
        try:
            # Проверяем на наличие заглушек
            if 'error-message' in html_result:
                logger.error(f"❌ HTML содержит заглушку для {locale}")
                raise ValueError(f"HTML содержит заглушку для {locale}")
            
            # Проверяем наличие описания
            if 'description' not in html_result.lower():
                logger.warning(f"⚠️ Отсутствует секция описания для {locale}")
            
            # Проверяем количество FAQ карточек
            faq_cards = html_result.count('<div class="card">')
            if faq_cards < 6:
                logger.warning(f"⚠️ FAQ карточек меньше 6 ({faq_cards}) для {locale}")
            
            logger.info(f"✅ Финальная валидация HTML пройдена для {locale}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации финального HTML: {e}")
            raise
    
    def _render_fallback_fragment(self, blocks: Dict[str, Any], locale: str) -> str:
        """Создает резервный фрагмент при ошибке"""
        doc, tag, text, line = Doc().ttl()
        
        with tag('div', klass='ds-desc'):
            if blocks.get('title'):
                line('h2', blocks['title'], klass='prod-title')
            
            if blocks.get('note_buy'):
                with tag('p', klass='note-buy'):
                    doc.asis(blocks['note_buy'])
            
            with tag('p', klass='error-message'):
                text('Описание товара временно недоступно')
        
        return doc.getvalue()
