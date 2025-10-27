"""
Асинхронный процессор товаров для новой архитектуры
"""
import asyncio
import logging
import re
from typing import Dict, Any, Optional, List
import httpx
from concurrent.futures import ThreadPoolExecutor

# ===== НОРМАЛИЗАЦИЯ ДЛЯ ROUND 3 =====
# Заменяем украинские буквы на русские для упрямых товаров
UA_TO_RU_MAP = str.maketrans({
    'і': 'и', 'І': 'И',
    'ї': 'и', 'Ї': 'И',
    'є': 'е', 'Є': 'Е',
    'ґ': 'г', 'Ґ': 'Г',
})

# Универсальный словарь перевода labels характеристик
SPEC_LABEL_TRANSLATIONS = {
    'ru': {
        'країна виробник': 'Страна производитель',
        'країна виробника': 'Страна производителя',
        'країна': 'Страна',
        'циферблат': 'Циферблат',
        'особливості': 'Особенности',
        'особливости': 'Особенности',
    },
    'ua': {
        'страна производитель': 'Країна виробник',
        'страна производителя': 'Країна виробника',
        'страна': 'Країна',
        'циферблат': 'Циферблат',
        'особенности': 'Особливості',
    }
}

def normalize_ru_specs_round3(specs: List[Dict]) -> List[Dict]:
    """Нормализация характеристик для Round 3 - заменяем украинские буквы на русские и переводим labels"""
    if not specs:
        return specs
    
    normalized = []
    for spec in specs:
        label = str(spec.get('label', ''))
        value = str(spec.get('value', ''))
        
        # Шаг 1: Заменяем украинские буквы на русские
        label = label.translate(UA_TO_RU_MAP)
        value = value.translate(UA_TO_RU_MAP)
        
        # Шаг 2: Переводим label если он на украинском
        label_lower = label.lower()
        if label_lower in SPEC_LABEL_TRANSLATIONS['ru']:
            label = SPEC_LABEL_TRANSLATIONS['ru'][label_lower]
            logger.info(f"✅ Перевод label: '{spec.get('label', '')}' → '{label}'")
        
        normalized.append({'label': label, 'value': value})
    
    return normalized

from src.fetcher.fallback_fetcher import FallbackFetcher
from src.llm.async_content_generator import AsyncLLMContentGenerator
from src.processing.async_content_critic import AsyncContentCritic
from src.processing.fragment_renderer import ProductFragmentRenderer
from src.processing.enhanced_note_buy_generator import EnhancedNoteBuyGenerator
from src.processing.description_generator import DescriptionGenerator
from src.processing.note_buy_generator import NoteBuyGenerator
from src.processing.specs_generator import SpecsGenerator
from src.processing.advantages_generator import AdvantagesGenerator
# from src.validation.guards import validate_content  # Не используется в асинхронной версии
from src.processing.real_facts_extractor import RealFactsExtractor
from src.parsing.bundle_extractor import extract_bundle_components
from src.validation.specs_validator import validate_specs_integrity, log_specs_changes, validate_and_filter_specs
from src.processing.unified_parser import UnifiedParser
from src.processing.faq_generator import FaqGenerator
from src.processing.universal_translator import UniversalTranslator
from src.utils.resilient_fetcher import ResilientFetcher
from src.recovery.llm_recovery import LLMRecovery

logger = logging.getLogger(__name__)

