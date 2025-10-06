"""
Fallback процессор для обработки спорных случаев без блокировок
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class FallbackProcessor:
    """Обработчик fallback режима для спорных случаев"""
    
    def __init__(self):
        # Инициализация будет добавлена при интеграции с существующими модулями
        pass
    
    def process_fallback(self, content: Dict[str, Any], locale: str, issues: List[str]) -> Dict[str, Any]:
        """Обрабатывает контент в fallback режиме"""
        result = content.copy()
        result['export_mode'] = 'fallback'
        result['flags'] = issues.copy()
        result['needs_review'] = False
        result['consistency_fixes'] = []
        
        # Исправляем проблемы с объёмами
        if 'volume_inconsistency' in issues:
            result = self._fix_volume_issues(result, locale)
        
        # Исправляем проблемы с преимуществами
        if 'insufficient_advantages' in issues:
            result = self._fix_advantages_issues(result, locale)
        
        # Исправляем проблемы с бюджетом
        if 'budget_violation' in issues:
            result = self._fix_budget_issues(result, locale)
        
        return result
    
    def _fix_volume_issues(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Исправляет проблемы с объёмами"""
        volume_manager = self.volume_manager_ru if locale == 'ru' else self.volume_manager_ua
        
        # Получаем разрешённые объёмы
        allowed_volumes = set()
        if 'specs' in content and content['specs']:
            for spec in content['specs']:
                if 'value' in spec:
                    volumes = volume_manager.extract_volumes_from_text(spec['value'])
                    allowed_volumes.update(volumes)
        
        if not allowed_volumes:
            return content
        
        # Исправляем описание
        if 'description' in content and content['description']:
            original_desc = content['description']
            fixed_desc = self._fix_volume_in_text(original_desc, allowed_volumes, volume_manager)
            if fixed_desc != original_desc:
                content['description'] = fixed_desc
                content['consistency_fixes'].append('description_volume_fixed')
        
        # Исправляем преимущества
        if 'advantages' in content and content['advantages']:
            fixed_advantages = []
            for advantage in content['advantages']:
                if isinstance(advantage, str):
                    fixed_adv = self._fix_volume_in_text(advantage, allowed_volumes, volume_manager)
                    fixed_advantages.append(fixed_adv)
                else:
                    fixed_advantages.append(advantage)
            content['advantages'] = fixed_advantages
            if fixed_advantages != content['advantages']:
                content['consistency_fixes'].append('advantages_volume_fixed')
        
        return content
    
    def _fix_volume_in_text(self, text: str, allowed_volumes: set, volume_manager) -> str:
        """Исправляет объёмы в тексте"""
        if not text or not allowed_volumes:
            return text
        
        # Находим упоминания объёмов
        mentions = volume_manager.find_volume_mentions(text)
        
        for volume, start, end in mentions:
            if volume not in allowed_volumes:
                # Проверяем, является ли это порционным контекстом
                if volume_manager._is_portion_context(text, volume):
                    continue  # Оставляем как есть
                
                # Пытаемся найти эквивалентный объём
                equivalent = self._find_equivalent_volume(volume, allowed_volumes, volume_manager)
                if equivalent:
                    text = text[:start] + equivalent + text[end:]
                    content['consistency_fixes'].append(f'volume_fixed_{volume}_to_{equivalent}')
        
        return text
    
    def _find_equivalent_volume(self, volume: str, allowed_volumes: set, volume_manager) -> Optional[str]:
        """Находит эквивалентный объём"""
        for allowed in allowed_volumes:
            if volume_manager._are_mass_equivalent(volume, allowed):
                return allowed
        return None
    
    def _fix_advantages_issues(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Исправляет проблемы с преимуществами"""
        if 'advantages' not in content or not content['advantages']:
            return content
        
        # Фильтруем заглушки
        filtered_advantages = []
        for advantage in content['advantages']:
            if isinstance(advantage, str) and not self._is_placeholder(advantage):
                filtered_advantages.append(advantage)
        
        # Если недостаточно преимуществ, автодозаполняем
        if len(filtered_advantages) < 3:
            auto_filled = self._auto_fill_advantages(content, locale, 3 - len(filtered_advantages))
            filtered_advantages.extend(auto_filled)
            content['auto_filled'] = len(auto_filled)
            content['consistency_fixes'].append('advantages_auto_filled')
        
        content['advantages'] = filtered_advantages
        return content
    
    def _is_placeholder(self, text: str) -> bool:
        """Проверяет, является ли текст заглушкой"""
        placeholders = [
            'проверенная временем рецептура',
            'перевірена часом рецептура',
            'дополнительная информация',
            'додаткова інформація',
            'подробнее',
            'подробиці'
        ]
        text_lower = text.lower()
        return any(placeholder in text_lower for placeholder in placeholders)
    
    def _auto_fill_advantages(self, content: Dict[str, Any], locale: str, count: int) -> List[str]:
        """Автодозаполняет преимущества"""
        advantages = []
        
        # Используем информацию из характеристик
        if 'specs' in content and content['specs']:
            for spec in content['specs']:
                if 'name' in spec and 'value' in spec:
                    if 'бренд' in spec['name'].lower() or 'brand' in spec['name'].lower():
                        brand = spec['value']
                        if locale == 'ru':
                            advantages.append(f"Продукция бренда {brand} отличается высоким качеством")
                        else:
                            advantages.append(f"Продукція бренду {brand} відрізняється високою якістю")
                    elif 'материал' in spec['name'].lower() or 'material' in spec['name'].lower():
                        material = spec['value']
                        if locale == 'ru':
                            advantages.append(f"Использование качественного материала {material}")
                        else:
                            advantages.append(f"Використання якісного матеріалу {material}")
        
        return advantages[:count]
    
    def _fix_budget_issues(self, content: Dict[str, Any], locale: str) -> Dict[str, Any]:
        """Исправляет проблемы с бюджетом"""
        # Генерируем note-buy без LLM
        if 'h1' in content and content['h1']:
            note_buy = self._generate_note_buy_fallback(content['h1'], locale)
            content['note_buy'] = note_buy
            content['consistency_fixes'].append('note_buy_generated_fallback')
        
        return content
    
    def _generate_note_buy_fallback(self, h1: str, locale: str) -> str:
        """Генерирует note-buy с улучшенным шаблоном"""
        from src.processing.enhanced_note_buy_generator import EnhancedNoteBuyGenerator
        
        generator = EnhancedNoteBuyGenerator()
        result = generator.generate_enhanced_note_buy(h1, locale)
        
        if result and result.get('content'):
            return result['content']
        else:
            # Fallback к старому шаблону
            if locale == 'ru':
                return f"В нашем интернет‑магазине ProRazko можно <strong>купить</strong> <strong>{h1.lower()}</strong> с быстрой доставкой по Украине и гарантией качества."
            else:
                return f"У нашому інтернет‑магазині ProRazko можна <strong>купити</strong> <strong>{h1.lower()}</strong> з швидкою доставкою по Україні та гарантією якості."
