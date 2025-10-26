"""
Конфигурация LSI Enhancement
"""

# Флаг включения/выключения LSI Enhancement
USE_LSI_ENHANCEMENT = False  # ⚠️ ВЫКЛЮЧЕН - добавляет 4x времени обработки

# Режим LSI
LSI_MODE = "integrated"  # "integrated" - в основном промпте, "separate" - отдельные вызовы

# Конфигурация для separate режима
LSI_SEPARATE_CONFIG = {
    "enabled": False,
    "generate_keywords": True,  # Генерировать ключи
    "inject_description": True,  # Инъекция в описание
    "inject_advantages": False,  # Инъекция в преимущества (выключено - экономия времени)
    "max_keywords": 15,
    "min_keywords": 5
}

# Конфигурация для integrated режима
LSI_INTEGRATED_CONFIG = {
    "enabled": True,  # Включен по умолчанию - нет дополнительного времени
    "instruction_level": "strong",  # "light", "medium", "strong"
    "examples_count": 3  # Сколько примеров LSI-ключей показывать в промпте
}

# Примеры LSI-ключей по категориям (для промпта)
LSI_EXAMPLES = {
    "ru": {
        "йога": "йога-мат, асаны, пилатес, медитация",
        "косметика": "уход за кожей, красота, процедуры, косметолог",
        "фитнес": "тренировки, упражнения, спорт, активный образ жизни",
        "туризм": "кемпинг, походы, outdoor, активный отдых"
    },
    "ua": {
        "йога": "йога-мат, асани, пілатес, медитація",
        "косметика": "догляд за шкірою, краса, процедури, косметолог",
        "фітнес": "тренування, вправи, спорт, активний спосіб життя",
        "туризм": "кемпінг, походи, outdoor, активний відпочинок"
    }
}

def get_lsi_mode():
    """Возвращает текущий режим LSI"""
    if not USE_LSI_ENHANCEMENT:
        return "disabled"
    return LSI_MODE

def is_lsi_enabled():
    """Проверяет, включен ли LSI"""
    if LSI_MODE == "integrated":
        return LSI_INTEGRATED_CONFIG["enabled"]
    elif LSI_MODE == "separate":
        return LSI_SEPARATE_CONFIG["enabled"]
    return False




