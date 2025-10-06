"""
Санитайзер для очистки преимуществ от заглушек
"""
import re
import logging
from typing import List, Dict, Tuple
from src.config.advantages_config import get_config, is_domain_relevant, contains_stop_phrase

logger = logging.getLogger(__name__)

class AdvantagesSanitizer:
    """Санитайзер преимуществ"""
    
    def __init__(self, locale: str):
        self.locale = locale
        self.config = get_config(locale)
    
    def sanitize(self, advantages: List[str]) -> Tuple[List[str], Dict[str, int]]:
        """
        Очистка преимуществ от заглушек
        
        Returns:
            Tuple[List[str], Dict[str, int]]: (очищенные преимущества, статистика)
        """
        if not advantages:
            return [], {'raw_count': 0, 'clean_count': 0, 'placeholders_detected': 0}
        
        stats = {
            'raw_count': len(advantages),
            'clean_count': 0,
            'placeholders_detected': 0,
            'domain_relevant': 0,
            'length_filtered': 0,
            'duplicates_removed': 0
        }
        
        # Этап 1: Фильтрация заглушек
        filtered_advantages = []
        for adv in advantages:
            if not adv or not adv.strip():
                continue
            
            # Нормализация текста
            normalized = self._normalize_text(adv)
            if not normalized:
                continue
            
            # Проверка на заглушки
            if contains_stop_phrase(normalized, self.locale):
                stats['placeholders_detected'] += 1
                logger.debug(f"Фильтруем заглушку: {normalized[:50]}...")
                continue
            
            # Исправляем несоответствие объёма для воскоплава (400 мл → 200 мл)
            if 'воскоплав' in normalized.lower() and '400 мл' in normalized:
                normalized = normalized.replace('400 мл', '200 мл')
                logger.info(f"Исправлен объём в преимуществе: 400 мл → 200 мл")
            
            # Проверка длины
            if len(normalized) < self.config['min_length'] or len(normalized) > self.config['max_length']:
                stats['length_filtered'] += 1
                logger.debug(f"Фильтруем по длине: {normalized[:50]}...")
                continue
            
            # Проверка доменной релевантности
            if not is_domain_relevant(normalized, self.locale):
                logger.debug(f"Фильтруем нерелевантное: {normalized[:50]}...")
                continue
            
            stats['domain_relevant'] += 1
            filtered_advantages.append(normalized)
        
        # Этап 2: Дедупликация
        unique_advantages = self._remove_duplicates(filtered_advantages)
        stats['duplicates_removed'] = len(filtered_advantages) - len(unique_advantages)
        
        # Этап 3: Сортировка по качеству
        sorted_advantages = self._sort_by_quality(unique_advantages)
        
        # Этап 4: Ограничение до максимума
        final_advantages = sorted_advantages[:self.config['max_advantages']]
        stats['clean_count'] = len(final_advantages)
        
        logger.info(f"Санитизация {self.locale}: {stats['raw_count']} → {stats['clean_count']} "
                   f"(заглушек: {stats['placeholders_detected']}, дублей: {stats['duplicates_removed']})")
        
        return final_advantages, stats
    
    def _normalize_text(self, text: str) -> str:
        """Нормализация текста"""
        if not text:
            return ""
        
        # Убираем лишние пробелы
        normalized = re.sub(r'\s+', ' ', text.strip())
        
        # Убираем многоточия в конце
        normalized = re.sub(r'\.{3,}$', '', normalized)
        
        # Убираем служебные символы
        normalized = re.sub(r'^[•\-\*\d+\.\)\s]+', '', normalized)
        
        return normalized
    
    def _remove_duplicates(self, advantages: List[str]) -> List[str]:
        """Удаление дубликатов по лемме"""
        seen = set()
        unique = []
        
        for adv in advantages:
            # Создаем ключ для сравнения (убираем пунктуацию и приводим к нижнему регистру)
            key = re.sub(r'[^\w\s]', '', adv.lower().strip())
            if key not in seen and len(key) > 10:  # Минимальная длина ключа
                seen.add(key)
                unique.append(adv)
        
        return unique
    
    def _sort_by_quality(self, advantages: List[str]) -> List[str]:
        """Сортировка по качеству (наиболее фактурные первыми)"""
        def quality_score(adv: str) -> int:
            score = 0
            adv_lower = adv.lower()
            
            # Бонус за цифры и единицы измерения
            if re.search(r'\d+', adv):
                score += 10
            
            # Бонус за единицы измерения
            if re.search(r'(мл|вт|°c|градус|мг|г|кг|см|мм|м)', adv_lower):
                score += 5
            
            # Бонус за бренды
            brands = ['epilax', 'esti', 'bucos', 'prorazko']
            for brand in brands:
                if brand in adv_lower:
                    score += 3
            
            # Бонус за доменные токены
            for token in self.config['domain_tokens']:
                if token in adv_lower:
                    score += 1
            
            # Штраф за общие фразы
            general_phrases = ['высокое качество', 'удобно', 'простота', 'эффективность']
            for phrase in general_phrases:
                if phrase in adv_lower:
                    score -= 2
            
            return score
        
        return sorted(advantages, key=quality_score, reverse=True)
    
    def validate_clean_advantages(self, advantages: List[str]) -> List[str]:
        """Финальная валидация очищенных преимуществ"""
        errors = []
        
        if len(advantages) < self.config['min_advantages']:
            errors.append(f"Недостаточно преимуществ: {len(advantages)} < {self.config['min_advantages']}")
        
        if len(advantages) > self.config['max_advantages']:
            errors.append(f"Слишком много преимуществ: {len(advantages)} > {self.config['max_advantages']}")
        
        # Проверка на оставшиеся заглушки
        for i, adv in enumerate(advantages):
            if contains_stop_phrase(adv, self.locale):
                errors.append(f"Обнаружена заглушка в преимуществе {i+1}: {adv[:50]}...")
        
        if errors:
            logger.error(f"Ошибки валидации преимуществ {self.locale}: {errors}")
        
        return errors
