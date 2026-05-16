from .base import BaseParser, detectar_banco, validar_dataframe
from .generico import GenericoParser
from .nubank import NubankParser
from .santander import SantanderParser

__all__ = [
    "BaseParser",
    "GenericoParser",
    "NubankParser",
    "SantanderParser",
    "detectar_banco",
    "validar_dataframe",
]