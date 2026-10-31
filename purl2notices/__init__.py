"""purl2notices - Generate legal notices for software packages."""

# The one place the version is written. pyproject.toml reads it from here
# (project.dynamic), and the cache BOM records it as the producing tool, so
# a release bumps this line and nothing else can disagree with it.
__version__ = "2.0.0"
__author__ = "Oscar Valenzuela B"
__email__ = "oscar.valenzuela.b@gmail.com"

from .core import Purl2Notices
from .models import Package, License, Copyright

__all__ = ["Purl2Notices", "Package", "License", "Copyright"]