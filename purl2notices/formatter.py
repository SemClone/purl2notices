"""Output formatting for legal notices."""

from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader, Template

from .models import Package, License


class NoticeFormatter:
    """Format legal notices using templates."""
    
    def __init__(self, template_path: Optional[Path] = None):
        """Initialize formatter."""
        if template_path and template_path.exists():
            # Use custom template
            self.env = Environment(
                loader=FileSystemLoader(template_path.parent),
                trim_blocks=True,
                lstrip_blocks=True
            )
            self.template_name = template_path.name
        else:
            # Use default templates
            template_dir = Path(__file__).parent / "templates"
            self.env = Environment(
                loader=FileSystemLoader(template_dir),
                trim_blocks=True,
                lstrip_blocks=True
            )
            self.template_name = None
    
    def format(
        self,
        packages: List[Package],
        format_type: str = "text",
        group_by_license: bool = True,
        include_copyright: bool = True,
        include_license_text: bool = True,
        license_texts: Optional[Dict[str, str]] = None,
        custom_template: Optional[str] = None
    ) -> str:
        """
        Format packages as legal notices.
        
        Args:
            packages: List of packages to format
            format_type: Output format (text, html)
            group_by_license: Group packages by license
            include_copyright: Include copyright statements
            include_license_text: Include full license texts
            license_texts: Map of SPDX ID to license text
            custom_template: Custom template string
        
        Returns:
            Formatted legal notices
        """
        # Prepare template context
        context = {
            "packages": packages,
            "group_by_license": group_by_license,
            "include_copyright": include_copyright,
            "include_license_text": include_license_text,
            "license_texts": license_texts or {}
        }
        
        # Group packages by license if requested
        if group_by_license:
            packages_by_license = self._group_by_license(packages)
            context["packages_by_license"] = packages_by_license
            
            # Collect all license texts needed
            if include_license_text and license_texts:
                for license_id in packages_by_license.keys():
                    if license_id not in context["license_texts"]:
                        # Try to find license text from packages
                        for pkg in packages:
                            for lic in pkg.licenses:
                                if lic.spdx_id == license_id and lic.text:
                                    context["license_texts"][license_id] = lic.text
                                    break
        
        # Get template
        if custom_template:
            template = Template(custom_template)
        elif self.template_name:
            template = self.env.get_template(self.template_name)
        else:
            # Use default template based on format
            template_name = f"default.{format_type}.j2"
            template = self.env.get_template(template_name)
        
        # Render template
        return template.render(**context)
    
    def _group_by_license(self, packages: List[Package]) -> Dict[str, List[Package]]:
        """Group packages by their licenses."""
        groups = defaultdict(list)
        
        for package in packages:
            if package.licenses:
                # For packages with multiple licenses, list under combined key
                unique_licenses = list(dict.fromkeys(lic.spdx_id for lic in package.licenses))
                if len(unique_licenses) > 1:
                    license_key = ", ".join(sorted(unique_licenses))
                else:
                    license_key = unique_licenses[0]
                groups[license_key].append(package)
            # Skip packages without licenses - don't add to any group
        
        # Sort groups by license ID
        return dict(sorted(groups.items()))
    
    def format_simple(
        self,
        packages: List[Package],
        include_copyright: bool = True,
        include_license: bool = True
    ) -> str:
        """
        Simple text format without templates.
        
        Useful for quick output or debugging.
        """
        lines = []
        lines.append("=" * 80)
        lines.append("LEGAL NOTICES")
        lines.append("=" * 80)
        lines.append("")
        
        for package in packages:
            lines.append(f"Package: {package.display_name}")
            
            if include_license and package.licenses:
                license_ids = ", ".join(lic.spdx_id for lic in package.licenses)
                lines.append(f"License: {license_ids}")
            
            if include_copyright and package.copyrights:
                lines.append("Copyright:")
                for copyright in package.copyrights:
                    lines.append(f"  {copyright.statement}")
            
            lines.append("-" * 40)
            lines.append("")
        
        return "\n".join(lines)