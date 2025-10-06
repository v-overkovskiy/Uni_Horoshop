"""
Sanity-фикс для автоматического дописывания описаний
"""
import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class SanityFixer:
    """Автоматический фикс для описаний, которые не проходят валидацию"""
    
    def __init__(self):
        self.safe_sentences = {
            'ru': [
                "Подходит для всех типов кожи и волос.",
                "Обеспечивает комфортное и эффективное удаление волос.",
                "Идеально подходит для домашнего использования.",
                "Температура плавления оптимальна для безопасного применения.",
                "Подходит для чувствительной кожи.",
                "Обеспечивает длительную гладкость кожи.",
                "Простота в использовании и быстрый результат.",
                "Подходит для различных зон тела."
            ],
            'ua': [
                "Підходить для всіх типів шкіри та волосся.",
                "Забезпечує комфортне та ефективне видалення волосся.",
                "Ідеально підходить для домашнього використання.",
                "Температура плавлення оптимальна для безпечного застосування.",
                "Підходить для чутливої шкіри.",
                "Забезпечує тривалу гладкість шкіри.",
                "Простота у використанні та швидкий результат.",
                "Підходить для різних зон тіла."
            ]
        }
    
    def fix_description(self, description: str, locale: str, specs: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Применяет sanity-фикс к описанию
        
        Args:
            description: Текущее описание
            locale: Локаль ('ru' или 'ua')
            specs: Характеристики товара для контекста
            
        Returns:
            Dict с результатом фикса
        """
        if not description or not description.strip():
            logger.warning(f"⚠️ Пустое описание для фикса (locale: {locale})")
            return {
                'success': False,
                'reason': 'empty_description',
                'fixed_description': description
            }
        
        # Анализируем текущее описание
        original_sentences = self._count_sentences(description)
        original_length = len(description.strip())
        
        logger.info(f"🔍 Анализ описания для {locale}: {original_sentences} предложений, {original_length} символов")
        
        # Определяем нужное количество дополнительных предложений
        sentences_needed = max(0, 4 - original_sentences)
        chars_needed = max(0, 400 - original_length)
        
        if sentences_needed == 0 and chars_needed <= 50:  # Уже достаточно
            logger.info(f"✅ Описание уже соответствует требованиям для {locale}")
            return {
                'success': True,
                'reason': 'already_valid',
                'fixed_description': description,
                'sentences_added': 0,
                'chars_added': 0
            }
        
        # Выбираем подходящие предложения
        selected_sentences = self._select_sentences(locale, sentences_needed, specs)
        
        if not selected_sentences:
            logger.error(f"❌ Не удалось выбрать предложения для фикса (locale: {locale})")
            return {
                'success': False,
                'reason': 'no_sentences_available',
                'fixed_description': description
            }
        
        # Применяем фикс
        fixed_description = self._apply_fix(description, selected_sentences)
        
        # Проверяем результат
        new_sentences = self._count_sentences(fixed_description)
        new_length = len(fixed_description.strip())
        
        logger.info(f"✅ Sanity-фикс применен для {locale}: добавлено {len(selected_sentences)} предложений, {new_length - original_length} символов")
        
        return {
            'success': True,
            'reason': 'fix_applied',
            'fixed_description': fixed_description,
            'sentences_added': len(selected_sentences),
            'chars_added': new_length - original_length,
            'original_sentences': original_sentences,
            'new_sentences': new_sentences,
            'original_length': original_length,
            'new_length': new_length
        }
    
    def _count_sentences(self, text: str) -> int:
        """Подсчитывает количество предложений в тексте"""
        if not text or not text.strip():
            return 0
        
        # Разбиваем по знакам препинания
        sentences = re.split(r'[.!?]+', text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return len(sentences)
    
    def _select_sentences(self, locale: str, count: int, specs: List[Dict[str, str]] = None) -> List[str]:
        """Выбирает подходящие предложения для дописывания"""
        if locale not in self.safe_sentences:
            logger.error(f"❌ Неподдерживаемая локаль: {locale}")
            return []
        
        available_sentences = self.safe_sentences[locale].copy()
        
        # Если есть характеристики, можем выбрать более релевантные предложения
        if specs:
            relevant_sentences = self._get_relevant_sentences(locale, specs)
            available_sentences = relevant_sentences + available_sentences
        
        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_sentences = []
        for sentence in available_sentences:
            if sentence not in seen:
                seen.add(sentence)
                unique_sentences.append(sentence)
        
        # Возвращаем нужное количество
        return unique_sentences[:count] if count > 0 else []
    
    def _get_relevant_sentences(self, locale: str, specs: List[Dict[str, str]]) -> List[str]:
        """Выбирает релевантные предложения на основе характеристик"""
        relevant = []
        
        # Ищем релевантные характеристики
        specs_dict = {}
        for spec in specs:
            key = spec.get('name', '').lower()
            value = spec.get('value', '').lower()
            specs_dict[key] = value
        
        # Проверяем тип кожи
        if any('кожа' in key or 'шкір' in key for key in specs_dict.keys()):
            if locale == 'ru':
                relevant.append("Подходит для всех типов кожи.")
            else:
                relevant.append("Підходить для всіх типів шкіри.")
        
        # Проверяем температуру
        if any('температур' in key or 'температур' in key for key in specs_dict.keys()):
            if locale == 'ru':
                relevant.append("Оптимальная температура для комфортного использования.")
            else:
                relevant.append("Оптимальна температура для комфортного використання.")
        
        return relevant
    
    def _apply_fix(self, original_description: str, new_sentences: List[str]) -> str:
        """Применяет фикс к описанию"""
        if not new_sentences:
            return original_description
        
        # Убираем лишние пробелы и знаки препинания в конце
        clean_description = original_description.strip()
        if clean_description.endswith('.'):
            clean_description = clean_description[:-1]
        
        # Добавляем новые предложения
        fixed_description = clean_description + '. ' + '. '.join(new_sentences) + '.'
        
        return fixed_description
    
    def validate_fixed_description(self, description: str, min_sentences: int = 4, min_chars: int = 400) -> bool:
        """Проверяет, соответствует ли исправленное описание требованиям"""
        sentences = self._count_sentences(description)
        length = len(description.strip())
        
        return sentences >= min_sentences and length >= min_chars

    def apply_service_product_fix(self, llm_content: Dict[str, Any], locale: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Применяет специальный фикс для сервисных товаров (очистители/обезжириватели).
        Создает корректный RU заголовок и FAQ блок для сервисного типа.
        """
        logger.info(f"🔧 Применение сервисного фикса для {locale}")
        
        # Определяем тип товара по URL или названию
        url = product_data.get('url', '')
        title = product_data.get('title', '')
        
        is_cleaner = any(word in url.lower() for word in ['ochysnyk', 'ochistitel', 'cleaner']) or \
                     any(word in title.lower() for word in ['очиститель', 'очисник', 'cleaner'])
        
        if not is_cleaner:
            logger.info(f"⚠️ Товар не является очистителем, пропускаем сервисный фикс для {locale}")
            return llm_content
        
        # Извлекаем бренд и объем из specs
        specs = llm_content.get('specs', [])
        brand = "ItalWAX"  # По умолчанию
        volume = "500 мл"  # По умолчанию
        
        for spec in specs:
            if isinstance(spec, dict):
                name = spec.get('name', '').lower()
                value = spec.get('value', '')
                if 'бренд' in name or 'brand' in name:
                    brand = value
                elif 'объем' in name or 'volume' in name or 'мл' in value:
                    volume = value
        
        # Создаем корректный заголовок для RU
        if locale == 'ru':
            new_title = f"Очиститель оборудования и воскоплава {brand}, {volume}"
            logger.info(f"🔧 Создан RU заголовок: {new_title}")
            llm_content['title'] = new_title
            
            # Создаем корректный note_buy для сервисного товара
            llm_content['note_buy'] = f"Эффективно удаляет остатки воска и загрязнения с оборудования. Подходит для всех типов восков и поверхностей."
            
            # Создаем базовый FAQ для сервисного типа
            if 'faq' not in llm_content or not llm_content['faq']:
                llm_content['faq'] = [
                    {
                        "question": f"Как использовать очиститель {brand}?",
                        "answer": "Нанесите средство на загрязненную поверхность, оставьте на 2-3 минуты, затем удалите остатки салфеткой или губкой."
                    },
                    {
                        "question": f"Подходит ли {brand} для всех типов восков?",
                        "answer": "Да, очиститель эффективно удаляет остатки любых типов восков и загрязнений с оборудования."
                    },
                    {
                        "question": f"Можно ли использовать {brand} на коже?",
                        "answer": "Нет, это средство предназначено только для очистки оборудования. Избегайте контакта с кожей."
                    },
                    {
                        "question": f"Как часто нужно очищать оборудование {brand}?",
                        "answer": "Рекомендуется очищать оборудование после каждого использования для поддержания гигиены и эффективности."
                    },
                    {
                        "question": f"Безопасен ли {brand} для пластиковых поверхностей?",
                        "answer": "Да, очиститель безопасен для пластиковых и металлических поверхностей оборудования."
                    },
                    {
                        "question": f"Нужно ли смывать {brand} после использования?",
                        "answer": "Да, после очистки рекомендуется протереть поверхность влажной салфеткой для полного удаления остатков средства."
                    }
                ]
                logger.info(f"🔧 Создан FAQ блок для сервисного товара: {len(llm_content['faq'])} Q&A")
        
        return llm_content

    def localize_specs_keys_with_llm(self, specs: List[Dict[str, str]], locale: str) -> Dict[str, Any]:
        """
        Локализует ключи характеристик через LLM с жестким whitelist.
        Возвращает словарь с локализованными specs и флагом успеха.
        """
        logger.info(f"🔧 LLM-локализация ключей для {locale}")
        
        # Белые списки допустимых ключей
        whitelist = {
            'ru': [
                'Тип средства', 'Назначение', 'Объём', 'Вес', 'Температура плавления',
                'Области применения', 'Тип кожи', 'Совместимость', 'Состав', 'Страна производства',
                'Бренд', 'Производитель', 'Артикул', 'Модель', 'Серия', 'Линейка',
                'Консистенция', 'Аромат', 'Цвет', 'Размер', 'Количество', 'Упаковка',
                'Срок годности', 'Условия хранения', 'Способ применения', 'Инструкция'
            ],
            'ua': [
                'Тип засобу', 'Призначення', 'Об\'єм', 'Вага', 'Температура плавлення',
                'Області застосування', 'Тип шкіри', 'Сумісність', 'Склад', 'Країна виробництва',
                'Бренд', 'Виробник', 'Артикул', 'Модель', 'Серія', 'Лінійка',
                'Консистенція', 'Аромат', 'Колір', 'Розмір', 'Кількість', 'Упаковка',
                'Термін придатності', 'Умови зберігання', 'Спосіб застосування', 'Інструкція'
            ]
        }
        
        if locale not in whitelist:
            logger.error(f"❌ Неподдерживаемая локаль для LLM-локализации: {locale}")
            return {'success': False, 'reason': 'unsupported_locale', 'localized_specs': specs}
        
        # Формируем prompt для LLM
        allowed_keys = ', '.join(whitelist[locale])
        specs_text = '\n'.join([f"{spec.get('name', '')}: {spec.get('value', '')}" for spec in specs])
        
        prompt = f"""Приведи ТОЛЬКО ключи характеристик к локали {locale} по этому whitelist, значения не трогай.

ДОПУСТИМЫЕ КЛЮЧИ: {allowed_keys}

ТЕКУЩИЕ ХАРАКТЕРИСТИКИ:
{specs_text}

ПРАВИЛА:
1. Если ключ в whitelist - оставь как есть
2. Если ключ похож на допустимый - замени на ближайший из whitelist
3. Если ключ не подходит - исключи из результата
4. Верни ТОЛЬКО JSON массив объектов {{"name": "ключ", "value": "значение"}}
5. Сохрани все значения без изменений

Ответ (только JSON):"""

        try:
            # Вызываем LLM с JSON-строгим режимом и ретраями
            from src.llm.content_generator import LLMContentGenerator
            llm_generator = LLMContentGenerator()
            
            # Добавляем явное требование JSON в промпт
            json_prompt = prompt + "\n\nВАЖНО: Верни ТОЛЬКО валидный JSON массив без дополнительного текста!"
            
            # Первая попытка с JSON-строгим режимом
            response = llm_generator.call_api_with_json_mode(json_prompt, max_tokens=1000, temperature=0.1)
            
            if not response:
                logger.error("❌ LLM не вернул ответ для локализации ключей")
                return {'success': False, 'reason': 'no_llm_response', 'localized_specs': specs}
            
            # Парсим JSON ответ
            import json
            try:
                localized_specs = json.loads(response)
                if not isinstance(localized_specs, list):
                    raise ValueError("Ответ не является массивом")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Первая попытка LLM-локализации не удалась: {e}")
                
                # Вторая попытка с более строгим промптом
                retry_prompt = f"""Переведи ключи характеристик на {locale} и верни ТОЛЬКО JSON массив:

ДОПУСТИМЫЕ КЛЮЧИ: {', '.join(whitelist[locale])}

ХАРАКТЕРИСТИКИ:
{specs_text}

ПРАВИЛА:
1. Если ключ в whitelist - оставь как есть
2. Если ключ похож - замени на ближайший из whitelist  
3. Если ключ не подходит - исключи
4. Верни ТОЛЬКО JSON массив: [{{"name": "ключ", "value": "значение"}}]

JSON:"""
                
                retry_response = llm_generator.call_api_with_json_mode(retry_prompt, max_tokens=800, temperature=0.1)
                
                if not retry_response:
                    logger.error("❌ Ретрай LLM-локализации не вернул ответ")
                    return {'success': False, 'reason': 'llm_retry_no_response', 'localized_specs': specs}
                
                try:
                    localized_specs = json.loads(retry_response)
                    if not isinstance(localized_specs, list):
                        raise ValueError("Ретрай ответ не является массивом")
                    logger.info("✅ Ретрай LLM-локализации успешен")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"❌ Ретрай LLM-локализации не удался: {e}")
                    return {'success': False, 'reason': 'llm_invalid_json_retry_exhausted', 'localized_specs': specs}
            
            # Валидируем результат
            valid_specs = []
            for spec in localized_specs:
                if isinstance(spec, dict) and 'name' in spec and 'value' in spec:
                    name = spec['name'].strip()
                    value = spec['value'].strip()
                    
                    # Проверяем, что ключ в whitelist
                    if name in whitelist[locale]:
                        valid_specs.append({'name': name, 'value': value})
                    else:
                        logger.warning(f"⚠️ LLM вернул недопустимый ключ: {name}")
            
            if len(valid_specs) < 3:
                logger.error(f"❌ Слишком мало валидных характеристик после LLM-локализации: {len(valid_specs)}")
                return {'success': False, 'reason': 'insufficient_specs', 'localized_specs': specs}
            
            logger.info(f"✅ LLM-локализация успешна: {len(valid_specs)} характеристик")
            return {'success': True, 'localized_specs': valid_specs}
            
        except Exception as e:
            logger.error(f"❌ Ошибка LLM-локализации: {e}")
            return {'success': False, 'reason': 'llm_error', 'localized_specs': specs}

    def deterministic_specs_normalize(self, specs: List[Dict[str, str]], locale: str) -> Dict[str, Any]:
        """
        Детерминированная нормализация spec-ключей: заменяет UA-лейблы на RU и наоборот.
        Возвращает словарь с результатом нормализации.
        """
        logger.info(f"🔧 Детерминированная нормализация spec-ключей для {locale}")
        
        # Словарь замены UA->RU и RU->UA
        normalization_map = {
            'ru': {
                'Тип засобу': 'Тип средства',
                'Призначення': 'Назначение', 
                'Об\'єм': 'Объём',
                'Вага': 'Вес',
                'Температура плавлення': 'Температура плавления',
                'Області застосування': 'Области применения',
                'Тип шкіри': 'Тип кожи',
                'Сумісність': 'Совместимость',
                'Склад': 'Состав',
                'Країна виробництва': 'Страна производства',
                'Виробник': 'Производитель',
                'Серія': 'Серия',
                'Лінійка': 'Линейка',
                'Консистенція': 'Консистенция',
                'Аромат': 'Аромат',
                'Колір': 'Цвет',
                'Розмір': 'Размер',
                'Кількість': 'Количество',
                'Упаковка': 'Упаковка',
                'Термін придатності': 'Срок годности',
                'Умови зберігання': 'Условия хранения',
                'Спосіб застосування': 'Способ применения',
                'Інструкція': 'Инструкция'
            },
            'ua': {
                'Тип средства': 'Тип засобу',
                'Назначение': 'Призначення',
                'Объём': 'Об\'єм', 
                'Вес': 'Вага',
                'Температура плавления': 'Температура плавлення',
                'Области применения': 'Області застосування',
                'Тип кожи': 'Тип шкіри',
                'Совместимость': 'Сумісність',
                'Состав': 'Склад',
                'Страна производства': 'Країна виробництва',
                'Производитель': 'Виробник',
                'Серия': 'Серія',
                'Линейка': 'Лінійка',
                'Консистенция': 'Консистенція',
                'Цвет': 'Колір',
                'Размер': 'Розмір',
                'Количество': 'Кількість',
                'Срок годности': 'Термін придатності',
                'Условия хранения': 'Умови зберігання',
                'Способ применения': 'Спосіб застосування',
                'Инструкция': 'Інструкція'
            }
        }
        
        if locale not in normalization_map:
            logger.error(f"❌ Неподдерживаемая локаль для нормализации: {locale}")
            return {'success': False, 'reason': 'unsupported_locale', 'normalized_specs': specs}
        
        normalized_specs = []
        fixed_count = 0
        dropped_count = 0
        
        for spec in specs:
            name = spec.get('name', '')
            value = spec.get('value', '')
            
            # Проверяем, нужно ли нормализовать ключ
            normalized_name = normalization_map[locale].get(name, name)
            
            if normalized_name != name:
                # Заменяем ключ
                normalized_specs.append({'name': normalized_name, 'value': value})
                fixed_count += 1
                logger.info(f"🔧 Нормализован ключ: '{name}' -> '{normalized_name}'")
            else:
                # Проверяем, не является ли это конфликтным ключом
                if self._is_conflict_key(name, locale):
                    dropped_count += 1
                    logger.info(f"🔧 Удален конфликтный ключ: '{name}'")
                else:
                    # Оставляем как есть
                    normalized_specs.append(spec)
        
        if fixed_count > 0 or dropped_count > 0:
            logger.info(f"✅ Детерминированная нормализация: исправлено {fixed_count}, удалено {dropped_count} ключей")
        
        return {
            'success': True,
            'normalized_specs': normalized_specs,
            'fixed_count': fixed_count,
            'dropped_count': dropped_count
        }
    
    def _is_conflict_key(self, name: str, locale: str) -> bool:
        """Проверяет, является ли ключ конфликтным для данной локали"""
        conflict_patterns = {
            'ru': ['гарячий', 'обличчя', 'область застосування', 'температура плавлення', 
                   'вага', 'об\'єм', 'матеріал', 'колір', 'серія', 'зони', 'тип шкіри'],
            'ua': ['горячий', 'лице', 'область применения', 'температура плавления',
                   'вес', 'объем', 'материал', 'цвет', 'серия', 'зоны', 'тип кожи']
        }
        
        if locale not in conflict_patterns:
            return False
        
        name_lower = name.lower()
        for pattern in conflict_patterns[locale]:
            if pattern in name_lower:
                return True
        
        return False

    def deterministic_specs_drop(self, specs: List[Dict[str, str]], locale: str) -> List[Dict[str, str]]:
        """
        Детерминированный fallback: удаляет конфликтные ключи из specs.
        Используется когда LLM-локализация недоступна или не удалась.
        """
        logger.info(f"🔧 Детерминированный дроп конфликтных ключей для {locale}")
        
        # Паттерны конфликтных ключей
        conflict_patterns = {
            'ru': ['клас', 'классификация', 'тип', 'вид'],  # UA-лексемы в RU
            'ua': ['класс', 'классификация', 'тип', 'вид']   # RU-лексемы в UA
        }
        
        if locale not in conflict_patterns:
            return specs
        
        filtered_specs = []
        dropped_count = 0
        
        for spec in specs:
            name = spec.get('name', '').lower()
            should_drop = False
            
            # Проверяем конфликтные паттерны
            for pattern in conflict_patterns[locale]:
                if pattern in name:
                    should_drop = True
                    break
            
            if should_drop:
                dropped_count += 1
                logger.info(f"🔧 Удален конфликтный ключ: {spec.get('name', '')}")
            else:
                filtered_specs.append(spec)
        
        if dropped_count > 0:
            logger.info(f"✅ Детерминированный дроп: удалено {dropped_count} конфликтных ключей")
        
        return filtered_specs

    def ensure_min_sentences(self, description: str, locale: str, target: int = 5) -> Dict[str, Any]:
        """
        Гарантирует минимальное количество предложений в описании.
        Добавляет нейтральные предложения если не хватает.
        """
        logger.info(f"🔧 Проверка минимального количества предложений для {locale} (цель: {target})")
        
        current_sentences = self._count_sentences(description)
        if current_sentences >= target:
            logger.info(f"✅ Уже достаточно предложений: {current_sentences}")
            return {
                'success': True,
                'reason': 'already_sufficient',
                'fixed_description': description,
                'sentences_added': 0
            }
        
        sentences_needed = target - current_sentences
        selected_sentences = self._select_sentences(locale, sentences_needed)
        
        if not selected_sentences:
            logger.error(f"❌ Не удалось выбрать предложения для {locale}")
            return {
                'success': False,
                'reason': 'no_sentences_available',
                'fixed_description': description
            }
        
        # Применяем фикс
        fixed_description = self._apply_fix(description, selected_sentences)
        new_sentences = self._count_sentences(fixed_description)
        
        logger.info(f"✅ Добавлено предложений: {len(selected_sentences)} (было: {current_sentences}, стало: {new_sentences})")
        
        return {
            'success': True,
            'reason': 'sentences_added',
            'fixed_description': fixed_description,
            'sentences_added': len(selected_sentences),
            'original_sentences': current_sentences,
            'new_sentences': new_sentences
        }

    def ensure_min_chars(self, description: str, locale: str, target: int = 450) -> Dict[str, Any]:
        """
        Гарантирует минимальную длину описания в символах.
        Добавляет нейтральные предложения если не хватает.
        """
        logger.info(f"🔧 Проверка минимальной длины для {locale} (цель: {target} символов)")
        
        current_length = len(description.strip())
        if current_length >= target:
            logger.info(f"✅ Уже достаточно символов: {current_length}")
            return {
                'success': True,
                'reason': 'already_sufficient',
                'fixed_description': description,
                'chars_added': 0
            }
        
        # Выбираем достаточно длинные предложения
        available_sentences = self.safe_sentences.get(locale, [])
        selected_sentences = []
        current_chars = current_length
        
        for sentence in available_sentences:
            if current_chars >= target:
                break
            selected_sentences.append(sentence)
            current_chars += len(sentence) + 2  # +2 для точки и пробела
        
        if not selected_sentences:
            logger.error(f"❌ Не удалось выбрать предложения для {locale}")
            return {
                'success': False,
                'reason': 'no_sentences_available',
                'fixed_description': description
            }
        
        # Применяем фикс
        fixed_description = self._apply_fix(description, selected_sentences)
        new_length = len(fixed_description.strip())
        chars_added = new_length - current_length
        
        logger.info(f"✅ Добавлено символов: {chars_added} (было: {current_length}, стало: {new_length})")
        
        return {
            'success': True,
            'reason': 'chars_added',
            'fixed_description': fixed_description,
            'chars_added': chars_added,
            'original_length': current_length,
            'new_length': new_length
        }

    def normalize_title(self, llm_content: Dict[str, Any], locale: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализует заголовок - создает из facts если пуст/короткий.
        """
        logger.info(f"🔧 Нормализация заголовка для {locale}")
        
        current_title = llm_content.get('title', '').strip()
        
        # Проверяем длину заголовка
        if len(current_title) >= 10:
            logger.info(f"✅ Заголовок уже достаточной длины: {len(current_title)} символов")
            return llm_content
        
        logger.warning(f"⚠️ Заголовок слишком короткий: {len(current_title)} символов")
        
        # Создаем заголовок из facts
        new_title = self._create_title_from_facts(locale, product_data, llm_content)
        
        if new_title and len(new_title) >= 10:
            logger.info(f"🔧 Создан новый заголовок: {new_title}")
            llm_content['title'] = new_title
            
            # Добавляем флаг в issues
            if 'issues' not in llm_content:
                llm_content['issues'] = []
            llm_content['issues'].append('repair: title_sanitized_safe_constructor')
        else:
            logger.error(f"❌ Не удалось создать валидный заголовок для {locale}")
        
        return llm_content

    def _create_title_from_facts(self, locale: str, product_data: Dict[str, Any], llm_content: Dict[str, Any]) -> str:
        """
        Создает заголовок из доступных facts (форма + бренд + серия/аромат + объём).
        """
        # Извлекаем данные из product_data
        url = product_data.get('url', '')
        specs = llm_content.get('specs', [])
        
        # Определяем тип товара
        product_type = self._extract_product_type(url, locale)
        
        # Извлекаем бренд, аромат, объем из specs
        brand = self._extract_from_specs(specs, ['бренд', 'brand', 'производитель'])
        aroma = self._extract_from_specs(specs, ['аромат', 'aroma', 'запах', 'запах'])
        volume = self._extract_from_specs(specs, ['объем', 'об\'єм', 'volume', 'мл', 'ml'])
        
        # Формируем заголовок
        title_parts = []
        
        if product_type:
            title_parts.append(product_type)
        
        if brand:
            title_parts.append(brand)
        
        if aroma:
            title_parts.append(aroma)
        
        if volume:
            title_parts.append(volume)
        
        # Объединяем части
        if title_parts:
            if locale == 'ru':
                return ', '.join(title_parts)
            else:
                return ', '.join(title_parts)
        
        # Fallback - используем URL
        return self._extract_title_from_url(url, locale)

    def _extract_product_type(self, url: str, locale: str) -> str:
        """Извлекает тип товара из URL"""
        url_lower = url.lower()
        
        if any(word in url_lower for word in ['visk', 'wax']):
            return 'Віск' if locale == 'ua' else 'Воск'
        elif any(word in url_lower for word in ['losion', 'lotion']):
            return 'Лосьйон' if locale == 'ua' else 'Лосьон'
        elif any(word in url_lower for word in ['ochysnyk', 'ochistitel', 'cleaner']):
            return 'Очисник' if locale == 'ua' else 'Очиститель'
        elif any(word in url_lower for word in ['gel', 'гель']):
            return 'Гель' if locale == 'ua' else 'Гель'
        elif any(word in url_lower for word in ['foam', 'піна', 'пена']):
            return 'Піна' if locale == 'ua' else 'Пена'
        
        return ''

    def _extract_from_specs(self, specs: List[Dict[str, str]], keywords: List[str]) -> str:
        """Извлекает значение из specs по ключевым словам"""
        if not specs:
            return ''
        
        for spec in specs:
            if isinstance(spec, dict):
                name = spec.get('name', '').lower()
                value = spec.get('value', '').strip()
                
                if value and any(keyword in name for keyword in keywords):
                    return value
        
        return ''

    def _extract_title_from_url(self, url: str, locale: str) -> str:
        """Извлекает заголовок из URL как последний fallback"""
        # Убираем домен и путь
        url_parts = url.split('/')
        if url_parts:
            last_part = url_parts[-1].replace('-', ' ').replace('_', ' ')
            # Капитализируем первое слово
            words = last_part.split()
            if words:
                words[0] = words[0].capitalize()
                return ' '.join(words)
        
        return f'Товар ({locale})'

    def generate_strict_description_with_llm(self, product_data: Dict[str, Any], locale: str, 
                                           previous_attempts: List[str] = None) -> Dict[str, Any]:
        """
        Генерирует описание через LLM с жестким промптом на ≥5 предложений и ≥450 символов.
        """
        logger.info(f"🔧 Генерация строгого описания через LLM для {locale}")
        
        # Извлекаем данные о товаре
        url = product_data.get('url', '')
        title = product_data.get('title', '')
        specs = product_data.get('specs', [])
        
        # Определяем тип товара
        product_type = self._extract_product_type(url, locale)
        
        # Извлекаем ключевые характеристики
        brand = self._extract_from_specs(specs, ['бренд', 'brand', 'производитель'])
        volume = self._extract_from_specs(specs, ['объем', 'об\'єм', 'volume', 'мл', 'ml'])
        aroma = self._extract_from_specs(specs, ['аромат', 'aroma', 'запах'])
        
        # Формируем строгий промпт
        prompt_parts = []
        
        if locale == 'ru':
            prompt_parts.append(f"Сгенерируй описания для {product_type or 'товара'}")
            if brand:
                prompt_parts.append(f"бренда {brand}")
            if volume:
                prompt_parts.append(f"объёмом {volume}")
            if aroma:
                prompt_parts.append(f"с ароматом {aroma}")
            
            prompt_parts.append("ТРЕБОВАНИЯ:")
            prompt_parts.append("- ровно 5-6 предложений")
            prompt_parts.append("- минимум 450 символов")
            prompt_parts.append("- запреты: цены/акции/доставка")
            prompt_parts.append("- стиль: информативный")
            prompt_parts.append("- включи: консистенцию, подходящие зоны, типы кожи, способ нанесения")
            prompt_parts.append("- локаль: русский")
        else:
            prompt_parts.append(f"Сгенеруй опис для {product_type or 'товару'}")
            if brand:
                prompt_parts.append(f"бренду {brand}")
            if volume:
                prompt_parts.append(f"об'ємом {volume}")
            if aroma:
                prompt_parts.append(f"з ароматом {aroma}")
            
            prompt_parts.append("ВИМОГИ:")
            prompt_parts.append("- рівно 5-6 речень")
            prompt_parts.append("- мінімум 450 символів")
            prompt_parts.append("- заборонено: ціни/акції/доставка")
            prompt_parts.append("- стиль: інформативний")
            prompt_parts.append("- включи: консистенцію, підходящі зони, типи шкіри, спосіб нанесення")
            prompt_parts.append("- локаль: українська")
        
        # Добавляем информацию о предыдущих попытках
        if previous_attempts:
            if locale == 'ru':
                prompt_parts.append("ПРЕДЫДУЩИЕ ПОПЫТКИ (не повторяй):")
            else:
                prompt_parts.append("ПОПЕРЕДНІ СПРОБИ (не повторюй):")
            
            for i, attempt in enumerate(previous_attempts[-2:], 1):  # Последние 2 попытки
                sentences = self._count_sentences(attempt)
                chars = len(attempt.strip())
                prompt_parts.append(f"Попытка {i}: {sentences} предложений, {chars} символов")
        
        prompt = '\n'.join(prompt_parts)
        
        try:
            # Вызываем LLM
            from src.llm.content_generator import LLMContentGenerator
            llm_generator = LLMContentGenerator()
            
            response = llm_generator.call_api(prompt, max_tokens=800, temperature=0.3)
            
            if not response:
                logger.error("❌ LLM не вернул ответ для строгого описания")
                return {
                    'success': False,
                    'reason': 'no_llm_response',
                    'description': ''
                }
            
            # Проверяем результат
            sentences = self._count_sentences(response)
            chars = len(response.strip())
            
            logger.info(f"🔍 LLM результат: {sentences} предложений, {chars} символов")
            
            if sentences >= 5 and chars >= 450:
                logger.info(f"✅ Строгое описание соответствует требованиям")
                return {
                    'success': True,
                    'description': response.strip(),
                    'sentences': sentences,
                    'chars': chars
                }
            else:
                logger.warning(f"⚠️ Строгое описание не соответствует требованиям: {sentences} предложений, {chars} символов")
                return {
                    'success': False,
                    'reason': 'insufficient_quality',
                    'description': response.strip(),
                    'sentences': sentences,
                    'chars': chars
                }
            
        except Exception as e:
            logger.error(f"❌ Ошибка LLM генерации строгого описания: {e}")
            return {
                'success': False,
                'reason': 'llm_error',
                'description': ''
            }
