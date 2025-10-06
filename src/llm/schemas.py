"""JSON Schema для строгой валидации LLM ответов"""

PRODUCT_CONTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Название товара на нужном языке (переведенное)"
        },
        "description": {
            "type": "object",
            "properties": {
                "paragraph_1": {
                    "type": "string",
                    "description": "Первый параграф: 3-5 предложений с характеристиками"
                },
                "paragraph_2": {
                    "type": "string",
                    "description": "Второй параграф: 3-5 предложений с преимуществами"
                }
            },
            "required": ["paragraph_1", "paragraph_2"],
            "additionalProperties": False
        },
        "characteristics": {
            "type": "array",
            "description": "ВСЕ доступные характеристики без ограничений",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"}
                },
                "required": ["label", "value"],
                "additionalProperties": False
            },
            "minItems": 2
        },
        "benefits": {
            "type": "array",
            "description": "3-6 карточек преимуществ",
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Заголовок максимум 4 слова"
                    },
                    "description": {
                        "type": "string",
                        "description": "Одно предложение пользы"
                    }
                },
                "required": ["title", "description"],
                "additionalProperties": False
            },
            "minItems": 3,
            "maxItems": 6
        },
        "faq": {
            "type": "array",
            "description": "4-6 вопросов и ответов",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"}
                },
                "required": ["question", "answer"],
                "additionalProperties": False
            },
            "minItems": 4,
            "maxItems": 6
        },
        "note_buy": {
            "type": "string",
            "description": "Коммерческая фраза с правильным падежом"
        }
    },
    "required": ["title", "description", "characteristics", "benefits", "faq", "note_buy"],
    "additionalProperties": False
}
