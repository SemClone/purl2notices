"""purl2notices - Generate legal notices for software packages."""

__version__ = "1.1.6"
__author__ = "Oscar Valenzuela B"
__email__ = "oscar.valenzuela.b@gmail.com"

from .core import Purl2Notices
from .models import Package, License, Copyright

__all__ = ["Purl2Notices", "Package", "License", "Copyright"]