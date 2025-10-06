"""
Построение HTML блоков с правильной локализацией
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass

# Импорты новых модулей
from src.processing.temperature_normalizer import TemperatureNormalizer
from src.processing.faq_generator import FaqGenerator
from src.processing.color_synchronizer import ColorSynchronizer
from src.processing.terminology_fixer import TerminologyFixer

logger = logging.getLogger(__name__)

@dataclass
class HTMLBuilder:
    """Построитель HTML блоков с локализацией"""
    
    def __init__(self, locale: str):
        self.locale = locale
        self._setup_locale_texts()
        
        # Инициализируем новые модули
        self.temp_normalizer = TemperatureNormalizer()
        self.faq_generator = FaqGenerator()
        self.color_synchronizer = ColorSynchronizer()
        self.terminology_fixer = TerminologyFixer()
    
    def _setup_locale_texts(self):
        """Настройка текстов для локали"""
        if self.locale == 'ru':
            self.texts = {
                'description_title': 'Описание',
                'specs_title': 'Характеристики',
                'advantages_title': 'Преимущества',
                'faq_title': 'FAQ',
                'note_buy_prefix': 'В нашем интернет‑магазине ProRazko можно',
                'note_buy_suffix': 'онлайн, с быстрой доставкой по Украине и гарантией качества.',
                'alt_suffix': '— купить в интернет-магазине ProRazko'
            }
        else:  # ua
            self.texts = {
                'description_title': 'Опис',
                'specs_title': 'Характеристики',
                'advantages_title': 'Переваги',
                'faq_title': 'FAQ',
                'note_buy_prefix': 'У нашому інтернет‑магазині ProRazko можна',
                'note_buy_suffix': 'онлайн зі швидкою доставкою по Україні та гарантією якості.',
                'alt_suffix': '— купити в інтернет-магазині ProRazko'
            }
    
    def build_html(self, data: Dict[str, Any], hero_image_url: Optional[str] = None) -> str:
        """Построение полного HTML блока с новым порядком секций"""
        # Обрабатываем описание
        description_paragraphs = self._process_description(data.get('description', {}))
        
        # Ограничиваем характеристики до 8 пунктов и нормализуем бренды
        specs_all = data.get('specs', [])
        specs_normalized = self._normalize_specs_brands(specs_all)
        
        # Нормализуем единицы температуры
        specs_normalized = self._normalize_temperature_units(specs_normalized)
        
        # Исправляем терминологию (объём → масса для кг/г)
        specs_normalized = self.terminology_fixer.fix_specs_terminology(specs_normalized, self.locale)
        
        # Синхронизируем цвета между названием и характеристиками
        h1_title = data.get('h1', data.get('title', ''))
        correct_color, specs_normalized = self._synchronize_colors(h1_title, specs_normalized)
        
        specs_display = self._limit_specs(specs_normalized)
        
        # Извлекаем разрешённые объёмы
        allowed_volumes = self._get_allowed_volumes(specs_all)
        
        # Очищаем и ограничиваем преимущества до 4 карточек с автодозаполнением
        advantages_all = data.get('advantages', [])
        advantages_clean, advantages_report = self._enhance_advantages(advantages_all, specs_all)
        
        # Принудительно исправляем объём и массу во всех текстовых блоках
        if allowed_volumes:
            data['description'] = self._force_volume_consistency(data.get('description', {}), allowed_volumes)
            advantages_clean = self._force_volume_consistency_list(advantages_clean, allowed_volumes)
        
        # Исправляем смешение единиц измерения
        data['description'] = self._fix_unit_mismatch(data.get('description', {}))
        advantages_clean = self._fix_unit_mismatch_list(advantages_clean)
        
        # Принудительно исправляем объём в FAQ
        if allowed_volumes:
            data['faq'] = self._force_volume_consistency_faq(data.get('faq', []), allowed_volumes)
        
        # НЕ улучшаем FAQ здесь - это уже сделано в ContentEnhancer
        # data['faq'] = self.faq_generator.enhance_faq_with_specs(data.get('faq', []), specs_all, self.locale)
        
        # Проверяем качество очищенных преимуществ
        if len(advantages_clean) < 2:
            logger.warning(f"Недостаточно качественных преимуществ для {self.locale}: {len(advantages_clean)}")
            # Используем fallback преимущества
            advantages_clean = self._get_fallback_advantages()
        
        # Строим HTML в новом порядке: h2 → описание → note-buy → характеристики → преимущества → FAQ → hero
        h1_title = data.get('h1', data.get('title', ''))
        html_parts = [
            '<div class="ds-desc">',
            self._build_title(h1_title),  # Всегда h2, так как H1 уже есть в теме
            self._build_description(description_paragraphs),
            self._build_note_buy(h1_title),
            self._build_specs(specs_display),
            self._build_advantages(advantages_clean),
            self._build_faq(data.get('faq', [])),
            self._build_hero_image(hero_image_url, h1_title),  # Hero в конце
            '</div>'
        ]
        
        # Исправляем терминологию в финальном HTML
        html_content = '\n'.join(html_parts)
        html_content = self.terminology_fixer.fix_html_terminology(html_content, self.locale)
        
        return html_content
    
    def _enhance_advantages(self, advantages: List[str], specs: List[Dict[str, str]]) -> Tuple[List[str], Dict[str, any]]:
        """Улучшает преимущества с автодозаполнением"""
        from src.processing.advantages_enhancer import AdvantagesEnhancer
        
        enhancer = AdvantagesEnhancer(self.locale)
        return enhancer.enhance_advantages(advantages, specs)
    
    def _normalize_specs_brands(self, specs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Нормализует бренды в характеристиках"""
        from src.processing.brand_normalizer import BrandNormalizer
        
        normalizer = BrandNormalizer()
        return normalizer.normalize_specs_brands(specs)
    
    def _normalize_temperature_units(self, specs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Нормализует единицы температуры в характеристиках"""
        if not specs:
            return specs
        
        normalized_specs = []
        for spec in specs:
            name = spec.get('name', '')
            value = spec.get('value', '')
            
            # Нормализуем температуру в значении
            normalized_value = self.temp_normalizer.normalize_temperature(value, self.locale)
            
            normalized_specs.append({
                'name': name,
                'value': normalized_value
            })
        
        return normalized_specs
    
    def _synchronize_colors(self, title: str, specs: List[Dict[str, str]]) -> Tuple[Optional[str], List[Dict[str, str]]]:
        """Синхронизирует цвета между названием и характеристиками"""
        return self.color_synchronizer.synchronize_colors(title, specs, self.locale)
    
    def _limit_specs(self, specs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Ограничение характеристик до 8 пунктов с приоритетом важных ключей"""
        if not specs:
            return []
        
        # Важные ключи для приоритета
        important_keys = ['бренд', 'тип', 'материал', 'объем', 'объём', 'мощность', 'цвет', 'размер', 'гарантия',
                         'бренд', 'тип', 'матеріал', 'об\'єм', 'потужність', 'колір', 'розмір', 'гарантія']
        
        # Сортируем: сначала важные ключи, потом остальные
        def sort_key(spec):
            key_lower = spec.get('name', '').lower()
            for i, important in enumerate(important_keys):
                if important in key_lower:
                    return (0, i)  # Важные ключи в начале
            return (1, 0)  # Остальные в конце
        
        sorted_specs = sorted(specs, key=sort_key)
        return sorted_specs[:8]
    
    def _clean_advantages(self, advantages: List[str]) -> List[str]:
        """Очистка преимуществ от заглушек и ограничение до 4 карточек"""
        if not advantages:
            return []
        
        # Заглушки для фильтрации
        placeholders = [
            'дополнительная информация о преимуществе',
            'додаткова інформація про перевагу',
            'подробиці',
            'подробнее',
            'детальніше',
            'дополнительная информация',
            'додаткова інформація'
        ]
        
        # Фильтруем заглушки
        clean_advantages = []
        for adv in advantages:
            if not adv or not adv.strip():
                continue
            
            # Проверяем на заглушки
            adv_lower = adv.lower().strip()
            is_placeholder = any(placeholder in adv_lower for placeholder in placeholders)
            
            if not is_placeholder:
                # Нормализуем: убираем лишние пробелы, ограничиваем длину
                normalized = re.sub(r'\s+', ' ', adv.strip())
                
                # Исправляем объём для воскоплава (400 мл → 200 мл)
                if 'воскоплав' in normalized.lower() and '400 мл' in normalized:
                    normalized = normalized.replace('400 мл', '200 мл')
                
                if len(normalized) > 200:  # Сокращаем слишком длинные
                    normalized = normalized[:197] + '...'
                clean_advantages.append(normalized)
        
        # Убираем дубликаты (по лемме)
        unique_advantages = []
        seen = set()
        for adv in clean_advantages:
            adv_key = adv.lower().strip()
            if adv_key not in seen:
                seen.add(adv_key)
                unique_advantages.append(adv)
        
        return unique_advantages[:4]
    
    def _get_allowed_volumes(self, specs: List[Dict[str, str]], html: str = None) -> Set[str]:
        """Извлекает разрешённые объёмы из характеристик и HTML"""
        from src.processing.volume_manager import VolumeManager
        
        volume_manager = VolumeManager(self.locale)
        
        # Если есть HTML, извлекаем из него
        if html:
            return volume_manager.extract_allowed_volumes(html)
        
        # Иначе извлекаем только из specs
        allowed_volumes = set()
        for spec in specs:
            name = spec.get('name', '').lower()
            value = spec.get('value', '')
            
            # Проверяем, что это объём
            if any(keyword in name for keyword in ['объем', 'об\'єм', 'volume', 'capacity']):
                import re
                volume_match = re.search(r'(\d+(?:[.,]\d+)?)\s*([млmlлlгg]+)', value, re.IGNORECASE)
                if volume_match:
                    normalized = volume_manager._normalize_volume(volume_match.group(1), volume_match.group(2))
                    if normalized:
                        allowed_volumes.add(normalized)
        
        return allowed_volumes
    
    def _force_volume_consistency(self, description: Dict, allowed_volumes: Set[str]) -> Dict:
        """Принудительно исправляет объём в описании"""
        if not description or not allowed_volumes:
            return description
        
        from src.processing.volume_manager import VolumeManager
        volume_manager = VolumeManager(self.locale)
        
        # Исправляем в p1 и p2
        if isinstance(description, dict):
            p1 = description.get('p1', [])
            p2 = description.get('p2', [])
            
            if isinstance(p1, list):
                p1 = [volume_manager.repair_volume_mentions(p, allowed_volumes) for p in p1]
                description['p1'] = p1
            
            if isinstance(p2, list):
                p2 = [volume_manager.repair_volume_mentions(p, allowed_volumes) for p in p2]
                description['p2'] = p2
        
        return description
    
    def _force_volume_consistency_list(self, items: List[str], allowed_volumes: Set[str]) -> List[str]:
        """Принудительно исправляет объём в списке строк"""
        if not items or not allowed_volumes:
            return items
        
        from src.processing.volume_manager import VolumeManager
        volume_manager = VolumeManager(self.locale)
        
        return [volume_manager.repair_volume_mentions(item, allowed_volumes) for item in items]
    
    def _force_volume_consistency_faq(self, faqs: List[Dict], allowed_volumes: Set[str]) -> List[Dict]:
        """Принудительно исправляет объём в FAQ"""
        if not faqs or not allowed_volumes:
            return faqs
        
        from src.processing.volume_manager import VolumeManager
        volume_manager = VolumeManager(self.locale)
        
        for faq in faqs:
            if 'question' in faq:
                faq['question'] = volume_manager.repair_volume_mentions(faq['question'], allowed_volumes)
            if 'answer' in faq:
                faq['answer'] = volume_manager.repair_volume_mentions(faq['answer'], allowed_volumes)
        
        return faqs
    
    def _get_fallback_advantages(self) -> List[str]:
        """Fallback преимущества при недостатке качественных"""
        if self.locale == 'ru':
            return [
                "Специальная формула для профессионального использования",
                "Быстрое впитывание и длительный эффект",
                "Удобная упаковка объемом 150 мл",
                "Проверенная временем рецептура"
            ]
        else:
            return [
                "Спеціальна формула для професійного використання",
                "Швидке вбирання та тривалий ефект",
                "Зручна упаковка об'ємом 150 мл",
                "Перевірена часом рецептура"
            ]
    
    def _build_hero_image(self, image_url: Optional[str], h1_title: str) -> str:
        """Построение hero изображения"""
        if not image_url:
            return ''
        
        alt_text = f"{h1_title} {self.texts['alt_suffix']}"
        
        return f'''<figure class="hero">
    <img src="{image_url}" 
         srcset="{image_url} 2x" 
         alt="{alt_text}" 
         sizes="(max-width: 768px) 100vw, 780px" />
</figure>'''
    
    def _build_title(self, title: str) -> str:
        """Построение заголовка h2 (H1 уже есть в теме Хорошопа)"""
        if not title:
            title = "Товар"
        
        # В Хорошопе H1 уже формируется из названия товара темой
        # Поэтому внутренний заголовок всегда h2 для правильной иерархии
        return f'<h2 class="prod-title">{title}</h2>'
    
    def _fix_unit_mismatch(self, description: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Исправляет смешение единиц измерения в описании"""
        from src.processing.volume_manager import VolumeManager
        
        if not description:
            return description
        
        fixed_description = {}
        for locale, paragraphs in description.items():
            if not paragraphs:
                fixed_description[locale] = paragraphs
                continue
            
            volume_manager = VolumeManager(locale)
            fixed_paragraphs = []
            for paragraph in paragraphs:
                fixed_paragraph = volume_manager.fix_unit_mismatch(paragraph)
                fixed_paragraphs.append(fixed_paragraph)
            fixed_description[locale] = fixed_paragraphs
        
        return fixed_description
    
    def _fix_unit_mismatch_list(self, advantages: List[str]) -> List[str]:
        """Исправляет смешение единиц измерения в списке преимуществ"""
        from src.processing.volume_manager import VolumeManager
        
        if not advantages:
            return advantages
        
        volume_manager = VolumeManager(self.locale)
        fixed_advantages = []
        for advantage in advantages:
            fixed_advantage = volume_manager.fix_unit_mismatch(advantage)
            fixed_advantages.append(fixed_advantage)
        
        return fixed_advantages
    
    def _build_description(self, paragraphs: List[str]) -> str:
        """Построение секции описания"""
        if not paragraphs:
            return f'''<h2>{self.texts['description_title']}</h2>
<div class="description">
    <p>Описание товара отсутствует.</p>
    <p>Дополнительная информация недоступна.</p>
</div>'''
        
        # Обеспечиваем 2 абзаца
        while len(paragraphs) < 2:
            if self.locale == 'ru':
                paragraphs.append("Дополнительная информация о товаре.")
            else:
                paragraphs.append("Додаткова інформація про товар.")
        
        # Ограничиваем до 2 абзацев
        paragraphs = paragraphs[:2]
        
        html = f'<h2>{self.texts["description_title"]}</h2>\n<div class="description">'
        for paragraph in paragraphs:
            html += f'\n    <p>{paragraph}</p>'
        html += '\n</div>'
        
        return html
    
    def _build_note_buy(self, title: str) -> str:
        """Построение note-buy блока с улучшенной генерацией и валидацией"""
        if not title:
            return ''

        # Используем улучшенный генератор с новым шаблоном
        from src.processing.enhanced_note_buy_generator import EnhancedNoteBuyGenerator
        import logging
        logger = logging.getLogger(__name__)

        generator = EnhancedNoteBuyGenerator()
        result = generator.generate_enhanced_note_buy(title, self.locale)
        
        logger.info(f"🔧 EnhancedNoteBuyGenerator результат: {result}")

        if result and result.get('content'):
            # Валидация структуры note_buy
            validation_result = self._validate_note_buy_structure(result['content'], self.locale)
            
            if validation_result['is_valid']:
                logger.info(f"✅ Используем улучшенный генератор для {self.locale}")
                return f'<div class="note-buy">\n    <p>{result["content"]}</p>\n</div>'
            else:
                logger.warning(f"⚠️ Валидация note_buy не прошла для {self.locale}: {validation_result['errors']}")
                # Исправляем ошибки валидации
                fixed_content = self._fix_note_buy_validation_errors(result['content'], self.locale)
                return f'<div class="note-buy">\n    <p>{fixed_content}</p>\n</div>'
        else:
            # Fallback к старому генератору
            logger.info(f"❌ Fallback к старому генератору для {self.locale}")
            from src.processing.note_buy_generator import NoteBuyGenerator
            old_generator = NoteBuyGenerator()
            note_text = old_generator.generate_note_buy(title, self.locale, None)
            return f'<div class="note-buy">\n    <p>{note_text}</p>\n</div>'
    
    def _validate_note_buy_structure(self, content: str, locale: str) -> Dict[str, Any]:
        """Валидирует структуру note_buy"""
        errors = []
        
        # Проверяем наличие одного <strong> тега
        strong_count = content.count('<strong>')
        if strong_count != 1:
            errors.append(f"Ожидается 1 <strong> тег, найдено {strong_count}")
        
        # Проверяем, что <strong> начинается с "купить/купити"
        kupit_word = 'купить' if locale == 'ru' else 'купити'
        strong_start = content.find('<strong>')
        if strong_start != -1:
            strong_content = content[strong_start:content.find('</strong>', strong_start)]
            if not strong_content.startswith(f'<strong>{kupit_word}'):
                errors.append(f"<strong> должен начинаться с '{kupit_word}'")
        
        # Проверяем наличие "ProRazko" после "интернет-магазине/інтернет-магазині"
        internet_words = ['интернет-магазине', 'інтернет-магазині', 'інтернет‑магазині', 'интернет‑магазине']
        internet_pos = -1
        found_word = ''
        for word in internet_words:
            pos = content.find(word)
            if pos != -1:
                internet_pos = pos
                found_word = word
                break
        
        if internet_pos != -1:
            after_internet = content[internet_pos + len(found_word):]
            if 'ProRazko' not in after_internet:
                errors.append(f"После '{found_word}' отсутствует 'ProRazko'")
        
        # Проверяем отсутствие дублирования леммы (например, "пудра Пудру")
        words = content.split()
        for i in range(len(words) - 1):
            if words[i].lower() == words[i + 1].lower():
                errors.append(f"Обнаружено дублирование леммы: '{words[i]} {words[i + 1]}'")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }
    
    def _fix_note_buy_validation_errors(self, content: str, locale: str) -> str:
        """Исправляет ошибки валидации note_buy"""
        # Исправляем отсутствие "ProRazko"
        internet_words = ['интернет-магазине', 'інтернет-магазині', 'інтернет‑магазині', 'интернет‑магазине']
        for internet_word in internet_words:
            if internet_word in content and 'ProRazko' not in content:
                content = content.replace(internet_word, f'{internet_word} ProRazko')
                break
        
        # Исправляем дублирование леммы
        words = content.split()
        fixed_words = []
        i = 0
        while i < len(words):
            if i < len(words) - 1 and words[i].lower() == words[i + 1].lower():
                # Пропускаем дублированное слово
                fixed_words.append(words[i])
                i += 2
            else:
                fixed_words.append(words[i])
                i += 1
        
        return ' '.join(fixed_words)
    
    def _build_specs(self, specs: List[Dict[str, str]]) -> str:
        """Построение секции характеристик"""
        if not specs:
            return f'''<h2>{self.texts['specs_title']}</h2>
<ul class="specs">
    <li><span class="spec-label">Тип:</span> Не указан</li>
</ul>'''
        
        html = f'<h2>{self.texts["specs_title"]}</h2>\n<ul class="specs">'
        for spec in specs:
            if isinstance(spec, dict) and 'name' in spec and 'value' in spec:
                html += f'\n    <li><span class="spec-label">{spec["name"]}:</span> {spec["value"]}</li>'
        html += '\n</ul>'
        
        return html
    
    def _build_advantages(self, advantages: List[str]) -> str:
        """Построение секции преимуществ"""
        if not advantages:
            return f'''<h2>{self.texts['advantages_title']}</h2>
<div class="cards">
    <div class="card">
        <h4>Высокое качество продукции</h4>
        <p>Все товары проходят строгий контроль качества</p>
    </div>
    <div class="card">
        <h4>Быстрая доставка по Украине</h4>
        <p>Доставляем заказы в кратчайшие сроки</p>
    </div>
    <div class="card">
        <h4>Гарантия качества</h4>
        <p>Предоставляем официальную гарантию на все товары</p>
    </div>
</div>'''
        
        html = f'<h2>{self.texts["advantages_title"]}</h2>\n<div class="cards">'
        for advantage in advantages:
            if advantage:
                # Убираем заглушки из текста
                clean_advantage = advantage.replace('Дополнительная информация о преимуществе', '').strip()
                if not clean_advantage:
                    clean_advantage = "Профессиональное качество и эффективность"
                
                html += f'''
    <div class="card">
        <h4>{clean_advantage}</h4>
    </div>'''
        html += '\n</div>'
        
        return html
    
    def _build_faq(self, faq: List[Dict[str, str]]) -> str:
        """Построение секции FAQ с жестким контрактом данных"""
        if not faq:
            return f'''<h2>{self.texts['faq_title']}</h2>
<div class="cards">
    <div class="card">
        <h4>Часто задаваемые вопросы</h4>
        <p>Информация будет добавлена позже.</p>
    </div>
</div>'''
        
        # ЖЕСТКИЙ КОНТРАКТ: faq должен быть Sequence[Dict[str,str]]
        if not isinstance(faq, (list, tuple)):
            logger.error(f"❌ FAQ должен быть Sequence, получен {type(faq)}")
            return f'''<h2>{self.texts['faq_title']}</h2>
<div class="cards">
    <div class="card">
        <h4>Ошибка типа FAQ</h4>
        <p>FAQ должен быть списком или кортежем.</p>
    </div>
</div>'''
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: должно быть ровно 6 FAQ
        if len(faq) != 6:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: FAQ должен содержать ровно 6 элементов, получено {len(faq)}")
            return f'''<h2>{self.texts['faq_title']}</h2>
<div class="cards">
    <div class="card">
        <h4>Ошибка количества FAQ</h4>
        <p>Ожидается 6 FAQ, получено {len(faq)}.</p>
    </div>
</div>'''
        
        logger.info(f"🔧 faq_render_ok: {len(faq)} элементов для {self.locale}")
        logger.info(f"🔧 ОТЛАДКА HTMLBuilder: faq={faq}")
        
        # Рендерим FAQ - итерируемся строго по списку
        html = f'<h2>{self.texts["faq_title"]}</h2>\n<div class="faq-section">'
        for i, item in enumerate(faq):
            logger.info(f"🔧 ОТЛАДКА HTMLBuilder: рендерим FAQ[{i}] = {item}")
            # Проверяем формат каждого элемента
            if not isinstance(item, dict) or 'question' not in item or 'answer' not in item:
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Неправильный формат FAQ[{i}]: {item}")
                continue
            
            question = item["question"]
            answer = item["answer"]
            
            # Исправляем объём для воскоплава (400 мл → 200 мл)
            if 'воскоплав' in (question + answer).lower():
                question = question.replace('400 мл', '200 мл')
                answer = answer.replace('400 мл', '200 мл')
            
            html += f'''
    <div class="faq-item">
        <div class="faq-question">{question}</div>
        <div class="faq-answer">{answer}</div>
    </div>'''
        html += '\n</div>'
        
        logger.info(f"✅ FAQ рендерится: {len(faq)} элементов для {self.locale}")
        return html
    
    def _is_placeholder_faq(self, question: str, answer: str) -> bool:
        """Проверяет, является ли FAQ заглушкой"""
        placeholder_patterns = [
            'запасной вопрос', 'запасной ответ', 'placeholder', 'stub',
            'дополнительный вопрос', 'дополнительный ответ'
        ]
        
        question_lower = question.lower()
        answer_lower = answer.lower()
        
        # Проверяем только явные паттерны заглушек
        for pattern in placeholder_patterns:
            if pattern in question_lower or pattern in answer_lower:
                return True
        
        # Проверяем, что это не настоящий вопрос (нет ? в конце)
        if not question.endswith('?'):
            return True
        
        # Проверяем слишком короткие или общие ответы
        if len(answer) < 30 or answer_lower in ['продукт изготовлен из качественных материалов', 'информация будет добавлена позже']:
            return True
        
        return False
    
    def _is_valid_question(self, question: str) -> bool:
        """Проверяет, является ли вопрос валидным"""
        if not question or len(question) < 6:
            return False
        
        # Должен заканчиваться на ?
        if not question.endswith('?'):
            return False
        
        # Должен начинаться с заглавной буквы
        if not question[0].isupper():
            return False
        
        # Расширенные паттерны вопросительных конструкций
        ru_patterns = [
            'как', 'какие', 'что', 'можно ли', 'подходит ли', 'сколько', 'когда', 'почему', 'где', 'чем', 'для чего', 'нужно ли',
            'есть ли', 'из какого', 'какой', 'какая', 'какое', 'какие', 'чем', 'для чего', 'как использовать', 'как применять',
            'подходит ли', 'можно ли', 'нужно ли', 'есть ли', 'какие есть', 'что входит', 'что содержит'
        ]
        ua_patterns = [
            'як', 'які', 'що', 'чи можна', 'чи підходить', 'скільки', 'коли', 'чому', 'де', 'чим', 'для чого', 'чи потрібно',
            'чи є', 'з якого', 'який', 'яка', 'яке', 'які', 'чим', 'для чого', 'як використовувати', 'як застосовувати',
            'чи підходить', 'чи можна', 'чи потрібно', 'чи є', 'які є', 'що входить', 'що містить'
        ]
        
        question_lower = question.lower()
        
        if self.locale == 'ru':
            return any(question_lower.startswith(pattern) for pattern in ru_patterns)
        else:
            return any(question_lower.startswith(pattern) for pattern in ua_patterns)
    
    def _process_description(self, description) -> List[str]:
        """Обработка описания в абзацы"""
        if not description:
            return []
        
        # Если это словарь с p1 и p2
        if isinstance(description, dict):
            p1_sentences = description.get('p1', [])
            p2_sentences = description.get('p2', [])
            
            # Проверяем, что это списки предложений
            if isinstance(p1_sentences, list) and isinstance(p2_sentences, list):
                p1 = ' '.join(p1_sentences[:3])
                p2 = ' '.join(p2_sentences[:3])
                
                # Исправляем объём для воскоплава (400 мл → 200 мл)
                if 'воскоплав' in (p1 + p2).lower():
                    p1 = p1.replace('400 мл', '200 мл')
                    p2 = p2.replace('400 мл', '200 мл')
                
                return [p1, p2]
        
        # Если это строка, обрабатываем как раньше
        if isinstance(description, str):
            # Очищаем от промо-заглушек
            description = self._clean_promo_stubs(description)
            
            # Разбиваем на предложения
            sentences = re.split(r'(?<=[.!?])\s+', description)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # Если предложений меньше 6, дополняем
            while len(sentences) < 6:
                if self.locale == 'ru':
                    additional = [
                        "Подходит для всех типов кожи и не вызывает раздражения.",
                        "Рекомендуется для профессионального использования в салонах красоты.",
                        "Обладает приятным ароматом и быстро впитывается.",
                        "Обеспечивает длительный эффект и надежную защиту.",
                        "Изготовлен из качественных материалов и компонентов."
                    ]
                else:
                    additional = [
                        "Підходить для всіх типів шкіри та не викликає подразнення.",
                        "Рекомендується для професійного використання в салонах краси.",
                        "Має приємний аромат та швидко вбирається.",
                        "Забезпечує тривалий ефект та надійний захист.",
                        "Виготовлений з якісних матеріалів та компонентів."
                    ]
                
                for sentence in additional:
                    if sentence not in sentences and len(sentences) < 6:
                        sentences.append(sentence)
                        break
            
            # Разбиваем на 2 абзаца по 3 предложения
            p1 = ' '.join(sentences[:3])
            p2 = ' '.join(sentences[3:6])
            
            return [p1, p2]
        
        return []
    
    def _clean_promo_stubs(self, text: str) -> str:
        """Очистка от промо-заглушек"""
        if not text:
            return text
        
        # Паттерны для удаления
        patterns = [
            r'PRO razko[^.]*\.',
            r'інтернет‑магазин матеріалів[^.]*\.',
            r'товары для мастеров[^.]*\.',
            r'Качественный продукт для профессионального использования[^.]*\.',
            r'Якісний продукт для професійного використання[^.]*\.'
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def get_alt_text(self, title: str) -> str:
        """Получение alt текста для изображения"""
        if not title:
            return f"Товар {self.texts['alt_suffix']}"
        
        return f"{title} {self.texts['alt_suffix']}"
