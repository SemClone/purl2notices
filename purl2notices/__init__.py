"""purl2notices - Generate legal notices for software packages."""

__version__ = "0.1.0"
__author__ = "Oscar Valenzuela B"
__email__ = "oscar.valenzuela.b@gmail.com"

try:
    from .core import Purl2Notices
except ImportError:
    # If old core fails to import, use the new one
    from .core_v2 import Purl2NoticesV2 as Purl2Notices
from .models import Package, License, Copyright

__all__ = ["Purl2Notices", "Package", "License", "Copyright"]