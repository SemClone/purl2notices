#!/usr/bin/env python3
"""Download all SPDX license texts."""

import json
import os
import sys
from pathlib import Path
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def download_license(license_id: str, details_url: str, output_dir: Path) -> tuple:
    """Download a single license text."""
    try:
        # Get license details
        response = requests.get(details_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Get the license text
        license_text = data.get('licenseText', '')
        if not license_text:
            # Try standardLicenseTemplate as fallback
            license_text = data.get('standardLicenseTemplate', '')
        
        if license_text:
            # Save to file
            output_file = output_dir / f"{license_id}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(license_text)
            return (license_id, 'success', len(license_text))
        else:
            return (license_id, 'no_text', 0)
    except Exception as e:
        return (license_id, f'error: {e}', 0)

def main():
    # Setup paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    licenses_dir = project_root / 'purl2notices' / 'data' / 'licenses'
    licenses_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading SPDX licenses to: {licenses_dir}")
    
    # Get the SPDX license list
    print("Fetching SPDX license list...")
    response = requests.get('https://spdx.org/licenses/licenses.json')
    response.raise_for_status()
    spdx_data = response.json()
    
    licenses = spdx_data.get('licenses', [])
    print(f"Found {len(licenses)} SPDX licenses")
    
    # Prepare download tasks
    download_tasks = []
    for license_info in licenses:
        license_id = license_info.get('licenseId')
        details_url = license_info.get('detailsUrl')
        
        if license_id and details_url:
            # Skip if already downloaded
            if (licenses_dir / f"{license_id}.txt").exists():
                continue
            download_tasks.append((license_id, details_url))
    
    print(f"Need to download {len(download_tasks)} licenses")
    
    if not download_tasks:
        print("All licenses already downloaded!")
        return
    
    # Download licenses in parallel
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(download_license, lid, url, licenses_dir): lid 
            for lid, url in download_tasks
        }
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            # Print progress
            if len(results) % 10 == 0:
                print(f"Downloaded {len(results)}/{len(download_tasks)} licenses...")
    
    # Summary
    print("\n=== Download Summary ===")
    success_count = sum(1 for _, status, _ in results if status == 'success')
    no_text_count = sum(1 for _, status, _ in results if status == 'no_text')
    error_count = sum(1 for _, status, _ in results if status.startswith('error'))
    
    print(f"Successfully downloaded: {success_count}")
    print(f"No text available: {no_text_count}")
    print(f"Errors: {error_count}")
    
    # Save summary
    summary = {
        'total_licenses': len(licenses),
        'downloaded': success_count,
        'no_text': no_text_count,
        'errors': error_count,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open(licenses_dir / 'download_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    # List errors if any
    if error_count > 0:
        print("\nErrors:")
        for lid, status, _ in results:
            if status.startswith('error'):
                print(f"  - {lid}: {status}")
    
    # List licenses with no text
    if no_text_count > 0:
        print("\nLicenses with no text available:")
        for lid, status, _ in results:
            if status == 'no_text':
                print(f"  - {lid}")

if __name__ == '__main__':
    main()
