"""Validators for purl2notices."""

import re
from pathlib import Path
from typing import List, Optional, Tuple
from packageurl import PackageURL


class PurlValidator:
    """Validate Package URLs according to the spec."""
    
    @staticmethod
    def validate(purl_string: str) -> Tuple[bool, Optional[str], Optional[PackageURL]]:
        """
        Validate a PURL string.
        
        Returns:
            Tuple of (is_valid, error_message, parsed_purl)
        """
        if not purl_string or not purl_string.strip():
            return False, "Empty PURL string", None
        
        try:
            # PackageURL will validate according to the spec
            parsed = PackageURL.from_string(purl_string.strip())
            
            # Additional validation
            if not parsed.type:
                return False, "PURL must have a type", None
            
            if not parsed.name:
                return False, "PURL must have a name", None
            
            return True, None, parsed
            
        except Exception as e:
            return False, str(e), None
    
    @staticmethod
    def validate_batch(purl_strings: List[str]) -> List[Tuple[str, bool, Optional[str]]]:
        """
        Validate multiple PURL strings.
        
        Returns:
            List of tuples (purl_string, is_valid, error_message)
        """
        results = []
        for purl in purl_strings:
            is_valid, error, _ = PurlValidator.validate(purl)
            results.append((purl, is_valid, error))
        return results


class FileValidator:
    """Validate input files."""
    
    @staticmethod
    def validate_kissbom(file_path: Path) -> Tuple[bool, Optional[str], List[str]]:
        """
        Validate a KissBOM file.
        
        Returns:
            Tuple of (is_valid, error_message, purl_list)
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}", []
        
        if not file_path.is_file():
            return False, f"Not a file: {file_path}", []
        
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            purls = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Basic PURL format check
                if not line.startswith('pkg:'):
                    return False, f"Line {line_num}: Invalid PURL format (must start with 'pkg:')", []
                
                purls.append(line)
            
            if not purls:
                return False, "No PURLs found in file", []
            
            return True, None, purls
            
        except Exception as e:
            return False, f"Error reading file: {e}", []
    
    @staticmethod
    def is_cache_file(file_path: Path) -> bool:
        """Check if a file is a CycloneDX cache file."""
        if not file_path.exists() or not file_path.is_file():
            return False
        
        # Check by extension
        if file_path.suffix in ['.json', '.cdx.json']:
            try:
                import json
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # Check for CycloneDX structure
                    return 'bomFormat' in data and data['bomFormat'] == 'CycloneDX'
            except:
                pass
        
        return False
    
    @staticmethod
    def detect_input_type(input_path: str) -> str:
        """
        Detect the type of input.
        
        Returns one of: 'purl', 'kissbom', 'cache', 'directory', 'unknown'
        """
        # Check if it's a PURL
        if input_path.startswith('pkg:'):
            return 'purl'
        
        path = Path(input_path)
        
        # Check if it's a directory
        if path.is_dir():
            return 'directory'
        
        # Check if it's a file
        if path.is_file():
            # Check if it's a cache file
            if FileValidator.is_cache_file(path):
                return 'cache'
            
            # Check if it's a KissBOM file
            is_valid, _, _ = FileValidator.validate_kissbom(path)
            if is_valid:
                return 'kissbom'
        
        return 'unknown'