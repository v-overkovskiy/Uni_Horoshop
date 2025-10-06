"""
Шаблоны для генерации качественных ответов на базовые вопросы
"""
import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class AnswerTemplates:
    """Шаблоны для генерации качественных ответов"""
    
    def __init__(self):
        # Шаблоны для разных типов вопросов
        self.templates = {
            'volume_weight': {
                'ru': {
                    'volume': "Объём этого {product_type} составляет {value}.",
                    'weight': "Вес этого {product_type} составляет {value}.",
                    'ml': "Объём составляет {value} миллилитров.",
                    'gram': "Вес составляет {value} граммов."
                },
                'ua': {
                    'volume': "Об'єм цього {product_type} становить {value}.",
                    'weight': "Вага цього {product_type} становить {value}.",
                    'ml': "Об'єм становить {value} мілілітрів.",
                    'gram': "Вага становить {value} грамів."
                }
            },
            'storage': {
                'ru': {
                    'general': "Храните {product_type} в сухом прохладном месте при температуре не выше {max_temp}°C.",
                    'specific': "Для {product_type} рекомендуется хранение в {storage_place} при температуре {temp_range}.",
                    'refrigerator': "Храните {product_type} в холодильнике при температуре {temp_range}.",
                    'room_temp': "Храните {product_type} при комнатной температуре в сухом месте."
                },
                'ua': {
                    'general': "Зберігайте {product_type} в сухому прохолодному місці при температурі не вище {max_temp}°C.",
                    'specific': "Для {product_type} рекомендується зберігання в {storage_place} при температурі {temp_range}.",
                    'refrigerator': "Зберігайте {product_type} в холодильнику при температурі {temp_range}.",
                    'room_temp': "Зберігайте {product_type} при кімнатній температурі в сухому місці."
                }
            },
            'skin_type': {
                'ru': {
                    'sensitive': "Этот {product_type} подходит для чувствительной кожи благодаря {reason}.",
                    'all_types': "Этот {product_type} подходит для всех типов кожи, включая чувствительную.",
                    'specific': "Этот {product_type} предназначен для {skin_type} кожи.",
                    'hypoallergenic': "Этот {product_type} гипоаллергенный и подходит для чувствительной кожи."
                },
                'ua': {
                    'sensitive': "Цей {product_type} підходить для чутливої шкіри завдяки {reason}.",
                    'all_types': "Цей {product_type} підходить для всіх типів шкіри, включаючи чутливу.",
                    'specific': "Цей {product_type} призначений для {skin_type} шкіри.",
                    'hypoallergenic': "Цей {product_type} гіпоалергенний і підходить для чутливої шкіри."
                }
            },
            'usage': {
                'ru': {
                    'general': "Нанесите {product_type} на {application_area} согласно инструкции.",
                    'specific': "Для использования {product_type}: {steps}.",
                    'preparation': "Перед применением {product_type} {preparation_steps}.",
                    'frequency': "Используйте {product_type} {frequency} для достижения наилучшего результата."
                },
                'ua': {
                    'general': "Нанесіть {product_type} на {application_area} згідно з інструкцією.",
                    'specific': "Для використання {product_type}: {steps}.",
                    'preparation': "Перед застосуванням {product_type} {preparation_steps}.",
                    'frequency': "Використовуйте {product_type} {frequency} для досягнення найкращого результату."
                }
            },
            'safety': {
                'ru': {
                    'general': "Этот {product_type} безопасен при правильном использовании.",
                    'hypoallergenic': "Этот {product_type} гипоаллергенный и не содержит агрессивных компонентов.",
                    'tested': "Этот {product_type} прошел дерматологические тесты и безопасен для кожи.",
                    'natural': "Этот {product_type} содержит натуральные компоненты и безопасен для использования."
                },
                'ua': {
                    'general': "Цей {product_type} безпечний при правильному використанні.",
                    'hypoallergenic': "Цей {product_type} гіпоалергенний і не містить агресивних компонентів.",
                    'tested': "Цей {product_type} пройшов дерматологічні тести і безпечний для шкіри.",
                    'natural': "Цей {product_type} містить натуральні компоненти і безпечний для використання."
                }
            }
        }
        
        # Извлечение данных из specs
        self.spec_extractors = {
            'volume': {
                'ru': [r'объ[её]м', r'мл', r'литр', r'л'],
                'ua': [r'об\'[еє]м', r'мл', r'л[іи]тр', r'л']
            },
            'weight': {
                'ru': [r'вес', r'грамм', r'г', r'кг', r'килограмм'],
                'ua': [r'вага', r'грам', r'г', r'кг', r'к[іи]лограм']
            },
            'brand': {
                'ru': [r'бренд', r'производитель', r'марка'],
                'ua': [r'бренд', r'виробник', r'марка']
            }
        }

    def extract_product_info(self, specs: List[Dict[str, str]], locale: str) -> Dict[str, Any]:
        """
        Извлекает информацию о продукте из specs
        
        Args:
            specs: Список характеристик
            locale: Локаль
            
        Returns:
            Словарь с информацией о продукте
        """
        info = {
            'product_type': 'продукт' if locale == 'ru' else 'продукт',
            'volume': None,
            'weight': None,
            'brand': None,
            'max_temp': '25',
            'storage_place': 'сухом прохладном месте' if locale == 'ru' else 'сухому прохолодному місці',
            'temp_range': '15-25°C' if locale == 'ru' else '15-25°C'
        }
        
        for spec in specs:
            if not isinstance(spec, dict):
                continue
                
            name = spec.get('name', '').lower()
            value = spec.get('value', '').strip()
            
            if not value:
                continue
            
            # Определяем тип продукта по названию
            if any(word in name for word in ['тип', 'вид', 'название']):
                info['product_type'] = value
            
            # Извлекаем объем
            if any(pattern in name for pattern in self.spec_extractors['volume'][locale]):
                info['volume'] = value
            
            # Извлекаем вес
            if any(pattern in name for pattern in self.spec_extractors['weight'][locale]):
                info['weight'] = value
            
            # Извлекаем бренд
            if any(pattern in name for pattern in self.spec_extractors['brand'][locale]):
                info['brand'] = value
        
        return info

    def generate_volume_answer(self, question: str, specs: List[Dict[str, str]], locale: str) -> Optional[str]:
        """Генерирует ответ на вопрос об объеме/весе"""
        info = self.extract_product_info(specs, locale)
        
        if info['volume']:
            template = self.templates['volume_weight'][locale]['volume']
            return template.format(
                product_type=info['product_type'],
                value=info['volume']
            )
        elif info['weight']:
            template = self.templates['volume_weight'][locale]['weight']
            return template.format(
                product_type=info['product_type'],
                value=info['weight']
            )
        
        return None

    def generate_storage_answer(self, question: str, specs: List[Dict[str, str]], locale: str) -> Optional[str]:
        """Генерирует ответ на вопрос о хранении"""
        info = self.extract_product_info(specs, locale)
        
        # Определяем тип продукта для выбора подходящего шаблона
        product_type = info['product_type'].lower()
        
        if any(word in product_type for word in ['воск', 'віск', 'wax']):
            template = self.templates['storage'][locale]['room_temp']
        elif any(word in product_type for word in ['крем', 'крем', 'cream']):
            template = self.templates['storage'][locale]['general']
        else:
            template = self.templates['storage'][locale]['general']
        
        return template.format(
            product_type=info['product_type'],
            max_temp=info['max_temp'],
            storage_place=info['storage_place'],
            temp_range=info['temp_range']
        )

    def generate_skin_type_answer(self, question: str, specs: List[Dict[str, str]], locale: str) -> Optional[str]:
        """Генерирует ответ на вопрос о типе кожи"""
        info = self.extract_product_info(specs, locale)
        
        # Определяем подходящий шаблон на основе вопроса
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['чувствительная', 'чутлива', 'sensitive']):
            template = self.templates['skin_type'][locale]['sensitive']
            reason = 'мягким составом' if locale == 'ru' else 'м\'яким складом'
        elif any(word in question_lower for word in ['гипоаллергенный', 'гіпоалергенний', 'hypoallergenic']):
            template = self.templates['skin_type'][locale]['hypoallergenic']
        else:
            template = self.templates['skin_type'][locale]['all_types']
            reason = ''
        
        if 'reason' in template:
            return template.format(
                product_type=info['product_type'],
                reason=reason
            )
        else:
            return template.format(
                product_type=info['product_type']
            )

    def generate_usage_answer(self, question: str, specs: List[Dict[str, str]], locale: str) -> Optional[str]:
        """Генерирует ответ на вопрос об использовании"""
        info = self.extract_product_info(specs, locale)
        
        # Определяем область применения на основе типа продукта
        product_type = info['product_type'].lower()
        
        if any(word in product_type for word in ['воск', 'віск', 'wax']):
            application_area = 'очищенную кожу' if locale == 'ru' else 'очищену шкіру'
            steps = 'очистите кожу, нанесите воск, удалите полоской' if locale == 'ru' else 'очистіть шкіру, нанесіть віск, видаліть смужкою'
        elif any(word in product_type for word in ['крем', 'крем', 'cream']):
            application_area = 'кожу' if locale == 'ru' else 'шкіру'
            steps = 'нанесите на кожу, массируйте до впитывания' if locale == 'ru' else 'нанесіть на шкіру, масажуйте до впитування'
        else:
            application_area = 'кожу' if locale == 'ru' else 'шкіру'
            steps = 'следуйте инструкции на упаковке' if locale == 'ru' else 'дотримуйтесь інструкції на упаковці'
        
        template = self.templates['usage'][locale]['specific']
        return template.format(
            product_type=info['product_type'],
            steps=steps
        )

    def generate_safety_answer(self, question: str, specs: List[Dict[str, str]], locale: str) -> Optional[str]:
        """Генерирует ответ на вопрос о безопасности"""
        info = self.extract_product_info(specs, locale)
        
        # Определяем подходящий шаблон
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['гипоаллергенный', 'гіпоалергенний', 'hypoallergenic']):
            template = self.templates['safety'][locale]['hypoallergenic']
        elif any(word in question_lower for word in ['натуральный', 'натуральний', 'natural']):
            template = self.templates['safety'][locale]['natural']
        elif any(word in question_lower for word in ['тестированный', 'тестований', 'tested']):
            template = self.templates['safety'][locale]['tested']
        else:
            template = self.templates['safety'][locale]['general']
        
        return template.format(
            product_type=info['product_type']
        )

    def generate_quality_answer(self, question: str, specs: List[Dict[str, str]], locale: str) -> Optional[str]:
        """
        Генерирует качественный ответ на вопрос
        
        Args:
            question: Текст вопроса
            specs: Характеристики товара
            locale: Локаль
            
        Returns:
            Сгенерированный ответ или None
        """
        question_lower = question.lower()
        
        # Определяем тип вопроса и генерируем соответствующий ответ
        if any(word in question_lower for word in ['объём', 'об\'єм', 'мл', 'литр', 'л']):
            return self.generate_volume_answer(question, specs, locale)
        elif any(word in question_lower for word in ['вес', 'вага', 'грамм', 'грам', 'кг']):
            return self.generate_volume_answer(question, specs, locale)
        elif any(word in question_lower for word in ['хранить', 'збер[іи]гати', 'хранение', 'збер[іи]гання']):
            return self.generate_storage_answer(question, specs, locale)
        elif any(word in question_lower for word in ['кожа', 'шк[іи]ра', 'тип', 'подходит', 'підходить']):
            return self.generate_skin_type_answer(question, specs, locale)
        elif any(word in question_lower for word in ['использовать', 'використовувати', 'применять', 'застосовувати']):
            return self.generate_usage_answer(question, specs, locale)
        elif any(word in question_lower for word in ['безопасен', 'безпечний', 'безопасность', 'безпека']):
            return self.generate_safety_answer(question, specs, locale)
        
        return None