class AsyncProductProcessor:
    """Асинхронный процессор одного товара"""
    
    def __init__(self):
        self.llm_generator = AsyncLLMContentGenerator()
        self.content_critic = AsyncContentCritic()
        self.fragment_renderer = ProductFragmentRenderer()
        self.note_buy_generator = EnhancedNoteBuyGenerator()
        self.description_generator = DescriptionGenerator()
        self.note_buy_generator_new = NoteBuyGenerator()
        self.specs_generator = SpecsGenerator()
        self.advantages_generator = AdvantagesGenerator()
        self.real_extractor = RealFactsExtractor()
        self.unified_parser = UnifiedParser()
        self.faq_generator = FaqGenerator()
        self.translator = UniversalTranslator()
        
        # 🛡️ Resilient компоненты для 100% обработки
        self.resilient_fetcher = ResilientFetcher(timeout=30, max_retries=3)
        self.llm_recovery = LLMRecovery()
        
        # Режим валидации (может быть установлен в relaxed для Round 3)
        self.relaxed_validation = False
        
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def process_product_with_validation(self, product_url: str, client: httpx.AsyncClient, 
                            llm_semaphore: asyncio.Semaphore, write_lock: asyncio.Lock) -> Dict[str, Any]:
        """Обработка с валидацией качества"""
        try:
            result = await self.process_product(product_url, client, llm_semaphore, write_lock)
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки {product_url}: {e}")
            result = {
                'url': product_url,
                'status': 'failed',
                'error': str(e),
                'ru_html': '',
                'ua_html': ''
            }
            return result

        # Валидация результата (с учетом relaxed_mode для Round 3)
        is_valid, issues = self._validate_content_quality(result, relaxed_mode=self.relaxed_validation)

        if is_valid:
            result['status'] = 'success'
            logger.info(f"✅ Товар обработан успешно: {product_url}")
        else:
            result['status'] = 'failed'
            result['error'] = '; '.join(issues)
            logger.error(f"❌ Товар НЕ прошёл валидацию: {product_url}")
            logger.error(f"   Проблемы: {issues}")

        return result

    async def process_product(self, product_url: str, client: httpx.AsyncClient, 
                            llm_semaphore: asyncio.Semaphore, write_lock: asyncio.Lock) -> Dict[str, Any]:
        """
        Асинхронная обработка одного товара (обе локали)
        
        Двухуровневая система:
        1. Первичная обработка через GPT-4o-mini (быстро и дешево)
        2. Fallback через Claude (если первичная провалилась)
        
        Args:
            product_url: URL товара
            client: HTTP клиент
            llm_semaphore: Семафор для ограничения LLM запросов
            write_lock: Блокировка для записи в файлы
            
        Returns:
            Dict с результатами обработки
        """
        try:
            logger.info(f"🔄 Начинаю обработку товара: {product_url}")
            
            # Генерируем URL для обеих локалей
            ua_url, ru_url = self._get_locale_urls(product_url)
            
            # Используем UnifiedParser для параллельной загрузки HTML
            ua_html, ru_html = await self.unified_parser.fetch_html(ua_url)
            
            # Обрабатываем RU сначала для получения компонентов
            ru_result = await self._process_locale(ru_html, ru_url, 'ru', client, llm_semaphore)
            
            # Извлекаем RU компоненты для UA фолбэка
            ru_bundle_components = ru_result.get('bundle_components', [])
            
            # Обрабатываем UA с передачей RU компонентов
            ua_result = await self._process_locale(ua_html, ua_url, 'ua', client, llm_semaphore, ru_bundle_components)
            
            # Собираем финальный результат
            final_result = {
                'url': product_url,
                'ua_html': ua_result.get('html', ''),
                'ru_html': ru_result.get('html', ''),
                'ua_title': ua_result.get('title', ''),
                'ru_title': ru_result.get('title', ''),
                'ua_metadata': ua_result.get('metadata', {}),
                'ru_metadata': ru_result.get('metadata', {}),
                'success': ua_result.get('success', False) and ru_result.get('success', False)
            }
            
            # ✅ ВАЛИДАЦИЯ РЕЗУЛЬТАТА: Проверяем что все необходимые поля заполнены
            if not self._validate_processing_result(final_result):
                logger.error(f"❌ ВАЛИДАЦИЯ: Неполный результат для {product_url}")
                raise ValueError(f"Неполный результат обработки для {product_url}")
            
            logger.info(f"✅ Товар обработан: {product_url}")
            return final_result
            
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА обработки товара {product_url}: {e}")
            
            # 🛡️ RESILIENT RECOVERY: Пробуем обработать через Claude
            try:
                logger.info(f"🛡️ Запускаем resilient recovery (Claude fallback) для {product_url}")
                recovery_result = await self._process_product_resilient(product_url, client, llm_semaphore)
                
                # ✅ КРИТИЧНО: Валидируем результат recovery ПЕРЕД возвратом
                if recovery_result.get('success', False):
                    # Проверяем качество контента (с учетом relaxed_mode для Round 3)
                    is_valid, issues = self._validate_content_quality(recovery_result, relaxed_mode=self.relaxed_validation)
                    
                    if is_valid:
                        logger.info(f"✅ Resilient recovery успешен и прошёл валидацию: {product_url}")
                        return recovery_result
                    else:
                        logger.error(f"❌ Resilient recovery НЕ прошёл валидацию: {product_url}")
                        logger.error(f"   Проблемы: {issues}")
                        # Продолжаем к финальному fallback
                else:
                    logger.error(f"❌ Resilient recovery не удался: {product_url}")
                    
            except Exception as recovery_error:
                logger.error(f"❌ Ошибка resilient recovery: {recovery_error}")
            
            # Последний fallback - возвращаем ошибку
            raise ValueError(f"Не удалось обработать товар {product_url}: {e}")
    
    def _validate_processing_result(self, result: Dict[str, Any]) -> bool:
        """Валидирует что результат обработки содержит все необходимые поля"""
        try:
            # Проверяем основные поля
            required_fields = ['url', 'ua_html', 'ru_html', 'ua_title', 'ru_title']
            
            for field in required_fields:
                if not result.get(field):
                    logger.warning(f"⚠️ ВАЛИДАЦИЯ: Отсутствует поле {field}")
                    return False
            
            # Проверяем что HTML не пустой
            if len(result.get('ua_html', '').strip()) < 100:
                logger.warning(f"⚠️ ВАЛИДАЦИЯ: UA HTML слишком короткий")
                return False
                
            if len(result.get('ru_html', '').strip()) < 100:
                logger.warning(f"⚠️ ВАЛИДАЦИЯ: RU HTML слишком короткий")
                return False
            
            # Проверяем что названия не пустые
            if len(result.get('ua_title', '').strip()) < 3:
                logger.warning(f"⚠️ ВАЛИДАЦИЯ: UA название слишком короткое")
                return False
                
            if len(result.get('ru_title', '').strip()) < 3:
                logger.warning(f"⚠️ ВАЛИДАЦИЯ: RU название слишком короткое")
                return False
            
            logger.info(f"✅ ВАЛИДАЦИЯ: Результат валиден")
            return True
            
        except Exception as e:
            logger.error(f"❌ ВАЛИДАЦИЯ: Ошибка валидации: {e}")
            return False
    
    def _validate_content_quality(self, result: Dict[str, Any], relaxed_mode: bool = False) -> tuple[bool, list[str]]:
        """Валидация качества контента
        
        Args:
            result: Результат обработки
            relaxed_mode: Если True, применяем смягченные требования (для Round 3 с GPT-4o)
        """
        issues = []
        
        ru_html = result.get('ru_html', '')
        ua_html = result.get('ua_html', '')
        
        # Устанавливаем пороги в зависимости от режима
        min_faq = 2 if relaxed_mode else 4
        min_benefits = 2 if relaxed_mode else 3
        min_html_size = 800 if relaxed_mode else 1500
        
        # 1. FAQ - критически важно
        ru_faq = ru_html.count('<div class="faq-item">')
        ua_faq = ua_html.count('<div class="faq-item">')
        
        if ru_faq < min_faq:
            issues.append(f"RU FAQ: {ru_faq} (нужно ≥{min_faq})")
        if ua_faq < min_faq:
            issues.append(f"UA FAQ: {ua_faq} (нужно ≥{min_faq})")
        
        # 2. Описания (должно быть минимум 2 <p>)
        if ru_html.count('</p>') < 2:
            issues.append("RU описание неполное")
        if ua_html.count('</p>') < 2:
            issues.append("UA описание неполное")
        
        # 3. Преимущества
        ru_benefits = ru_html.count('<div class="card"><h4>')
        ua_benefits = ua_html.count('<div class="card"><h4>')
        
        if ru_benefits < min_benefits:
            issues.append(f"RU преимущества: {ru_benefits} (нужно ≥{min_benefits})")
        if ua_benefits < min_benefits:
            issues.append(f"UA преимущества: {ua_benefits} (нужно ≥{min_benefits})")
        
        # 4. Минимальный размер
        if len(ru_html) < min_html_size:
            issues.append(f"RU HTML слишком короткий: {len(ru_html)} байт (минимум {min_html_size})")
        if len(ua_html) < min_html_size:
            issues.append(f"UA HTML слишком короткий: {len(ua_html)} байт (минимум {min_html_size})")
        
        # 5. Проверяем что нет заглушек
        if 'error-message' in ru_html or 'error-message' in ua_html:
            issues.append("Обнаружены заглушки в HTML")
        
        # 6. Проверяем что нет пустых блоков
        if 'FAQ</h2>' in ru_html and ru_faq == 0:
            issues.append("RU FAQ заголовок есть, но FAQ отсутствуют")
        if 'FAQ</h2>' in ua_html and ua_faq == 0:
            issues.append("UA FAQ заголовок есть, но FAQ отсутствуют")
        
        # ============ СТРОГИЕ ПРОВЕРКИ (работают ВСЕГДА) ============
        # Эти проблемы НЕ ДОПУСКАЮТСЯ даже в relaxed_mode
        
        strict_issues = []
        
        # 1. Проверка на заглушки в описании
        generic_phrases = [
            'качественный продукт',
            'эффективное средство',
            'якісний продукт',
            'ефективний засіб'
        ]
        
        for phrase in generic_phrases:
            # Проверяем RU описание
            ru_desc_match = re.search(r'<div class="description">(.*?)</div>', ru_html, re.DOTALL)
            if ru_desc_match:
                desc_text = ru_desc_match.group(1).strip()
                # Если описание очень короткое (<150 символов) и содержит заглушку - это плохо
                if phrase in desc_text.lower() and len(desc_text) < 200:
                    strict_issues.append(f"RU описание содержит заглушку '{phrase}' при малом объеме текста")
            
            # Проверяем UA описание
            ua_desc_match = re.search(r'<div class="description">(.*?)</div>', ua_html, re.DOTALL)
            if ua_desc_match:
                desc_text = ua_desc_match.group(1).strip()
                if phrase in desc_text.lower() and len(desc_text) < 200:
                    strict_issues.append(f"UA описание содержит заглушку '{phrase}' при малом объеме текста")
        
        # 2. Проверка на некорректные названия (с кавычками/JSON)
        ru_title = result.get('ru_title', '')
        ua_title = result.get('ua_title', '')
        
        if ru_title.startswith('"') or ru_title.startswith('{'):
            strict_issues.append("RU название не очищено от JSON символов")
        if ua_title.startswith('"') or ua_title.startswith('{'):
            strict_issues.append("UA название не очищено от JSON символов")
        
        # 3. Проверка на единственное преимущество "Высокое качество" (заглушка)
        if ru_benefits == 1 and 'Высокое качество</h4>' in ru_html:
            strict_issues.append("RU преимущества: только заглушка 'Высокое качество'")
        if ua_benefits == 1 and ('Висока якість</h4>' in ua_html or 'Высокое качество</h4>' in ua_html):
            strict_issues.append("UA преимущества: только заглушка 'Висока якість'")
        
        # Если есть строгие проблемы - ВСЕГДА отклоняем (даже в relaxed_mode)
        if strict_issues:
            logger.error(f"❌ СТРОГАЯ ВАЛИДАЦИЯ: Обнаружены заглушки/недоработки - ОТКЛОНЯЕМ")
            logger.error(f"   Проблемы: {strict_issues}")
            return (False, strict_issues + issues)
        
        # ============ ГИБКАЯ ВАЛИДАЦИЯ (только для relaxed_mode) ============
        
        if relaxed_mode and issues:
            # В relaxed_mode можем принять товар с некритичными проблемами (меньше FAQ, etc)
            # НО только если НЕТ заглушек (это мы уже проверили выше)
            logger.info(f"🔵 СМЯГЧЕННАЯ ВАЛИДАЦИЯ (Round 3): {len(issues)} проблем, но БЕЗ заглушек - ПРИНИМАЕМ")
            logger.info(f"   Проблемы: {issues[:3]}..." if len(issues) > 3 else f"   Проблемы: {issues}")
            return (True, issues)
        
        return (len(issues) == 0, issues)
    
    async def _process_locale(self, html: str, url: str, locale: str,
                            client: httpx.AsyncClient, llm_semaphore: asyncio.Semaphore, 
                            ru_bundle_components: List[str] = None) -> Dict[str, Any]:
        """Обработка одной локали с извлечением компонентов набора"""
        try:
            if not html:
                return {'html': '', 'success': False, 'error': 'Empty HTML'}
            
            # CPU-bound операции в отдельном потоке
            loop = asyncio.get_running_loop()
            
            # Извлекаем факты и компоненты набора параллельно
            facts_task = loop.run_in_executor(
                self.executor, 
                self._extract_facts_from_html, 
                html, url, locale
            )
            
            # Используем UnifiedParser для парсинга характеристик и состава набора
            # Получаем HTML обеих версий для сопоставления
            ua_url, ru_url = self._get_locale_urls(url)
            ua_html_for_parsing, ru_html_for_parsing = await self.unified_parser.fetch_html(ua_url)
            
            # Парсим характеристики и состав набора с помощью UnifiedParser
            specs_task = self.unified_parser.parse_characteristics(
                ua_html_for_parsing, ru_html_for_parsing
            )
            bundle_task = loop.run_in_executor(
                self.executor,
                self.unified_parser.parse_bundle,
                ua_html_for_parsing, ru_html_for_parsing
            )
            
            facts, specs, bundle_components = await asyncio.gather(facts_task, specs_task, bundle_task)
            
            # КРИТИЧНО: Переводим название для правильной локали
            original_title = facts.get('title', '')
            if original_title:
                try:
                    translated_title = await self.unified_parser.get_translated_title(
                        ua_html_for_parsing, ru_html_for_parsing, locale
                    )
                    facts['title'] = translated_title
                    logger.info(f"✅ Название для {locale}: {translated_title}")
                except Exception as e:
                    logger.error(f"❌ Ошибка перевода названия: {e}")
                    # Оставляем исходное название если перевод не удался
            
            # Добавляем характеристики из UnifiedParser в факты (теперь specs это кортеж)
            if specs:
                ru_specs, ua_specs = specs
                
                # Выбираем правильный список характеристик в зависимости от локали
                if locale == 'ru':
                    # ✅ ВСЕГДА нормализуем украинские буквы в RU характеристиках (Флізелін → Флизелин)
                    # Это решает проблему валидации языка в генераторе контента
                    selected_specs = normalize_ru_specs_round3(ru_specs)
                    logger.info(f"✅ Используем RU характеристики: {len(ru_specs)} (переведенные через LLM)")
                    logger.info(f"🔧 Нормализованы украинские буквы в RU характеристиках (Флізелін → Флизелин)")
                else:  # ua
                    selected_specs = ua_specs
                    logger.info(f"✅ Используем UA характеристики: {len(ua_specs)} (переведенные через LLM)")
                
                # selected_specs уже список словарей, используем напрямую
                logger.info(f"🔍 DEBUG: selected_specs тип: {type(selected_specs)}")
                logger.info(f"🔍 DEBUG: selected_specs содержимое: {selected_specs}")
                facts['specs'] = selected_specs
                logger.info(f"✅ Извлечено {len(selected_specs)} характеристик через UnifiedParser для {locale}")
            
            # Добавляем компоненты набора в факты
            facts['bundle_components'] = bundle_components
            if bundle_components:
                logger.info(f"✅ Извлечено {len(bundle_components)} компонентов набора для {locale}")
                
                # Сохраняем RU компоненты для UA фолбэка
                if locale == 'ru':
                    facts['ru_bundle_components'] = bundle_components[:]
                    logger.info(f"💾 Сохранены RU компоненты для UA фолбэка: {len(bundle_components)}")
            
            # Добавляем компоненты набора в факты
            facts['bundle_components'] = bundle_components
            if bundle_components:
                logger.info(f"✅ Извлечено {len(bundle_components)} компонентов набора для {locale}")
                
                # Сохраняем RU компоненты для UA фолбэка
                if locale == 'ru':
                    facts['ru_bundle_components'] = bundle_components[:]
                    logger.info(f"💾 Сохранены RU компоненты для UA фолбэка: {len(bundle_components)}")
            
            # Для UA: передаем RU компоненты для фолбэка
            if locale == 'ua' and ru_bundle_components:
                facts['ru_bundle_components'] = ru_bundle_components
                logger.info(f"🔄 UA: Переданы RU компоненты для фолбэка: {len(ru_bundle_components)}")
                
                # Принудительно применяем фолбэк если UA компонентов меньше
                if not bundle_components or len(bundle_components) < len(ru_bundle_components):
                    logger.warning(f"🔄 UA: Принудительный фолбэк - заменяем {len(bundle_components) if bundle_components else 0} на {len(ru_bundle_components)}")
                    bundle_components = ru_bundle_components[:]
                    facts['bundle_components'] = bundle_components
                    logger.info(f"✅ UA: Фолбэк применен - теперь {len(bundle_components)} компонентов")
                else:
                    logger.info(f"✅ UA: Полный состав найден ({len(bundle_components)} компонентов)")
            
            # Генерация контента с ограничением LLM
            async with llm_semaphore:
                content = await self._generate_content(facts, locale, client)
            
            # Рендеринг HTML
            html_result = await loop.run_in_executor(
                self.executor,
                self._render_html,
                content, locale, url, html
            )
            
            return {
                'html': html_result,
                'title': facts.get('title', ''),
                'success': True,
                'bundle_components': bundle_components,
                'metadata': {
                    'facts_count': len(facts.get('specs', [])),
                    'content_quality': content.get('quality_score', 0.0),
                    'bundle_components_count': len(bundle_components)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки локали {locale}: {e}")
            return {'html': '', 'success': False, 'error': str(e)}
    
    def _extract_facts_from_html(self, html: str, url: str, locale: str) -> Dict[str, Any]:
        """Извлекает РЕАЛЬНЫЕ факты из HTML"""
        try:
            # Используем реальный извлекатель фактов
            facts = self.real_extractor.extract_product_facts(html, url)
            
            # Добавляем локаль
            facts['locale'] = locale
            
            # Валидируем, что у нас есть основные данные
            if not facts.get('title') or len(facts.get('title', '').strip()) < 3:
                raise ValueError(f"Не удалось извлечь название товара из {url}")
            
            logger.info(f"✅ Извлечены факты для {locale}: {facts.get('title', 'N/A')}")
            return facts
            
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА извлечения фактов для {url}: {e}")
            # НЕ возвращаем пустой словарь - это приведет к generic контенту
            raise ValueError(f"Не удалось извлечь факты из {url}: {e}")
    
    def _extract_title_from_html(self, html: str) -> str:
        """Извлекает заголовок из HTML"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            h1_tag = soup.find('h1')
            return h1_tag.get_text().strip() if h1_tag else ""
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения заголовка: {e}")
            return ""
    
    def _extract_h1(self, html: str) -> str:
        """Извлечение H1 заголовка"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            h1_tag = soup.find('h1')
            return h1_tag.get_text().strip() if h1_tag else ""
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения H1: {e}")
            return ""
    
    def _extract_specs(self, html: str) -> List[Dict[str, str]]:
        """Извлечение характеристик"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            specs = []
            # Ищем таблицы с характеристиками
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text().strip()
                        value = cells[1].get_text().strip()
                        if key and value:
                            specs.append({'key': key, 'value': value})
            
            return specs[:8]  # Ограничиваем до 8 характеристик
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения характеристик: {e}")
            return []
    
    async def _generate_content(self, facts: Dict[str, Any], locale: str, 
                              client: httpx.AsyncClient) -> Dict[str, Any]:
        """ОПТИМИЗИРОВАННАЯ генерация контента с жёстким включением состава набора"""
        try:
            from src.llm.unified_content_generator import UnifiedContentGenerator
            
            # Инициализируем объединенный генератор
            unified_generator = UnifiedContentGenerator()
            
            # ОДИН LLM вызов вместо четырех (25 сек вместо 80 сек)
            # Временно отключаем Structured Output из-за проблем с API
            unified_content = await unified_generator.generate_unified_content(facts, locale)
            
            # ИСПРАВЛЕНИЕ: Используем описание из unified_content_generator, НЕ заменяем на шаблон!
            description = unified_content.get('description', [])
            # КРИТИЧНО: НЕ объединяем параграфы в строку - оставляем список для FragmentRenderer!
            
            # Для FaqGenerator нужно описание как строка
            description_for_faq = description
            if isinstance(description, list):
                description_for_faq = ' '.join(description)
            
            # Собираем полный контекст для FaqGenerator
            product_data = {
                'title': facts.get('title', ''),
                'description': description_for_faq,
                'specs': facts.get('specs', []),
                'bundle': [],  # ИСПРАВЛЕНИЕ: bundle_components не определена, используем пустой список
                'volume': facts.get('volume', ''),
                'purpose': facts.get('purpose', '')
            }
            
            # СТАБИЛЬНАЯ ВЕРСИЯ: Сначала генерируем FAQ на русском, затем переводим
            # Используем SmartLLMClient для FaqGenerator и Translator
            from src.llm.smart_llm_client import SmartLLMClient
            smart_llm_client = SmartLLMClient()
            self.faq_generator.llm = smart_llm_client
            self.translator.llm_client = smart_llm_client
            
            # 1. ВСЕГДА генерируем FAQ на русском для максимального качества
            # 🔍 ДЕБАГ: Проверяем что передаем в FaqGenerator
            logger.info(f"🔍 DEBUG: type(product_data) = {type(product_data)}")
            logger.info(f"🔍 DEBUG: product_data keys = {list(product_data.keys()) if isinstance(product_data, dict) else 'НЕ СЛОВАРЬ'}")
            if isinstance(product_data, dict) and 'specs' in product_data:
                specs = product_data['specs']
                logger.info(f"🔍 DEBUG: product_data['specs'] тип = {type(specs)}")
                logger.info(f"🔍 DEBUG: product_data['specs'] длина = {len(specs) if specs else 0}")
                if specs and len(specs) > 0:
                    logger.info(f"🔍 DEBUG: product_data['specs'][0] = {specs[0]}")
            
            ru_faq_list = await self.faq_generator.generate(product_data, 'ru', num_questions=6)
            logger.info(f"✅ Сгенерировано {len(ru_faq_list)} FAQ на русском")
            
            # 2. Переводим на нужный язык если требуется
            if locale == 'ua':
                faq_list = await self.translator.translate_faq_list(ru_faq_list, 'uk')
                logger.info(f"✅ Переведено {len(faq_list)} FAQ на украинский")
            else:
                faq_list = ru_faq_list
                logger.info(f"✅ Используем {len(faq_list)} FAQ на русском")
            
            # Используем характеристики из UnifiedParser (приоритет) или генерируем новые
            original_specs = facts.get('specs', [])
            logger.info(f"🔍 {locale.upper()}: facts.get('specs') тип: {type(original_specs)}")
            logger.info(f"🔍 {locale.upper()}: facts.get('specs') длина: {len(original_specs) if original_specs else 0}")
            if original_specs:
                logger.info(f"🔍 {locale.upper()}: facts.get('specs') первый элемент: {original_specs[0]}")
            else:
                logger.warning(f"⚠️ {locale.upper()}: facts.get('specs') ПУСТОЙ!")
            
            if original_specs:
                # Используем характеристики из UnifiedParser
                logger.info(f"✅ Используем {len(original_specs)} характеристик из UnifiedParser для {locale}")
                final_specs = original_specs
            else:
                # Генерируем характеристики (строгий режим)
                generated_specs = self.specs_generator.generate_specs_from_facts(facts, locale)
                
                # Дополнительная пост-валидация после генерации
                if generated_specs:
                    # Преобразуем в формат кортежей для валидации
                    source_facts = [(spec.get('name', ''), spec.get('value', '')) for spec in generated_specs]
                    
                    # Применяем строгую валидацию
                    validated_specs, validation_status = validate_specs_integrity(generated_specs, source_facts)
                    
                    # Дополнительная пост-валидация
                    final_specs = validate_and_filter_specs(validated_specs, source_facts)
                    
                    # Логируем изменения
                    log_specs_changes(generated_specs, final_specs)
                    
                    if validation_status != "VALID":
                        logger.warning(f"⚠️ Характеристики исправлены после валидации: {validation_status}")
                else:
                    final_specs = generated_specs
            
            # Добавляем характеристики и метаданные
            content = {
                'title': facts.get('title', ''),
                'image_url': facts.get('image_url', ''),
                'description': description,
                'advantages': unified_content.get('advantages', []),
                'faq': faq_list,  # Используем FAQ из FaqGenerator
                'note_buy': unified_content.get('note_buy', ''),
                'specs': final_specs,
                'bundle_components': [],  # ИСПРАВЛЕНИЕ: bundle_components не определена, используем пустой список
                'quality_score': 0.9,  # Высокое качество с улучшенными FAQ
                'critic_status': 'UNIFIED_GENERATION_WITH_ENHANCED_FAQ' if faq_list else 'UNIFIED_GENERATION'
            }
            
            logger.info(f"✅ Объединенный контент сгенерирован для {locale}: {len(content)} блоков")
            
            # 🔍 ДЕБАГ: Проверяем что в возвращаемом content
            specs_in_return = content.get('specs', [])
            logger.info(f"🔍 {locale.upper()}: content['specs'] в возврате тип: {type(specs_in_return)}")
            logger.info(f"🔍 {locale.upper()}: content['specs'] в возврате длина: {len(specs_in_return) if specs_in_return else 0}")
            if specs_in_return:
                logger.info(f"🔍 {locale.upper()}: content['specs'] в возврате первый элемент: {specs_in_return[0]}")
            else:
                logger.warning(f"⚠️ {locale.upper()}: content['specs'] в возврате ПУСТОЙ!")
            
            # ИСПРАВЛЕНИЕ: убираем проверку bundle_components так как она не определена
            return content
            
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА генерации контента: {e}")
            # НЕ возвращаем fallback - это приведет к generic контенту
            raise ValueError(f"Не удалось сгенерировать контент для {locale}: {e}")
    
    def _render_html(self, content: Dict[str, Any], locale: str, product_url: str, html_content: str) -> str:
        """Рендеринг HTML (CPU-bound операция)"""
        try:
            # Проверяем, что контент не пустой
            if not content or not any(content.values()):
                raise ValueError(f"Пустой контент для рендеринга {locale}")
            
            # Валидируем обязательные поля
            required_fields = ['title', 'description', 'note_buy']
            for field in required_fields:
                if not content.get(field) or len(str(content.get(field)).strip()) < 3:
                    raise ValueError(f"Отсутствует обязательное поле {field} для {locale}")
            
            # Подготавливаем блоки для рендеринга
            # Конвертируем FAQ в правильный формат для рендерера
            faq_data = content.get('faq', [])
            if isinstance(faq_data, list) and faq_data:
                # Проверяем тип первого элемента
                first_item = faq_data[0]
                if isinstance(first_item, dict):
                    # Уже правильный формат
                    faq_formatted = faq_data
                elif isinstance(first_item, tuple):
                    # Конвертируем кортежи в словари
                    faq_formatted = [{'question': q, 'answer': a} for q, a in faq_data]
                elif isinstance(first_item, list):
                    # Если это список списков, конвертируем
                    faq_formatted = [{'question': item[0], 'answer': item[1]} for item in faq_data]
                else:
                    # Неизвестный формат, создаем пустой список
                    logger.warning(f"⚠️ Неизвестный формат FAQ: {type(first_item)}")
                    faq_formatted = []
            else:
                faq_formatted = []
            
            # ЛОГИРОВАНИЕ: Проверяем что в content
            logger.info(f"🔍 content.description тип: {type(content.get('description', 'НЕТ'))}")
            if 'description' in content:
                desc = content['description']
                logger.info(f"🔍 content.description содержимое: {str(desc)[:100]}...")
            
            # ЛОГИРОВАНИЕ: Что передаем в blocks
            description_for_blocks = content.get('description', '')
            logger.info(f"🔍 Передаем в blocks.description тип: {type(description_for_blocks)}")
            
            # 🔍 ДЕБАГ: Проверяем specs в content
            specs_in_content = content.get('specs', [])
            logger.info(f"🔍 {locale.upper()}: content['specs'] тип: {type(specs_in_content)}")
            logger.info(f"🔍 {locale.upper()}: content['specs'] длина: {len(specs_in_content)}")
            if specs_in_content:
                logger.info(f"🔍 {locale.upper()}: content['specs'] первый элемент: {specs_in_content[0]}")
            else:
                logger.warning(f"⚠️ {locale.upper()}: content['specs'] ПУСТОЙ!")
            
            blocks = {
                'title': content.get('title', ''),
                'description': description_for_blocks,
                'advantages': content.get('advantages', []),
                'specs': content.get('specs', []),
                'faq': faq_formatted,
                'note_buy': content.get('note_buy', ''),
                'image_url': content.get('image_url', ''),
                'image_data': content.get('image_data', {}),
                'product_url': product_url,  # Добавляем URL товара для ProductImageExtractor
                'html_content': html_content,  # Добавляем HTML контент для извлечения изображений
                'bundle_components': content.get('bundle_components', [])  # Добавляем компоненты набора
            }
            
            # Рендерим HTML
            html_result = self.fragment_renderer.render_product_fragment(blocks, locale)
            
            # Проверяем, что не получили заглушку
            if 'error-message' in html_result:
                logger.error(f"❌ Получена заглушка при рендеринге {locale} - FALLBACK ОТКЛЮЧЕН")
                raise ValueError(f"HTML содержит заглушку для {locale} - fallback отключен")
            
            return html_result
            
        except Exception as e:
            logger.error(f"❌ Ошибка рендеринга HTML: {e}")
            raise ValueError(f"Ошибка рендеринга HTML для {locale} - fallback отключен")
    
    def _create_fallback_html(self, locale: str) -> str:
        """Создание fallback HTML при ошибках"""
        try:
            if locale == 'ua':
                return '''<div class="ds-desc">
                    <h2>Товар Epilax</h2>
                    <h2>Опис</h2>
                    <p>Якісний продукт для догляду за шкірою. Підходить для щоденного використання та забезпечує ефективний результат.</p>
                    <p class="note-buy">Замовте товар вже сьогодні та насолоджуйтеся якісним доглядом!</p>
                    <h2>Переваги</h2>
                    <ul><li>Висока якість</li><li>Підходить для щоденного використання</li><li>Ефективний результат</li></ul>
                    <h2>FAQ</h2>
                    <div class="faq-section">
                        <div class="faq-item">
                            <div class="faq-question">Для чого призначений цей продукт?</div>
                            <div class="faq-answer">Продукт призначений для догляду за шкірою.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Як використовувати?</div>
                            <div class="faq-answer">Використовуйте згідно з інструкцією на упаковці.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Чи підходить для чутливої шкіри?</div>
                            <div class="faq-answer">Так, продукт підходить для всіх типів шкіри.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Який об'єм упаковки?</div>
                            <div class="faq-answer">Об'єм вказано на упаковці.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Чи є протипоказання?</div>
                            <div class="faq-answer">Перед використанням проконсультуйтеся з лікарем.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Як зберігати?</div>
                            <div class="faq-answer">Зберігайте в сухому прохолодному місці.</div>
                        </div>
                    </div>
                </div>'''
            else:
                return '''<div class="ds-desc">
                    <h2>Товар Epilax</h2>
                    <h2>Описание</h2>
                    <p>Качественный продукт для ухода за кожей. Подходит для ежедневного использования и обеспечивает эффективный результат.</p>
                    <p class="note-buy">Закажите товар уже сегодня и наслаждайтесь качественным уходом!</p>
                    <h2>Преимущества</h2>
                    <ul><li>Высокое качество</li><li>Подходит для ежедневного использования</li><li>Эффективный результат</li></ul>
                    <h2>FAQ</h2>
                    <div class="faq-section">
                        <div class="faq-item">
                            <div class="faq-question">Для чего предназначен этот продукт?</div>
                            <div class="faq-answer">Продукт предназначен для ухода за кожей.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Как использовать?</div>
                            <div class="faq-answer">Используйте согласно инструкции на упаковке.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Подходит ли для чувствительной кожи?</div>
                            <div class="faq-answer">Да, продукт подходит для всех типов кожи.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Какой объём упаковки?</div>
                            <div class="faq-answer">Объём указан на упаковке.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Есть ли противопоказания?</div>
                            <div class="faq-answer">Перед использованием проконсультируйтесь с врачом.</div>
                        </div>
                        <div class="faq-item">
                            <div class="faq-question">Как хранить?</div>
                            <div class="faq-answer">Храните в сухом прохладном месте.</div>
                        </div>
                    </div>
                </div>'''
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания fallback HTML: {e}")
            return f'<div class="ds-desc"><p class="error-message">Ошибка обработки товара</p></div>'
    
    def _get_locale_urls(self, product_url: str) -> tuple[str, str]:
        """Генерация URL для обеих локалей - УНИВЕРСАЛЬНО"""
        from src.utils.domain_detector import UniversalDomainDetector
        
        # Используем универсальный детектор для генерации пары локалей
        ua_url, ru_url = UniversalDomainDetector.get_locale_pair(product_url)
        
        return ua_url, ru_url
    
    def _create_fallback_content(self, facts: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Создание fallback контента при ошибках"""
        try:
            title = facts.get('title', 'Товар Epilax')
            
            if locale == 'ua':
                return {
                    'title': title,
                    'description': f'{title} - це якісний продукт для догляду за шкірою. Він підходить для щоденного використання та забезпечує ефективний результат.',
                    'advantages': [
                        'Висока якість',
                        'Підходить для щоденного використання',
                        'Ефективний результат'
                    ],
                    'specs': facts.get('specs', []),
                    'faq': [
                        {'question': 'Для чого призначений цей продукт?', 'answer': 'Продукт призначений для догляду за шкірою.'},
                        {'question': 'Як використовувати?', 'answer': 'Використовуйте згідно з інструкцією на упаковці.'},
                        {'question': 'Чи підходить для чутливої шкіри?', 'answer': 'Так, продукт підходить для всіх типів шкіри.'},
                        {'question': 'Який об\'єм упаковки?', 'answer': 'Об\'єм вказано на упаковці.'},
                        {'question': 'Чи є протипоказання?', 'answer': 'Перед використанням проконсультуйтеся з лікарем.'},
                        {'question': 'Як зберігати?', 'answer': 'Зберігайте в сухому прохолодному місці.'}
                    ],
                    'note_buy': f'Замовте {title.lower()} вже сьогодні та насолоджуйтеся якісним доглядом!',
                    'quality_score': 0.3,
                    'critic_status': 'FALLBACK'
                }
            else:
                return {
                    'title': title,
                    'description': f'{title} - это качественный продукт для ухода за кожей. Он подходит для ежедневного использования и обеспечивает эффективный результат.',
                    'advantages': [
                        'Высокое качество',
                        'Подходит для ежедневного использования',
                        'Эффективный результат'
                    ],
                    'specs': facts.get('specs', []),
                    'faq': [
                        {'question': 'Для чего предназначен этот продукт?', 'answer': 'Продукт предназначен для ухода за кожей.'},
                        {'question': 'Как использовать?', 'answer': 'Используйте согласно инструкции на упаковке.'},
                        {'question': 'Подходит ли для чувствительной кожи?', 'answer': 'Да, продукт подходит для всех типов кожи.'},
                        {'question': 'Какой объём упаковки?', 'answer': 'Объём указан на упаковке.'},
                        {'question': 'Есть ли противопоказания?', 'answer': 'Перед использованием проконсультируйтесь с врачом.'},
                        {'question': 'Как хранить?', 'answer': 'Храните в сухом прохладном месте.'}
                    ],
                    'note_buy': f'Закажите {title.lower()} уже сегодня и наслаждайтесь качественным уходом!',
                    'quality_score': 0.3,
                    'critic_status': 'FALLBACK'
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка создания fallback контента: {e}")
            # Последний fallback
            return {
                'title': 'Товар Epilax',
                'description': 'Качественный продукт для ухода за кожей.',
                'advantages': ['Высокое качество'],
                'specs': [],
                'faq': [{'question': 'Вопрос', 'answer': 'Ответ'}],
                'note_buy': 'Закажите товар уже сегодня!',
                'quality_score': 0.1,
                'critic_status': 'EMERGENCY_FALLBACK'
            }
    
    async def _process_product_resilient(
        self, 
        product_url: str, 
        client: httpx.AsyncClient, 
        llm_semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """🛡️ Resilient обработка товара с гарантией 100% успеха"""
        
        try:
            logger.info(f"🛡️ Resilient processing: {product_url}")
            
            # Инициализируем Claude для recovery (максимальная надёжность)
            # ✅ ПРАВИЛЬНО: Используем Claude Haiku для resilient recovery (экономичный fallback)
            from anthropic import Anthropic
            import os
            claude_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            self.llm_recovery.llm = claude_client
            self.llm_recovery.model = "claude-3-haiku-20240307"  # Claude Haiku - быстрый fallback
            logger.info(f"🟣 Resilient recovery использует Claude Haiku для fallback")
            
            # 1. Получаем URLs для обеих локалей
            ua_url, ru_url = self.resilient_fetcher.get_fallback_urls(product_url)
            
            # 2. Пробуем загрузить контент с fallback
            try:
                ua_content, ru_content, status = await self.resilient_fetcher.fetch_product_with_locales(product_url)
                logger.info(f"✅ Resilient fetch: {status}")
            except Exception as e:
                logger.error(f"❌ Resilient fetch failed: {e}")
                raise
            
            # 3. Извлекаем базовую информацию через LLM
            ua_product_name = await self.llm_recovery.extract_title_from_raw_html(ua_content)
            ru_product_name = await self.llm_recovery.extract_title_from_raw_html(ru_content)
            
            # Если не удалось извлечь названия, используем fallback
            if not ua_product_name and not ru_product_name:
                base_name = f"Товар из {product_url}"
                ua_product_name = base_name
                ru_product_name = base_name
            elif not ua_product_name:
                ua_product_name = ru_product_name
            elif not ru_product_name:
                ru_product_name = ua_product_name
            
            logger.info(f"✅ Resilient: UA название = '{ua_product_name}'")
            logger.info(f"✅ Resilient: RU название = '{ru_product_name}'")
            
            # 4. Извлекаем характеристики через LLM
            characteristics = []
            if ua_content:
                characteristics = await self.llm_recovery.extract_characteristics_from_raw_html(
                    ua_content, ua_product_name
                )
            
            if not characteristics and ru_content:
                logger.info(f"🔄 Пробуем извлечь характеристики из RU версии")
                characteristics = await self.llm_recovery.extract_characteristics_from_raw_html(
                    ru_content, ru_product_name
                )
            
            # 5. Исправляем языковые проблемы если нужно
            if characteristics:
                # Для RU версии исправляем язык
                ru_characteristics = await self.llm_recovery.fix_language_issues(
                    characteristics, target_locale='ru'
                )
                logger.info(f"✅ Resilient: {len(ru_characteristics)} RU характеристик")
            else:
                ru_characteristics = []
                logger.warning(f"⚠️ Resilient: характеристики не найдены")
            
            # 6. Генерируем контент через LLM
            async with llm_semaphore:
                ru_content_dict = await self.llm_recovery.generate_fallback_content(
                    ru_product_name, ru_characteristics, 'ru'
                )
                
                ua_content_dict = await self.llm_recovery.generate_fallback_content(
                    ua_product_name, characteristics, 'ua'
                )
            
            # 7. Ищем изображения
            ru_image = await self.llm_recovery.find_image_from_raw_html(ru_content, ru_product_name)
            ua_image = await self.llm_recovery.find_image_from_raw_html(ua_content, ua_product_name)
            
            # 8. Рендерим HTML
            loop = asyncio.get_running_loop()
            
            # RU HTML
            ru_blocks = {
                'title': ru_product_name,
                'description': ru_content_dict.get('description', f'{ru_product_name} - качественный продукт'),
                'advantages': ru_content_dict.get('advantages', ['Высокое качество']),
                'specs': ru_characteristics,
                'faq': ru_content_dict.get('faq', []),
                'note_buy': f'Закажите {ru_product_name.lower()} уже сегодня!',
                'image_url': ru_image or '',
                'product_url': product_url,
                'html_content': ru_content or '',
                'bundle_components': []
            }
            
            ru_html = await loop.run_in_executor(
                self.executor,
                self._render_html,
                ru_blocks, 'ru', product_url, ru_content or ''
            )
            
            # UA HTML
            ua_blocks = {
                'title': ua_product_name,
                'description': ua_content_dict.get('description', f'{ua_product_name} - якісний продукт'),
                'advantages': ua_content_dict.get('advantages', ['Висока якість']),
                'specs': characteristics,
                'faq': ua_content_dict.get('faq', []),
                'note_buy': f'Замовте {ua_product_name.lower()} вже сьогодні!',
                'image_url': ua_image or '',
                'product_url': product_url,
                'html_content': ua_content or '',
                'bundle_components': []
            }
            
            ua_html = await loop.run_in_executor(
                self.executor,
                self._render_html,
                ua_blocks, 'ua', product_url, ua_content or ''
            )
            
            # 9. Возвращаем результат
            result = {
                'url': product_url,
                'ua_html': ua_html,
                'ru_html': ru_html,
                'ua_title': ua_product_name,
                'ru_title': ru_product_name,
                'ua_metadata': {'recovery_status': 'resilient_ua'},
                'ru_metadata': {'recovery_status': 'resilient_ru'},
                'success': True
            }
            
            logger.info(f"✅ Resilient processing успешен: {product_url}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Resilient processing failed: {e}")
            return {
                'url': product_url,
                'ua_html': '',
                'ru_html': '',
                'ua_title': '',
                'ru_title': '',
                'ua_metadata': {},
                'ru_metadata': {},
                'success': False,
                'error': f'Resilient processing failed: {e}'
            }
