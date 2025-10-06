"""
Версионированные адаптеры парсинга
"""
from .content_model import ContentModel
from .detector import StructureDetector
from .parser_v1 import ParserV1
from .parser_v2 import ParserV2

__all__ = ['ContentModel', 'StructureDetector', 'ParserV1', 'ParserV2']


