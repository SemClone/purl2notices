#!/usr/bin/env python3
"""Download SPDX license texts for bundling with the package."""

import json
import requests
from pathlib import Path
from typing import Dict, List


def download_spdx_licenses() -> None:
    """Download SPDX license list and texts."""
    print("Downloading SPDX license data...")
    
    # URLs for SPDX data
    LICENSE_LIST_URL = "https://raw.githubusercontent.com/spdx/license-list-data/main/json/licenses.json"
    LICENSE_TEXT_BASE = "https://raw.githubusercontent.com/spdx/license-list-data/main/text/"
    
    # Create output directory
    output_dir = Path(__file__).parent.parent / "purl2notices" / "data" / "licenses"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download license list
    print("Fetching license list...")
    response = requests.get(LICENSE_LIST_URL)
    response.raise_for_status()
    license_data = response.json()
    
    # Save license metadata
    metadata_file = output_dir / "spdx_licenses.json"
    with open(metadata_file, 'w') as f:
        json.dump(license_data, f, indent=2)
    
    print(f"Found {len(license_data['licenses'])} licenses")
    
    # Download common license texts
    common_licenses = [
        "MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "GPL-2.0-only",
        "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later", "LGPL-2.1-only",
        "LGPL-2.1-or-later", "LGPL-3.0-only", "LGPL-3.0-or-later", "ISC",
        "MPL-2.0", "CC0-1.0", "Unlicense", "AGPL-3.0-only", "AGPL-3.0-or-later",
        "EPL-1.0", "EPL-2.0", "CC-BY-4.0", "CC-BY-SA-4.0", "BSD-4-Clause",
        "0BSD", "Zlib", "WTFPL", "PostgreSQL", "Python-2.0", "PHP-3.0",
        "Ruby", "Artistic-2.0", "BSL-1.0", "AFL-3.0", "MS-PL", "MS-RL"
    ]
    
    print(f"Downloading texts for {len(common_licenses)} common licenses...")
    
    downloaded = 0
    failed = []
    
    for license_id in common_licenses:
        try:
            # Find license in metadata
            license_info = next(
                (lic for lic in license_data['licenses'] if lic['licenseId'] == license_id),
                None
            )
            
            if not license_info:
                print(f"  Warning: {license_id} not found in SPDX list")
                continue
            
            # Download license text
            text_url = f"{LICENSE_TEXT_BASE}{license_id}.txt"
            response = requests.get(text_url)
            response.raise_for_status()
            
            # Save license text
            text_file = output_dir / f"{license_id}.txt"
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            downloaded += 1
            print(f"  Downloaded: {license_id}")
            
        except Exception as e:
            print(f"  Failed to download {license_id}: {e}")
            failed.append(license_id)
    
    print(f"\nDownloaded {downloaded} license texts")
    if failed:
        print(f"Failed to download: {', '.join(failed)}")
    
    # Create a summary file
    summary = {
        "total_licenses": len(license_data['licenses']),
        "downloaded": downloaded,
        "common_licenses": common_licenses,
        "failed": failed
    }
    
    summary_file = output_dir / "download_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\nLicense data saved to: {output_dir}")


if __name__ == "__main__":
    download_spdx_licenses()