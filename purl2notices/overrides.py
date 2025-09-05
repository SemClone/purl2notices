"""User overrides and preferences management."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class OverrideManager:
    """Manages user overrides for package data."""
    
    def __init__(self, override_file: Optional[Path] = None):
        """Initialize override manager."""
        self.override_file = override_file or Path("purl2notices.overrides.json")
        self.overrides = self._load_overrides()
    
    def _load_overrides(self) -> Dict[str, Any]:
        """Load overrides from file."""
        if not self.override_file.exists():
            return {
                "version": "1.0",
                "disabled_copyrights": {},  # purl -> list of disabled copyright strings
                "disabled_licenses": {},    # purl -> list of disabled license ids
                "custom_copyrights": {},    # purl -> list of custom copyright strings to add
                "custom_licenses": {},      # purl -> dict of custom license data
                "package_disabled": []      # list of purls to completely exclude
            }
        
        try:
            with open(self.override_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load overrides from {self.override_file}: {e}")
            return {}
    
    def save_overrides(self) -> None:
        """Save overrides to file."""
        try:
            with open(self.override_file, 'w') as f:
                json.dump(self.overrides, f, indent=2, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to save overrides to {self.override_file}: {e}")
    
    def is_package_disabled(self, purl: str) -> bool:
        """Check if a package is disabled."""
        return purl in self.overrides.get("package_disabled", [])
    
    def disable_package(self, purl: str) -> None:
        """Disable a package completely."""
        if "package_disabled" not in self.overrides:
            self.overrides["package_disabled"] = []
        if purl not in self.overrides["package_disabled"]:
            self.overrides["package_disabled"].append(purl)
            self.save_overrides()
    
    def enable_package(self, purl: str) -> None:
        """Enable a previously disabled package."""
        if "package_disabled" in self.overrides and purl in self.overrides["package_disabled"]:
            self.overrides["package_disabled"].remove(purl)
            self.save_overrides()
    
    def get_disabled_copyrights(self, purl: str) -> List[str]:
        """Get list of disabled copyright strings for a package."""
        return self.overrides.get("disabled_copyrights", {}).get(purl, [])
    
    def disable_copyright(self, purl: str, copyright_text: str) -> None:
        """Disable a specific copyright string for a package."""
        if "disabled_copyrights" not in self.overrides:
            self.overrides["disabled_copyrights"] = {}
        if purl not in self.overrides["disabled_copyrights"]:
            self.overrides["disabled_copyrights"][purl] = []
        if copyright_text not in self.overrides["disabled_copyrights"][purl]:
            self.overrides["disabled_copyrights"][purl].append(copyright_text)
            self.save_overrides()
    
    def enable_copyright(self, purl: str, copyright_text: str) -> None:
        """Enable a previously disabled copyright string."""
        if "disabled_copyrights" in self.overrides and purl in self.overrides["disabled_copyrights"]:
            if copyright_text in self.overrides["disabled_copyrights"][purl]:
                self.overrides["disabled_copyrights"][purl].remove(copyright_text)
                if not self.overrides["disabled_copyrights"][purl]:
                    del self.overrides["disabled_copyrights"][purl]
                self.save_overrides()
    
    def get_disabled_licenses(self, purl: str) -> List[str]:
        """Get list of disabled license IDs for a package."""
        return self.overrides.get("disabled_licenses", {}).get(purl, [])
    
    def disable_license(self, purl: str, license_id: str) -> None:
        """Disable a specific license for a package."""
        if "disabled_licenses" not in self.overrides:
            self.overrides["disabled_licenses"] = {}
        if purl not in self.overrides["disabled_licenses"]:
            self.overrides["disabled_licenses"][purl] = []
        if license_id not in self.overrides["disabled_licenses"][purl]:
            self.overrides["disabled_licenses"][purl].append(license_id)
            self.save_overrides()
    
    def enable_license(self, purl: str, license_id: str) -> None:
        """Enable a previously disabled license."""
        if "disabled_licenses" in self.overrides and purl in self.overrides["disabled_licenses"]:
            if license_id in self.overrides["disabled_licenses"][purl]:
                self.overrides["disabled_licenses"][purl].remove(license_id)
                if not self.overrides["disabled_licenses"][purl]:
                    del self.overrides["disabled_licenses"][purl]
                self.save_overrides()
    
    def get_custom_copyrights(self, purl: str) -> List[str]:
        """Get list of custom copyright strings for a package."""
        return self.overrides.get("custom_copyrights", {}).get(purl, [])
    
    def add_custom_copyright(self, purl: str, copyright_text: str) -> None:
        """Add a custom copyright string for a package."""
        if "custom_copyrights" not in self.overrides:
            self.overrides["custom_copyrights"] = {}
        if purl not in self.overrides["custom_copyrights"]:
            self.overrides["custom_copyrights"][purl] = []
        if copyright_text not in self.overrides["custom_copyrights"][purl]:
            self.overrides["custom_copyrights"][purl].append(copyright_text)
            self.save_overrides()
    
    def get_custom_licenses(self, purl: str) -> Dict[str, Any]:
        """Get custom license data for a package."""
        return self.overrides.get("custom_licenses", {}).get(purl, {})
    
    def add_custom_license(self, purl: str, license_id: str, license_text: Optional[str] = None) -> None:
        """Add a custom license for a package."""
        if "custom_licenses" not in self.overrides:
            self.overrides["custom_licenses"] = {}
        if purl not in self.overrides["custom_licenses"]:
            self.overrides["custom_licenses"][purl] = {}
        
        self.overrides["custom_licenses"][purl][license_id] = {
            "id": license_id,
            "text": license_text
        }
        self.save_overrides()
    
    def apply_overrides_to_cache(self, cache_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply overrides to cache data."""
        if "components" not in cache_data:
            return cache_data
        
        filtered_components = []
        
        for component in cache_data["components"]:
            purl = component.get("purl", "")
            
            # Skip disabled packages
            if self.is_package_disabled(purl):
                logger.debug(f"Skipping disabled package: {purl}")
                continue
            
            # Filter disabled copyrights
            disabled_copyrights = self.get_disabled_copyrights(purl)
            if disabled_copyrights and "properties" in component:
                component["properties"] = [
                    prop for prop in component["properties"]
                    if prop.get("name") != "copyright" or prop.get("value") not in disabled_copyrights
                ]
            
            # Add custom copyrights
            custom_copyrights = self.get_custom_copyrights(purl)
            if custom_copyrights:
                if "properties" not in component:
                    component["properties"] = []
                for copyright_text in custom_copyrights:
                    component["properties"].append({
                        "name": "copyright",
                        "value": copyright_text
                    })
            
            # Filter disabled licenses
            disabled_licenses = self.get_disabled_licenses(purl)
            if disabled_licenses and "licenses" in component:
                component["licenses"] = [
                    lic for lic in component["licenses"]
                    if lic.get("license", {}).get("id") not in disabled_licenses
                ]
            
            # Add custom licenses
            custom_licenses = self.get_custom_licenses(purl)
            if custom_licenses:
                if "licenses" not in component:
                    component["licenses"] = []
                for license_id, license_data in custom_licenses.items():
                    component["licenses"].append({
                        "license": {"id": license_id}
                    })
                    # Add license text if provided
                    if license_data.get("text") and "properties" in component:
                        component["properties"].append({
                            "name": f"purl2notices:license_text:{license_id}",
                            "value": license_data["text"]
                        })
            
            filtered_components.append(component)
        
        cache_data["components"] = filtered_components
        return cache_data