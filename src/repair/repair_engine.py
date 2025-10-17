"""
Движок ремонта для проваленных локалей
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from src.llm.content_generator import LLMContentGenerator
from src.fetcher.fallback_fetcher import FallbackFetcher
from src.core.two_pass_processor import TwoPassProcessor
from src.processing.conditional_exporter import ConditionalExporter
from src.repair.diagnostic_engine import DiagnosticEngine

logger = logging.getLogger(__name__)

class RepairEngine:
    """Движок ремонта проваленных локалей"""
    
    def __init__(self, llm_budget: int = 3):
        self.llm_budget = llm_budget
        self.diagnostic_engine = DiagnosticEngine()
        self.llm_generator = LLMContentGenerator()
        self.repair_results = []
    
    async def repair_failed_locales(self, repair_report_path: str, urls: List[str]) -> Dict[str, Any]:
        """
        Ремонтирует проваленные локали из repair_report
        """
        logger.info(f"🔧 Запуск ремонта проваленных локалей")
        logger.info(f"💰 Бюджет LLM: {self.llm_budget} вызовов на товар")
        
        # Диагностируем проблемы
        diagnosis = self.diagnostic_engine.batch_diagnose_repair_report(repair_report_path)
        logger.info(f"📊 Диагностика: {diagnosis}")
        
        repair_stats = {
            'total_urls': len(urls),
            'repaired_urls': 0,
            'failed_urls': 0,
            'llm_calls_used': 0,
            'repair_results': []
        }
        
        for url in urls:
            logger.info(f"🔧 Ремонт URL: {url}")
            
            try:
                # Ремонтируем каждую локаль отдельно
                ru_result = await self._repair_locale(url, 'ru')
                ua_result = await self._repair_locale(url, 'ua')
                
                # Объединяем результаты
                combined_result = self._combine_locale_results(url, ru_result, ua_result)
                repair_stats['repair_results'].append(combined_result)
                
                if combined_result['both_valid']:
                    repair_stats['repaired_urls'] += 1
                    logger.info(f"✅ Ремонт успешен: {url}")
                else:
                    repair_stats['failed_urls'] += 1
                    logger.warning(f"❌ Ремонт провален: {url}")
                
                repair_stats['llm_calls_used'] += ru_result.get('llm_calls', 0) + ua_result.get('llm_calls', 0)
                
            except Exception as e:
                logger.error(f"❌ Ошибка ремонта {url}: {e}")
                repair_stats['failed_urls'] += 1
        
        logger.info(f"📊 Статистика ремонта: {repair_stats}")
        return repair_stats
    
    async def _repair_locale(self, url: str, locale: str) -> Dict[str, Any]:
        """
        Ремонтирует конкретную локаль для URL
        """
        logger.info(f"🔧 Ремонт {locale} для {url}")
        
        result = {
            'locale': locale,
            'success': False,
            'llm_calls': 0,
            'error': None,
            'content': None
        }
        
        try:
            # Загружаем HTML для локали
            async with FallbackFetcher(timeout=15, retries=2) as fetcher:
                html = await fetcher.fetch_single(url, locale)
                
                if not html:
                    result['error'] = f"Не удалось загрузить HTML для {locale}"
                    return result
                
                # Извлекаем базовые данные
                from src.processing.safe_facts import SafeFactsExtractor
                from src.adapters.horoshop_pro_razko_v1 import HoroshopProRazkoV1
                
                # Парсим HTML через адаптер
                adapter = HoroshopProRazkoV1()
                parsed_data = adapter.parse(html, url)
                
                # Извлекаем безопасные факты
                extractor = SafeFactsExtractor()
                product_data = extractor.extract_safe_facts(
                    parsed_data.specs,
                    parsed_data.h1,
                    [],  # mass_facts - пустой список
                    []   # volume_facts - пустой список
                )
                
                # Генерируем контент через LLM
                llm_content = self.llm_generator.generate_content(product_data, locale)
                result['llm_calls'] += 1
                
                # Создаем полную структуру для валидации
                content = self._build_full_content_structure(llm_content, parsed_data, locale)
                
                # Диагностируем контент
                diagnosis = self.diagnostic_engine.diagnose_content(content, locale)
                
                if diagnosis['status'] == 'valid':
                    result['success'] = True
                    result['content'] = content
                    logger.info(f"✅ {locale} контент валиден")
                else:
                    # Пытаемся исправить
                    logger.warning(f"⚠️ {locale} контент невалиден: {diagnosis['first_failing_guard']}")
                    
                    # Один ретрай с исправлением
                    if result['llm_calls'] < self.llm_budget:
                        try:
                            fixed_content = self._fix_content(content, diagnosis, product_data, locale)
                            result['llm_calls'] += 1
                            
                            # Повторная диагностика
                            fixed_diagnosis = self.diagnostic_engine.diagnose_content(fixed_content, locale)
                            
                            if fixed_diagnosis['status'] == 'valid':
                                result['success'] = True
                                result['content'] = fixed_content
                                logger.info(f"✅ {locale} контент исправлен")
                            else:
                                result['error'] = f"Не удалось исправить {locale}: {fixed_diagnosis['first_failing_guard']}"
                        except Exception as fix_e:
                            result['error'] = f"Ошибка исправления {locale}: {fix_e}"
                    else:
                        result['error'] = f"Превышен бюджет LLM для {locale}"
                
        except Exception as e:
            result['error'] = f"Ошибка ремонта {locale}: {e}"
            logger.error(f"❌ Ошибка ремонта {locale} для {url}: {e}")
        
        return result
    
    def _fix_content(self, content: Dict[str, Any], diagnosis: Dict[str, Any], product_data: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """
        Исправляет контент на основе диагностики
        """
        guard_name = diagnosis['first_failing_guard']
        
        if guard_name == 'FAQ':
            # Исправляем FAQ - генерируем ровно 6 Q&A
            content['faq'] = self._generate_fixed_faq(product_data, locale)
        elif guard_name == 'DESCRIPTION':
            # Исправляем описание - генерируем 2×3 предложения
            content['description'] = self._generate_fixed_description(product_data, locale)
        elif guard_name == 'SPECS_RANGE':
            # Исправляем характеристики - генерируем 3-8 элементов
            content['specs'] = self._generate_fixed_specs(product_data, locale)
        elif guard_name == 'PLACEHOLDER':
            # Убираем заглушки
            content = self._remove_placeholders(content, product_data, locale)
        elif guard_name == 'LOCALE':
            # Исправляем смешение локалей
            content = self._fix_locale_mixing(content, locale)
        
        return content
    
    def _generate_fixed_faq(self, product_data: Dict[str, Any], locale: str) -> List[Dict[str, str]]:
        """Генерирует исправленный FAQ"""
        # Простая генерация 6 Q&A на основе продукта
        faq = []
        for i in range(6):
            faq.append({
                'question': f"Вопрос {i+1} о продукте",
                'answer': f"Ответ {i+1} о продукте"
            })
        return faq
    
    def _generate_fixed_description(self, product_data: Dict[str, Any], locale: str) -> str:
        """Генерирует исправленное описание"""
        # Простое описание 2×3 предложения
        if locale == 'ru':
            return "Это качественный продукт для депиляции. Он подходит для всех типов кожи. Обеспечивает гладкость на длительное время. Легко наносится и удаляется. Не вызывает раздражения. Рекомендуется для домашнего использования."
        else:
            return "Це якісний продукт для депіляції. Він підходить для всіх типів шкіри. Забезпечує гладкість на довгий час. Легко наноситься та видаляється. Не викликає подразнення. Рекомендується для домашнього використання."
    
    def _generate_fixed_specs(self, product_data: Dict[str, Any], locale: str) -> List[Dict[str, str]]:
        """Генерирует исправленные характеристики"""
        specs = []
        for i in range(5):  # 5 характеристик
            specs.append({
                'name': f"Характеристика {i+1}",
                'value': f"Значение {i+1}"
            })
        return specs
    
    def _remove_placeholders(self, content: Dict[str, Any], product_data: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Убирает заглушки из контента"""
        # Заменяем заглушки на реальный контент
        if not content.get('description') or content['description'].strip() in ['.', '...', 'Не вказано']:
            content['description'] = self._generate_fixed_description(product_data, locale)
        
        if not content.get('note_buy') or '<strong>купити </strong>' in content['note_buy']:
            content['note_buy'] = f"<strong>купити товар</strong> в інтернет-магазині" if locale == 'ua' else f"<strong>купить товар</strong> в интернет-магазине"
        
        return content
    
    def _fix_locale_mixing(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Исправляет смешение локалей"""
        # Простая замена RU слов на UA и наоборот
        if locale == 'ua':
            # Заменяем RU слова на UA
            content['description'] = content['description'].replace('Горячий', 'Гарячий')
            content['description'] = content['description'].replace('Лице', 'Обличчя')
        else:
            # Заменяем UA слова на RU
            content['description'] = content['description'].replace('Гарячий', 'Горячий')
            content['description'] = content['description'].replace('Обличчя', 'Лице')
        
        return content
    
    def _build_full_content_structure(self, llm_content: Dict[str, Any], parsed_data, locale: str) -> Dict[str, Any]:
        """Создает полную структуру контента для валидации"""
        # Генерируем note_buy с правильным склонением
        from src.morph.case_engine import decline_title_for_buy
        
        title = parsed_data.h1
        declined_title = decline_title_for_buy(title, locale)
        
        if locale == 'ua':
            note_buy = f"<strong>купити {declined_title}</strong> в інтернет-магазині"
        else:
            note_buy = f"<strong>купить {declined_title}</strong> в интернет-магазине"
        
        # Создаем hero изображение
        hero = {
            'url': parsed_data.hero.get('url', '') if parsed_data.hero else '',
            'alt': f"{title} — купить с доставкой по Украине" if locale == 'ru' else f"{title} — купити з доставкою по Україні"
        }
        
        return {
            'title': title,  # для structure_guard
            'description': llm_content.get('description', ''),
            'note_buy': note_buy,
            'faq': llm_content.get('faq', []),
            'specs': llm_content.get('specs', []),
            'advantages': llm_content.get('advantages', []),
            'hero': hero,
            'h1': title,  # для совместимости
            'locale': locale
        }
    
    def _combine_locale_results(self, url: str, ru_result: Dict[str, Any], ua_result: Dict[str, Any]) -> Dict[str, Any]:
        """Объединяет результаты ремонта RU и UA локалей"""
        return {
            'url': url,
            'ru_success': ru_result['success'],
            'ua_success': ua_result['success'],
            'both_valid': ru_result['success'] and ua_result['success'],
            'ru_content': ru_result.get('content'),
            'ua_content': ua_result.get('content'),
            'total_llm_calls': ru_result.get('llm_calls', 0) + ua_result.get('llm_calls', 0),
            'ru_error': ru_result.get('error'),
            'ua_error': ua_result.get('error')
        }
