"""Output formatting for legal notices."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader, Template

from .models import Package
from .constants import NON_OSS_INDICATORS, COMMON_OSS_PATTERNS


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
            format_type: Output format (text, html, json)
            group_by_license: Group packages by license
            include_copyright: Include copyright statements
            include_license_text: Include full license texts
            license_texts: Map of SPDX ID to license text
            custom_template: Custom template string
        
        Returns:
            Formatted legal notices
        """
        # Handle JSON format separately
        if format_type == "json":
            return self._format_json(packages, group_by_license, include_copyright, include_license_text, license_texts)
        # Filter out packages with non-OSS licenses
        oss_packages = self._filter_oss_packages(packages)
        
        # Prepare template context
        context = {
            "packages": oss_packages,
            "group_by_license": group_by_license,
            "include_copyright": include_copyright,
            "include_license_text": include_license_text,
            "license_texts": license_texts or {}
        }
        
        # Group packages by license if requested
        if group_by_license:
            packages_by_license = self._group_by_license(oss_packages)
            context["packages_by_license"] = packages_by_license
            
            # Collect all license texts needed
            if include_license_text:
                for license_key in packages_by_license.keys():
                    # For combined license keys, check each individual license
                    if ", " in license_key:
                        # Combined licenses - aggregate texts
                        combined_texts = []
                        for individual_license in license_key.split(", "):
                            if individual_license in context["license_texts"]:
                                combined_texts.append(f"\n===== {individual_license} =====\n\n{context['license_texts'][individual_license]}")
                        if combined_texts:
                            context["license_texts"][license_key] = "\n".join(combined_texts)
                    elif license_key not in context["license_texts"]:
                        # Single license - check if we have it
                        if license_texts and license_key in license_texts:
                            context["license_texts"][license_key] = license_texts[license_key]
                        else:
                            # Try to find license text from packages
                            for pkg in packages:
                                for lic in pkg.licenses:
                                    if lic.spdx_id == license_key and lic.text:
                                        context["license_texts"][license_key] = lic.text
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
    
    def _filter_oss_packages(self, packages: List[Package]) -> List[Package]:
        """Filter out packages with non-OSS licenses."""
        oss_packages = []
        
        licenses_dir = Path(__file__).parent / "data" / "licenses"
        
        # Build set of valid SPDX license IDs from files
        valid_spdx_ids = set()
        if licenses_dir.exists():
            for license_file in licenses_dir.glob("*.txt"):
                # Remove .txt extension to get license ID
                valid_spdx_ids.add(license_file.stem)
        
        # Also build lowercase mapping for case-insensitive matching
        valid_spdx_lower = {lid.lower(): lid for lid in valid_spdx_ids}
        
        for package in packages:
            # Skip packages without licenses
            if not package.licenses:
                continue
            
            # Check if any license is non-OSS
            is_non_oss = False
            for license_info in package.licenses:
                license_id = (license_info.spdx_id or license_info.name or '').lower()
                
                # Check if it's a known non-OSS license
                if license_id and any(indicator in license_id for indicator in NON_OSS_INDICATORS):
                    is_non_oss = True
                    break
                
                # Check if it's an unrecognized SPDX license
                if license_info.spdx_id:
                    # Check exact match or case-insensitive match
                    if license_info.spdx_id not in valid_spdx_ids:
                        # Try case-insensitive match
                        spdx_lower = license_info.spdx_id.lower()
                        if spdx_lower not in valid_spdx_lower:
                            # Check for common OSS license patterns without version
                            if not any(oss in spdx_lower for oss in COMMON_OSS_PATTERNS):
                                is_non_oss = True
                                break
            
            # Only include OSS packages
            if not is_non_oss:
                oss_packages.append(package)
        
        return oss_packages
    
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
    
    def _format_json(self, packages: List[Package], group_by_license: bool = True,
                     include_copyright: bool = True, include_license_text: bool = True,
                     license_texts: Optional[Dict[str, str]] = None) -> str:
        """Format packages as JSON output."""
        # Filter out non-OSS packages
        oss_packages = self._filter_oss_packages(packages)
        
        result = {
            "metadata": {
                "total_packages": len(oss_packages),
                "grouped_by_license": group_by_license,
                "includes_copyright": include_copyright,
                "includes_license_text": include_license_text
            }
        }
        
        if group_by_license:
            packages_by_license = self._group_by_license(oss_packages)
            result["licenses"] = []
            
            for license_id, pkgs in packages_by_license.items():
                license_data = {
                    "id": license_id,
                    "packages": [
                        {
                            "name": pkg.name,
                            "version": pkg.version,
                            "purl": pkg.purl,
                            "homepage": pkg.metadata.get("homepage") if pkg.metadata else None,
                            "source_path": pkg.source_path
                        }
                        for pkg in pkgs
                    ]
                }
                
                if include_copyright:
                    all_copyrights = []
                    for pkg in pkgs:
                        all_copyrights.extend([c.statement for c in pkg.copyrights])
                    license_data["copyrights"] = list(set(all_copyrights))
                
                if include_license_text and license_texts and license_id in license_texts:
                    license_data["text"] = license_texts[license_id]
                
                result["licenses"].append(license_data)
        else:
            result["packages"] = []
            for pkg in oss_packages:
                pkg_data = {
                    "name": pkg.name,
                    "version": pkg.version,
                    "purl": pkg.purl,
                    "licenses": [lic.id for lic in pkg.licenses],
                    "homepage": pkg.metadata.get("homepage") if pkg.metadata else None,
                    "source_path": pkg.source_path
                }
                
                if include_copyright:
                    pkg_data["copyrights"] = [c.statement for c in pkg.copyrights]
                
                result["packages"].append(pkg_data)
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    
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
        # Filter out non-OSS packages
        oss_packages = self._filter_oss_packages(packages)
        
        lines = []
        lines.append("=" * 80)
        lines.append("LEGAL NOTICES")
        lines.append("=" * 80)
        lines.append("")
        
        for package in oss_packages:
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