"""Configuration management for purl2notices."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
from platformdirs import user_config_dir, user_cache_dir


class Config:
    """Configuration management."""
    
    # Package metadata patterns for different ecosystems
    METADATA_PATTERNS: Dict[str, List[str]] = {
        "npm": ["package.json", "package-lock.json"],
        "pypi": ["setup.py", "setup.cfg", "pyproject.toml", "requirements.txt", "Pipfile"],
        "maven": ["pom.xml"],
        "gradle": ["build.gradle", "build.gradle.kts"],
        "cargo": ["Cargo.toml", "Cargo.lock"],
        "go": ["go.mod", "go.sum"],
        "gem": ["Gemfile", "Gemfile.lock", "*.gemspec"],
        "composer": ["composer.json", "composer.lock"],
        "nuget": ["*.csproj", "*.nuspec", "packages.config"],
        "cocoapods": ["Podfile", "Podfile.lock", "*.podspec"],
        "swift": ["Package.swift"],
        "hex": ["mix.exs", "mix.lock"],
    }
    
    # Archive extensions for package detection
    ARCHIVE_EXTENSIONS: List[str] = [
        ".jar", ".war", ".ear",  # Java
        ".whl", ".egg", ".tar.gz", ".tgz", ".zip",  # Python
        ".gem",  # Ruby
        ".nupkg",  # NuGet
        ".aar",  # Android
        ".deb", ".rpm",  # Linux packages
        ".tgz", ".tar.bz2", ".tar.xz",  # Generic archives
    ]
    
    # Default configuration
    DEFAULT_CONFIG = {
        "general": {
            "verbose": 0,
            "parallel_workers": 4,
            "timeout": 30,
            "continue_on_error": True,
        },
        "scanning": {
            "recursive": True,
            "max_depth": 10,
            "exclude_patterns": [
                "*/node_modules/*",
                "*/venv/*",
                "*/.venv/*",
                "*/.git/*",
                "*/vendor/*",
                "*/__pycache__/*",
                "*/dist/*",
                "*/build/*",
            ],
            "include_hidden": False,
        },
        "output": {
            "format": "text",
            "group_by_license": True,
            "include_copyright": True,
            "include_license_text": True,
            "template": None,
        },
        "cache": {
            "enabled": True,
            "location": ".purl2notices.cache.json",
            "auto_mode": True,
            "ttl": 86400,  # 24 hours
        },
        "network": {
            "retries": 3,
            "retry_delay": 1,
            "user_agent": "purl2notices/0.1.0",
        }
    }
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize configuration."""
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = config_file
        
        if config_file and config_file.exists():
            self.load_config(config_file)
    
    def load_config(self, config_file: Path) -> None:
        """Load configuration from file."""
        try:
            with open(config_file, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    self._merge_config(self.config, user_config)
        except Exception as e:
            print(f"Warning: Failed to load config from {config_file}: {e}")
    
    def _merge_config(self, base: Dict, override: Dict) -> None:
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation path."""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """Set configuration value by dot-notation path."""
        keys = key_path.split('.')
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    @property
    def cache_dir(self) -> Path:
        """Get cache directory."""
        return Path(user_cache_dir("purl2notices", "oscarvalenzuelab"))
    
    @property
    def config_dir(self) -> Path:
        """Get config directory."""
        return Path(user_config_dir("purl2notices", "oscarvalenzuelab"))
    
    def get_metadata_files(self) -> List[str]:
        """Get all metadata file patterns."""
        files = []
        for patterns in self.METADATA_PATTERNS.values():
            files.extend(patterns)
        return files