"""
Генератор описаний товаров с жёстким включением состава набора
"""
import re
import logging
from typing import Dict, Any, List
from src.parsing.bundle_extractor import (
    validate_bundle_components, 
    create_fallback_bundle_text,
    validate_bundle_in_description
)
from src.processing.seo_bundle_optimizer import SEOBundleOptimizer
from src.processing.html_sanitizer import HTMLSanitizer
from src.processing.unified_parser import UnifiedParser

logger = logging.getLogger(__name__)

class DescriptionGenerator:
    """Генерирует описания товаров"""
    
    def __init__(self):
        self.seo_optimizer = SEOBundleOptimizer()
        self.html_sanitizer = HTMLSanitizer()
        self.unified_parser = UnifiedParser()
        self.description_prompt = """
Ты — эксперт по написанию коммерческих описаний для товаров интернет-магазина.

ЗАДАЧА: Создать описание товара ровно из 6-8 предложений, разбитых на 2 абзаца.

СТРУКТУРА:
Абзац 1 (3-4 предложения): Назначение товара, кому подходит, основные свойства.
Абзац 2 (3-4 предложения): Преимущества использования, результаты, практические детали.

ТРЕБОВАНИЯ:
- Без воды — каждое предложение несёт ценность
- Используй конкретные факты из характеристик товара
- Избегай generic-фраз: "качественный продукт", "эффективное средство"
- Описывай конкретные результаты и выгоды для покупателя

ВХОДНЫЕ ДАННЫЕ:
Название: {product_title}
Объём: {volume}
Тип товара: {product_type}
Назначение: {purpose}

ПРИМЕР ВЫВОДА:
"Энзимная пудра Epilax предназначена для профессионального пилинга лица и тела, обеспечивая мягкое отшелушивание отмерших клеток кожи. Она эффективно нормализует секрецию сальных желез и подходит для всех типов кожи, включая чувствительную. Продукт может применяться до депиляции для предотвращения врастания волос.

Пудра обладает антибактериальными свойствами и способствует выравниванию тона кожи. Упаковка весом 50 грамм обеспечивает длительное использование и удобство хранения. Гипоаллергенная формула делает её безопасной для применения в интимных зонах и на чувствительных участках тела."

ГЕНЕРИРУЙ ТОЛЬКО ТЕКСТ ОПИСАНИЯ БЕЗ ДОПОЛНИТЕЛЬНЫХ КОММЕНТАРИЕВ.
"""
    
    def generate_description(self, product_facts: Dict[str, Any], locale: str, bundle_components: List[str] = None) -> str:
        """Генерирует описание товара с жёстким включением состава набора"""
        try:
            # Подготавливаем данные для промпта
            prompt_data = {
                'product_title': product_facts.get('title', ''),
                'volume': product_facts.get('volume', ''),
                'product_type': product_facts.get('product_type', ''),
                'purpose': self._extract_purpose(product_facts)
            }
            
            # Форматируем промпт
            formatted_prompt = self.description_prompt.format(**prompt_data)
            
            # Генерируем базовое описание (2 абзаца, 6 предложений макс)
            base_description = self._create_structured_description(product_facts, locale)
            
            # ЖЁСТКО добавляем состав набора, если есть компоненты
            final_description = self._add_bundle_section(base_description, bundle_components, locale)
            
            # Валидация: проверяем, что все компоненты в описании
            if bundle_components:
                if not validate_bundle_components(bundle_components, final_description):
                    logger.warning("Не все компоненты набора найдены в описании, добавляем фолбэк")
                    fallback_text = create_fallback_bundle_text(bundle_components, locale)
                    final_description += fallback_text
            
            logger.info(f"✅ Сгенерировано описание для {locale}: {len(final_description)} символов")
            return final_description
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации описания: {e}")
            # КРИТИЧНО: НЕ используем fallback - лучше ошибка чем заглушка
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось сгенерировать описание для {product_facts.get('title', 'товар')}: {e}")
    
    def _create_structured_description(self, product_facts: Dict[str, Any], locale: str) -> str:
        """Создает структурированное описание"""
        title = product_facts.get('title', '')
        product_type = product_facts.get('product_type', '')
        volume = product_facts.get('volume', '')
        
        # ✅ УНИВЕРСАЛЬНАЯ генерация описания через LLM - работает для ЛЮБЫХ товаров
        try:
            import httpx
            import os
            
            # Формируем контекст для LLM
            specs_text = ""
            if isinstance(specs, list):
                specs_text = "\n".join([f"- {spec.get('label', '')}: {spec.get('value', '')}" for spec in specs[:5]])
            elif isinstance(specs, dict):
                specs_text = "\n".join([f"- {k}: {v}" for k, v in list(specs.items())[:5]])
            
            locale_name = "украинском" if locale == 'ua' else "русском"
            volume_text = f" Объем: {volume}" if volume else ""
            
            prompt = f"""Создай описание товара на {locale_name} языке:

Название: {title}{volume_text}
Характеристики:
{specs_text}

Требования:
- 2-3 предложения (40-80 слов)
- Конкретное описание на основе характеристик
- БЕЗ фраз: "качественный продукт", "профессиональный уход", "эффективный результат"
- Опиши реальные свойства товара
- БЕЗ пояснений

Формат ответа (ТОЛЬКО описание):
[описание товара]"""

            api_key = os.getenv('OPENAI_API_KEY')
            with httpx.Client() as client:
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 200
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    description_text = result['choices'][0]['message']['content'].strip()
                    logger.info(f"✅ LLM сгенерировал описание для {locale}")
                    return description_text
                else:
                    logger.error(f"❌ LLM API ошибка: {response.status_code}")
                    raise ValueError("LLM API ошибка")
                    
        except Exception as e:
            logger.error(f"❌ Ошибка LLM генерации описания: {e}")
            raise ValueError(f"Не удалось сгенерировать описание: {e}")
    
    def _extract_purpose(self, product_facts: Dict[str, Any]) -> str:
        """✅ УНИВЕРСАЛЬНОЕ извлечение назначения через LLM - работает для ЛЮБЫХ товаров"""
        title = product_facts.get('title', '')
        characteristics = product_facts.get('specs', [])
        
        # ✅ УНИВЕРСАЛЬНЫЙ подход через LLM
        try:
            import httpx
            import os
            
            # Формируем контекст для LLM
            specs_text = ""
            if isinstance(characteristics, list):
                specs_text = "\n".join([f"- {spec.get('label', '')}: {spec.get('value', '')}" for spec in characteristics[:5]])
            elif isinstance(characteristics, dict):
                specs_text = "\n".join([f"- {k}: {v}" for k, v in list(characteristics.items())[:5]])
            
            prompt = f"""Определи назначение товара на основе его названия и характеристик:

Название: {title}
Характеристики:
{specs_text}

Требования:
- Определи ТОЧНОЕ назначение товара
- НЕ используй общие фразы типа "уход за кожей"
- Будь конкретным и точным
- БЕЗ пояснений

Формат ответа (ТОЛЬКО результат):
[конкретное назначение товара]"""

            api_key = os.getenv('OPENAI_API_KEY')
            with httpx.Client() as client:
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 100
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    purpose = result['choices'][0]['message']['content'].strip()
                    logger.info(f"✅ LLM определил назначение: '{title}' → '{purpose}'")
                    return purpose
                else:
                    logger.error(f"❌ LLM API ошибка: {response.status_code}")
                    return "специализированное применение"  # Универсальный fallback
                    
        except Exception as e:
            logger.error(f"❌ Ошибка LLM определения назначения: {e}")
            return "специализированное применение"  # Универсальный fallback
    
    def _add_bundle_section(self, base_description: str, bundle_components: List[str], locale: str) -> str:
        """
        Жёстко добавляет состав набора в описание, не считая его за предложения
        
        Args:
            base_description: Базовое описание (2 абзаца)
            bundle_components: Список компонентов набора
            locale: Локаль ('ru' или 'ua')
            
        Returns:
            HTML с базовым описанием + секция состава набора
        """
        if not bundle_components:
            return base_description
        
        # Заголовок секции состава
        if locale == 'ua':
            bundle_title = "Склад набору"
        else:
            bundle_title = "Состав набора"
        
        # Создаем HTML секцию со списком компонентов
        bundle_section = f"\n<h3>{bundle_title}</h3>\n<ul>"
        for item in bundle_components:
            bundle_section += f"<li>{item}</li>"
        bundle_section += "</ul>"
        
        # Объединяем базовое описание с секцией состава
        # Базовое описание оборачиваем в параграфы
        paragraphs = base_description.split('\n\n')
        html_description = ""
        for paragraph in paragraphs:
            if paragraph.strip():
                html_description += f"<p>{paragraph.strip()}</p>\n"
        
        # Добавляем секцию состава
        final_html = f"<div class=\"description\">\n{html_description}{bundle_section}\n</div>"
        
        logger.info(f"Добавлена секция состава с {len(bundle_components)} компонентами")
        return final_html
    
    def generate_universal_description_with_bundle(self, product_facts: Dict[str, Any], bundle_components: List[str], locale: str = 'ru', ru_bundle_components: List[str] = None) -> str:
        """
        Универсальное генерация описания с жёстким включением состава набора
        
        Args:
            product_facts: Факты о товаре
            bundle_components: Список компонентов набора для текущей локали
            locale: Локаль ('ru' или 'ua')
            ru_bundle_components: Полный список компонентов из RU (для UA фолбэка)
            
        Returns:
            HTML описание с гарантированным включением состава
        """
        try:
            logger.info(f"🔍 DEBUG: bundle_components для {locale}: {bundle_components}")
            logger.info(f"🔍 DEBUG: ru_bundle_components для {locale}: {ru_bundle_components}")
            
            # Для UA: обеспечиваем полный состав набора
            if locale == 'ua' and ru_bundle_components:
                if not bundle_components or len(bundle_components) < len(ru_bundle_components):
                    logger.warning(f"⚠️ UA: Неполный состав ({len(bundle_components) if bundle_components else 0}), используем RU фолбэк ({len(ru_bundle_components)})")
                    bundle_components = ru_bundle_components[:]  # Копируем все компоненты из RU
                    logger.info(f"✅ UA: Фолбэк применен - теперь {len(bundle_components)} компонентов")
                else:
                    logger.info(f"✅ UA: Полный состав найден ({len(bundle_components)} компонентов)")
            
            logger.info(f"🔍 DEBUG: Финальные bundle_components для {locale}: {bundle_components}")
            
            # Генерация базового описания (2 абзаца, лимит 6 предложений)
            base_description = self._create_structured_description(product_facts, locale)
            
            # SEO-оптимизация базового описания
            optimized_description = self.seo_optimizer.optimize_description_for_bundle(
                base_description, product_facts, bundle_components, locale
            )
            
            # Принудительно разбиваем на 2 абзаца
            paragraphs = self._split_into_two_paragraphs(optimized_description)
            
            # Формируем HTML параграфы
            paragraphs_html = ''.join(f'<p>{p}</p>' for p in paragraphs)
            
            # ЖЁСТКО добавляем состав (не считаем за предложения)
            bundle_html = self._create_bundle_section(bundle_components, locale)
            logger.info(f"🔍 DEBUG: bundle_html для {locale}: {bundle_html}")
            
            # Создаем чистый HTML описания
            description_html = f"<div class=\"description\">{paragraphs_html}{bundle_html}</div>"
            final_html = description_html
            logger.info(f"🔍 DEBUG: final_html для {locale}: {final_html[:500]}...")
            
            # Валидация HTML структуры
            if not self.html_sanitizer.validate_html_structure(final_html):
                logger.warning("⚠️ HTML структура некорректна, применяем исправления")
                final_html = self._fix_html_structure(final_html)
            
            # Валидация и фолбэк для гарантии полноты
            final_html = validate_bundle_in_description(final_html, bundle_components, locale)
            
            logger.info(f"✅ Универсальное SEO-оптимизированное описание сгенерировано для {locale}: {len(final_html)} символов")
            logger.info(f"📦 Включено компонентов: {len(bundle_components)}")
            return final_html
            
        except Exception as e:
            logger.error(f"❌ Ошибка универсальной генерации описания: {e}")
            # КРИТИЧНО: НЕ используем fallback - лучше ошибка чем заглушка
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось сгенерировать универсальное описание для {product_facts.get('title', 'товар')}: {e}")
    
    def _create_bundle_section(self, bundle_components: List[str], locale: str) -> str:
        """
        Создает секцию состава набора с универсальной логикой
        
        Args:
            bundle_components: Список компонентов набора
            locale: Локаль ('ru' или 'ua')
            
        Returns:
            HTML секция состава набора
        """
        if not bundle_components:
            return ""
        
        # Заголовок секции
        if locale == 'ua':
            bundle_title = "Склад набору"
        else:
            bundle_title = "Состав набора"
        
        # Для UA переводим компоненты
        if locale == 'ua':
            translated_components = self._translate_bundle_components(bundle_components)
        else:
            translated_components = bundle_components
        
        # Универсальная логика: UL для ≥3 элементов, иначе абзац
        if len(translated_components) >= 3:
            # Создаем список
            bundle_html = f"<h3>{bundle_title}</h3><ul>"
            for item in translated_components:
                bundle_html += f"<li>{item}</li>"  # Все элементы полностью
            bundle_html += "</ul>"
        else:
            # Создаем абзац с перечислением
            bundle_text = ", ".join(translated_components)
            bundle_html = f"<p><strong>{bundle_title}:</strong> {bundle_text}</p>"
        
        logger.info(f"Создана секция состава: {len(translated_components)} компонентов")
        return bundle_html
    
    def _translate_bundle_components(self, components: List[str]) -> List[str]:
        """
        ✅ УНИВЕРСАЛЬНЫЙ перевод компонентов набора через LLM
        БЕЗ словарей - работает для ЛЮБЫХ товаров
        
        Args:
            components: Список компонентов на русском
            
        Returns:
            Список компонентов на украинском
        """
        if not components:
            return []
        
        # ✅ Универсальный перевод через LLM
        try:
            import httpx
            import os
            import asyncio
            
            async def translate_with_llm():
                api_key = os.getenv('OPENAI_API_KEY')
                
                # Формируем промпт для пакетного перевода
                components_text = "\n".join([f"{i+1}. {comp}" for i, comp in enumerate(components)])
                
                prompt = f"""Переведи компоненты набора на украинский язык:
{components_text}

Требования:
- Точный перевод каждого компонента
- Сохрани технические термины и единицы измерения
- Сохрани названия брендов
- БЕЗ пояснений

Формат ответа (ТОЛЬКО список):
1. [переведенный компонент 1]
2. [переведенный компонент 2]
..."""

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.3,
                            "max_tokens": 500
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        response_text = result['choices'][0]['message']['content'].strip()
                        
                        # Парсим ответ
                        lines = [line.strip() for line in response_text.split('\n') if line.strip()]
                        translated = []
                        
                        for line in lines:
                            # Ищем паттерн "1. текст" или просто "текст"
                            if '. ' in line:
                                translated.append(line.split('. ', 1)[1])
                            else:
                                translated.append(line)
                        
                        if len(translated) == len(components):
                            logger.info(f"✅ LLM переведено {len(translated)} компонентов набора на украинский")
                            return translated
                    
                    logger.error(f"❌ LLM API ошибка: {response.status_code}")
                    return components
                    
            # Выполняем асинхронный перевод
            translated = asyncio.run(translate_with_llm())
            return translated
            
        except Exception as e:
            logger.error(f"❌ Ошибка LLM перевода компонентов: {e}")
            # Fallback: возвращаем оригинал
            return components
    
    def _split_into_two_paragraphs(self, text: str) -> List[str]:
        """
        Принудительно разбивает текст на 2 абзаца
        
        Args:
            text: Исходный текст
            
        Returns:
            Список из 2 абзацев (или меньше, если текст короткий)
        """
        if not text or not text.strip():
            return []
        
        # Сначала пробуем разбить по двойным переносам
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if len(paragraphs) >= 2:
            # Если уже есть 2+ абзаца, берем первые 2
            return paragraphs[:2]
        
        # Если один абзац, разбиваем по предложениям
        sentences = re.split(r'[.!?]+', text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 2:
            # Если 1-2 предложения, возвращаем как есть
            return [text.strip()]
        
        # Разбиваем на 2 части примерно поровну
        mid_point = len(sentences) // 2
        
        # Первый абзац
        first_paragraph = '. '.join(sentences[:mid_point])
        if not first_paragraph.endswith('.'):
            first_paragraph += '.'
        
        # Второй абзац
        second_paragraph = '. '.join(sentences[mid_point:])
        if not second_paragraph.endswith('.'):
            second_paragraph += '.'
        
        result = [first_paragraph, second_paragraph]
        logger.info(f"✅ Текст разбит на {len(result)} абзацев")
        return result
    
    def _fix_html_structure(self, html: str) -> str:
        """
        Исправляет HTML структуру
        
        Args:
            html: HTML для исправления
            
        Returns:
            Исправленный HTML
        """
        try:
            # Удаляем вложенные div в p
            html = re.sub(r'<p([^>]*)>([^<]*)<div([^>]*)>([^<]*)</div>([^<]*)</p>', r'<p\1>\2\4\5</p>', html)
            
            # Удаляем лишние div
            html = re.sub(r'<div[^>]*>\s*</div>', '', html)
            
            # Очищаем от script/style
            html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
            
            logger.info("✅ HTML структура исправлена")
            return html
            
        except Exception as e:
            logger.error(f"❌ Ошибка исправления HTML: {e}")
            return html
    
    def _create_fallback_description(self, product_facts: Dict[str, Any], locale: str) -> str:
        """Создает fallback описание при ошибке"""
        title = product_facts.get('title', 'Товар Epilax')
        volume = product_facts.get('volume', '')
        
        if locale == 'ua':
            return f"{title} - це якісний продукт для догляду за шкірою. Він підходить для щоденного використання та забезпечує ефективний результат. Об'єм {volume} дозволяє використовувати продукт протягом тривалого часу."
        else:
            return f"{title} - это качественный продукт для ухода за кожей. Он подходит для ежедневного использования и обеспечивает эффективный результат. Объём {volume} позволяет использовать продукт в течение длительного времени."
    
    def generate_description_with_unified_parser(self, ua_html: str, ru_html: str, locale: str) -> str:
        """
        Генерирует описание товара с использованием данных из UnifiedParser.
        
        Args:
            ua_html: HTML украинской версии
            ru_html: HTML русской версии  
            locale: Локаль ('ru' или 'ua')
            
        Returns:
            str: Сгенерированное описание товара
        """
        try:
            # Парсим полную информацию о продукте
            product_info = self.unified_parser.parse_product_info(ua_html, ru_html)
            
            # Получаем характеристики и состав набора
            specs = product_info.get('specs', {})
            bundle = product_info.get('bundle', [])
            
            # Формируем контекст для генерации
            context_parts = []
            
            # Добавляем характеристики
            if specs:
                specs_text = ', '.join([f"{key}: {value}" for key, value in specs.items()])
                context_parts.append(f"Характеристики: {specs_text}")
            
            # Добавляем состав набора, если есть
            if bundle:
                bundle_text = ', '.join(bundle)
                context_parts.append(f"Состав набора: {bundle_text}")
            
            # Добавляем название и описание
            title = product_info.get(f'title_{locale}', '') or product_info.get('title_ru', '')
            description = product_info.get(f'description_{locale}', '') or product_info.get('description_ru', '')
            
            if title:
                context_parts.append(f"Название: {title}")
            if description:
                context_parts.append(f"Описание: {description}")
            
            context = '\n'.join(context_parts)
            
            # Создаем промпт для LLM
            if locale == 'ua':
                prompt = f"""На основі даних: {context}
Створи опис товару на 2 абзаци (6-8 речень). Використовуй тільки ці дані, нічого не вигадуй.
Абзац 1: Призначення товару, кому підходить, основні властивості.
Абзац 2: Переваги використання, результати, практичні деталі.
"""
            else:
                prompt = f"""На основе данных: {context}
Создай описание товара на 2 абзаца (6-8 предложений). Используй только эти данные, ничего не придумывай.
Абзац 1: Назначение товара, кому подходит, основные свойства.
Абзац 2: Преимущества использования, результаты, практические детали.
"""
            
            # Здесь должен быть вызов LLM API
            # Пока возвращаем базовое описание на основе контекста
            if locale == 'ua':
                return f"Якісний продукт {title} призначений для професійного догляду за шкірою. {description if description else 'Він забезпечує ефективний результат та підходить для щоденного використання.'}"
            else:
                return f"Качественный продукт {title} предназначен для профессионального ухода за кожей. {description if description else 'Он обеспечивает эффективный результат и подходит для ежедневного использования.'}"
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации описания с UnifiedParser: {e}")
            # КРИТИЧНО: НЕ используем fallback - лучше ошибка чем заглушка
            raise ValueError(f"❌ ЗАПРЕЩЕНО: Не удалось сгенерировать описание с UnifiedParser: {e}")
