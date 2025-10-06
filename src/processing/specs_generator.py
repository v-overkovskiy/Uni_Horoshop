"""
Генератор характеристик товаров по стандартам ProRazko
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class SpecsGenerator:
    """Генерирует характеристики товаров по стандартам ProRazko"""
    
    def __init__(self):
        self.universal_specs = {
            'ru': [
                {"label": "Страна производства", "value": "Украина"},
                {"label": "Срок годности", "value": "24 месяца"},
                {"label": "Условия хранения", "value": "В сухом прохладном месте"},
                {"label": "Способ применения", "value": "Согласно инструкции"},
                {"label": "Противопоказания", "value": "Индивидуальная непереносимость"}
            ],
            'ua': [
                {"label": "Країна виробництва", "value": "Україна"},
                {"label": "Термін придатності", "value": "24 місяці"},
                {"label": "Умови зберігання", "value": "В сухому прохолодному місці"},
                {"label": "Спосіб застосування", "value": "Згідно з інструкцією"},
                {"label": "Протипоказання", "value": "Індивідуальна непереносимість"}
            ]
        }
    
    def generate_specs_from_facts(self, product_facts: Dict[str, Any], locale: str) -> List[Dict[str, str]]:
        """
        Генерирует характеристики ТОЛЬКО из source_facts.
        ЖЁСТКО: без добавлений, заглушек или выдумок!
        """
        try:
            # СТРОГИЙ РЕЖИМ: Используем ТОЛЬКО реальные характеристики из HTML
            if 'specs' in product_facts and product_facts['specs']:
                original_specs = product_facts['specs']
                logger.info(f"✅ Строгий режим: используем {len(original_specs)} характеристик из HTML")
                
                # Применяем строгий фильтр против заглушек
                filtered_specs = self._strict_filter_specs(original_specs)
                
                if len(filtered_specs) != len(original_specs):
                    removed_count = len(original_specs) - len(filtered_specs)
                    logger.warning(f"⚠️ Строгий фильтр удалил {removed_count} заглушек")
                
                logger.info(f"✅ Финально: {len(filtered_specs)} реальных характеристик для {locale}")
                return filtered_specs
            
            # Если нет характеристик из HTML - возвращаем пустой список
            logger.warning("⚠️ Нет характеристик из HTML - возвращаем пустой список")
            return []
            
        except Exception as e:
            logger.error(f"❌ Ошибка строгой генерации характеристик: {e}")
            return []
    
    def _strict_filter_specs(self, specs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Жёстко фильтрует характеристики, удаляя заглушки и выдумки
        """
        filtered_specs = []
        removed_count = 0
        
        for spec in specs:
            label = spec.get('label', '').strip()
            value = spec.get('value', '').strip()
            
            # Проверяем на заглушки и выдумки
            if self._is_placeholder_spec(label, value):
                removed_count += 1
                logger.warning(f"🚫 Удаляем заглушку: {label}: {value}")
                continue
            
            # Проверяем на пустые значения
            if not label or not value:
                removed_count += 1
                logger.warning(f"🚫 Удаляем пустую характеристику: {label}: {value}")
                continue
            
            # Проверяем на generic значения
            if self._is_generic_value(value):
                removed_count += 1
                logger.warning(f"🚫 Удаляем generic значение: {label}: {value}")
                continue
            
            filtered_specs.append(spec)
        
        if removed_count > 0:
            logger.info(f"🔒 Строгий фильтр: удалено {removed_count} заглушек, осталось {len(filtered_specs)}")
        
        return filtered_specs
    
    def _is_placeholder_spec(self, label: str, value: str) -> bool:
        """Проверяет, является ли характеристика заглушкой"""
        placeholder_patterns = [
            'заглушка', 'placeholder', 'unknown', 'неизвестно', 'н/д', 'n/a',
            'указано на упаковке', 'согласно инструкции', 'в сухом месте',
            'украина', 'україна', 'epilax', '100 г', 'косметический уход', 'все типы'
        ]
        
        label_lower = label.lower()
        value_lower = value.lower()
        
        for pattern in placeholder_patterns:
            if pattern in label_lower or pattern in value_lower:
                return True
        
        return False
    
    def _is_generic_value(self, value: str) -> bool:
        """Проверяет, является ли значение generic"""
        generic_values = [
            'все типы', 'универсальный', 'стандартный', 'обычный',
            'качественный продукт', 'эффективное средство', 'профессиональный'
        ]
        
        value_lower = value.lower()
        
        for generic in generic_values:
            if generic in value_lower:
                return True
        
        return False
    
    def generate_universal_spec(self, index: int, product_facts: Dict[str, Any], locale: str) -> Dict[str, str]:
        """Генерирует универсальную характеристику"""
        try:
            if index < len(self.universal_specs[locale]):
                return self.universal_specs[locale][index]
            
            # Дополнительные универсальные характеристики
            additional_specs = {
                'ru': [
                    {"label": "Форма выпуска", "value": "Косметическое средство"},
                    {"label": "Состав", "value": "Натуральные компоненты"},
                    {"label": "Упаковка", "value": "Пластиковая бутылка"}
                ],
                'ua': [
                    {"label": "Форма випуску", "value": "Косметичний засіб"},
                    {"label": "Склад", "value": "Натуральні компоненти"},
                    {"label": "Упаковка", "value": "Пластикова пляшка"}
                ]
            }
            
            additional_index = index - len(self.universal_specs[locale])
            if additional_index < len(additional_specs[locale]):
                return additional_specs[locale][additional_index]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации универсальной характеристики: {e}")
            return None
    
    def _extract_volume_from_url_and_title(self, url: str, title: str) -> str:
        """Извлекает объём из URL и названия"""
        import re
        
        # Поиск в URL
        volume_patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:ml|мл)',
            r'(\d+(?:\.\d+)?)\s*(?:hram|грам|g)',
            r'(\d+(?:\.\d+)?)\s*(?:gram|грамм)'
        ]
        
        for pattern in volume_patterns:
            match = re.search(pattern, url + ' ' + title, re.IGNORECASE)
            if match:
                volume = match.group(1)
                if 'ml' in match.group(0).lower() or 'мл' in match.group(0).lower():
                    return f"{volume} мл"
                elif 'hram' in match.group(0).lower() or 'грам' in match.group(0).lower():
                    return f"{volume} г"
        
        return None
    
    def _extract_scent_from_url(self, url: str) -> str:
        """Извлекает аромат из URL"""
        scent_mapping = {
            'kokos': 'Кокос',
            'vetiver': 'Ветивер', 
            'aqua-blue': 'Аква Блю',
            'bilyi-chai': 'Белый чай',
            'morska-sil': 'Морская соль'
        }
        
        for pattern, scent in scent_mapping.items():
            if pattern in url.lower():
                return scent
        
        return None
    
    def _extract_purpose_from_url(self, url: str) -> str:
        """Извлекает назначение из URL"""
        if 'hel-dlia-dushu' in url:
            return 'Очищение и увлажнение кожи'
        elif 'pudra' in url:
            return 'Энзимный пилинг и отшелушивание'
        elif 'fliuid' in url:
            return 'Предотвращение врастания волос'
        elif 'pinka-dlia-intymnoi' in url:
            return 'Интимная гигиена'
        elif 'pinka-dlia-ochyshchennia' in url:
            return 'Мягкое очищение кожи'
        elif 'hel-do-depiliatsii' in url:
            return 'Подготовка к депиляции'
        
        return None
    
    def _extract_product_type_from_url(self, url: str) -> str:
        """Извлекает тип средства из URL"""
        if 'hel-dlia-dushu' in url:
            return 'Гель для душа'
        elif 'pudra' in url:
            return 'Пудра энзимная'
        elif 'fliuid' in url:
            return 'Флюид'
        elif 'pinka' in url:
            return 'Пенка'
        elif 'hel-do-depiliatsii' in url:
            return 'Гель для депиляции'
        
        return None
    
    def _extract_skin_type_from_url(self, url: str) -> str:
        """Извлекает тип кожи из URL"""
        if 'sukhoi-ta-normalnoi' in url:
            return 'Сухая и нормальная'
        elif 'zhyrnoi-ta-kombinovanoi' in url:
            return 'Жирная и комбинированная'
        else:
            return 'Все типы кожи'
    
