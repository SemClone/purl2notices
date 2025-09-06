"""Cache management using CycloneDX format."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import Package, License, Copyright, ProcessingStatus
from .overrides import OverrideManager
from .constants import CACHE_FORMAT, CACHE_SPEC_VERSION

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage cache in CycloneDX format."""
    
    def __init__(self, cache_file: Path, override_file: Optional[Path] = None):
        """Initialize cache manager."""
        self.cache_file = cache_file
        self.bom_ref = str(uuid.uuid4())
        self.override_manager = OverrideManager(override_file)
    
    def load(self, apply_overrides: bool = True) -> List[Package]:
        """Load packages from cache and apply overrides."""
        if not self.cache_file.exists():
            return []
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            if data.get('bomFormat') != CACHE_FORMAT:
                raise ValueError("Invalid cache format: not a CycloneDX BOM")
            
            packages = self._parse_cyclonedx(data)
            
            # Apply overrides if enabled
            if apply_overrides and self.override_manager.override_file.exists():
                packages = self.override_manager.apply_overrides(packages)
            
            return packages
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            return []
    
    def save(self, packages: List[Package], apply_overrides: bool = True) -> None:
        """Save packages to cache, merging with existing cache if present."""
        try:
            # If cache file exists, merge with existing packages
            if self.cache_file.exists():
                packages = self.merge(packages)
            
            bom = self._create_cyclonedx(packages)
            
            # Apply user overrides if enabled
            if apply_overrides:
                bom = self.override_manager.apply_overrides_to_cache(bom)
            
            # Ensure directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w') as f:
                json.dump(bom, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def merge(self, packages: List[Package]) -> List[Package]:
        """Merge new packages with cached ones, preserving user overrides."""
        cached = self.load()
        
        # Create a map of cached packages by PURL/display_name
        cache_map = {pkg.purl or pkg.display_name: pkg for pkg in cached}
        
        # Merge with intelligent handling of overrides
        for pkg in packages:
            key = pkg.purl or pkg.display_name
            
            # If package is marked as disabled, skip it
            if pkg.purl and self.override_manager.is_package_disabled(pkg.purl):
                continue
            
            # If package exists in cache, merge intelligently
            if key in cache_map:
                cached_pkg = cache_map[key]
                # Preserve user overrides from cached version
                self._merge_package(cached_pkg, pkg)
                cache_map[key] = cached_pkg
            else:
                cache_map[key] = pkg
        
        return list(cache_map.values())
    
    def _merge_package(self, cached: Package, new: Package) -> None:
        """Merge new package data into cached, preserving overrides."""
        # Update basic fields from new data
        if new.version:
            cached.version = new.version
        if new.source_path:
            cached.source_path = new.source_path
        
        # Merge licenses - keep disabled ones marked
        if cached.purl:
            disabled_licenses = self.override_manager.get_disabled_licenses(cached.purl)
            # Filter out disabled licenses from new data
            new_licenses = [lic for lic in new.licenses 
                          if lic.spdx_id not in disabled_licenses]
            # Add new licenses not in cached
            cached_license_ids = {lic.spdx_id for lic in cached.licenses}
            for lic in new_licenses:
                if lic.spdx_id not in cached_license_ids:
                    cached.licenses.append(lic)
        else:
            cached.licenses = new.licenses
        
        # Merge copyrights - keep disabled ones marked
        if cached.purl:
            disabled_copyrights = self.override_manager.get_disabled_copyrights(cached.purl)
            # Filter out disabled copyrights from new data
            new_copyrights = [cp for cp in new.copyrights 
                            if cp.statement not in disabled_copyrights]
            # Add new copyrights not in cached
            cached_copyright_stmts = {cp.statement for cp in cached.copyrights}
            for cp in new_copyrights:
                if cp.statement not in cached_copyright_stmts:
                    cached.copyrights.append(cp)
        else:
            cached.copyrights = new.copyrights
        
        # Update status only if new has better info
        if new.status == ProcessingStatus.SUCCESS:
            cached.status = new.status
            cached.error_message = None
        elif cached.status != ProcessingStatus.SUCCESS:
            cached.status = new.status
            cached.error_message = new.error_message
    
    def _create_cyclonedx(self, packages: List[Package]) -> Dict[str, Any]:
        """Create CycloneDX BOM from packages."""
        components = []
        
        for pkg in packages:
            component = {
                "type": "library",
                "bom-ref": str(uuid.uuid4()),
                "name": pkg.name or "unknown",
            }
            
            if pkg.version:
                component["version"] = pkg.version
            
            if pkg.purl:
                component["purl"] = pkg.purl
            
            # Add licenses
            if pkg.licenses:
                component["licenses"] = []
                for lic in pkg.licenses:
                    license_obj = {}
                    if lic.spdx_id and lic.spdx_id != "NOASSERTION":
                        license_obj["license"] = {"id": lic.spdx_id}
                    else:
                        license_obj["license"] = {"name": lic.name}
                    component["licenses"].append(license_obj)
            
            # Add copyright as property
            if pkg.copyrights:
                if "properties" not in component:
                    component["properties"] = []
                
                for copyright in pkg.copyrights:
                    component["properties"].append({
                        "name": "copyright",
                        "value": copyright.statement
                    })
            
            # Add custom properties for our needs
            if "properties" not in component:
                component["properties"] = []
            
            # Add status
            component["properties"].append({
                "name": "purl2notices:status",
                "value": pkg.status.value
            })
            
            # Add source path if available
            if pkg.source_path:
                component["properties"].append({
                    "name": "purl2notices:source_path",
                    "value": pkg.source_path
                })
            
            # Add error message if any
            if pkg.error_message:
                component["properties"].append({
                    "name": "purl2notices:error",
                    "value": pkg.error_message
                })
            
            # Store license texts separately
            for lic in pkg.licenses:
                if lic.text:
                    component["properties"].append({
                        "name": f"purl2notices:license_text:{lic.spdx_id}",
                        "value": lic.text
                    })
            
            components.append(component)
        
        # Create the BOM
        bom = {
            "bomFormat": CACHE_FORMAT,
            "specVersion": CACHE_SPEC_VERSION,
            "serialNumber": f"urn:uuid:{self.bom_ref}",
            "version": 1,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tools": [
                    {
                        "vendor": "oscarvalenzuelab",
                        "name": "purl2notices",
                        "version": "0.1.0"
                    }
                ],
                "properties": [
                    {
                        "name": "purl2notices:cache_version",
                        "value": "1.0"
                    }
                ]
            },
            "components": components
        }
        
        return bom
    
    def _parse_cyclonedx(self, data: Dict[str, Any]) -> List[Package]:
        """Parse CycloneDX BOM to packages."""
        packages = []
        
        for component in data.get("components", []):
            pkg = Package(
                purl=component.get("purl"),
                name=component.get("name", ""),
                version=component.get("version", "")
            )
            
            # Extract type from PURL if available
            if pkg.purl and pkg.purl.startswith("pkg:"):
                pkg.type = pkg.purl.split("/")[0].replace("pkg:", "")
            
            # Parse licenses
            for lic_obj in component.get("licenses", []):
                license_data = lic_obj.get("license", {})
                
                spdx_id = license_data.get("id", "")
                name = license_data.get("name", "")
                
                if spdx_id or name:
                    license = License(
                        spdx_id=spdx_id or "NOASSERTION",
                        name=name or spdx_id,
                        text="",  # Will be loaded from properties
                        source="cache"
                    )
                    pkg.licenses.append(license)
            
            # Parse properties
            for prop in component.get("properties", []):
                prop_name = prop.get("name", "")
                prop_value = prop.get("value", "")
                
                if prop_name == "copyright":
                    pkg.copyrights.append(Copyright(statement=prop_value))
                elif prop_name == "purl2notices:status":
                    try:
                        pkg.status = ProcessingStatus(prop_value)
                    except ValueError:
                        pkg.status = ProcessingStatus.SUCCESS
                elif prop_name == "purl2notices:source_path":
                    pkg.source_path = prop_value
                elif prop_name == "purl2notices:error":
                    pkg.error_message = prop_value
                elif prop_name.startswith("purl2notices:license_text:"):
                    # Match license text to license
                    spdx_id = prop_name.replace("purl2notices:license_text:", "")
                    for lic in pkg.licenses:
                        if lic.spdx_id == spdx_id:
                            lic.text = prop_value
                            break
            
            packages.append(pkg)
        
        return packages