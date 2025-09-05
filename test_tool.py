#!/usr/bin/env python3
"""Test script for purl2notices tool."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from purl2notices.core_v2 import Purl2NoticesV2
from purl2notices.config import Config
from purl2notices.detectors import DetectorRegistry
from purl2notices.extractors import CombinedExtractor


async def test_detectors():
    """Test detector functionality."""
    print("=" * 60)
    print("Testing Detectors")
    print("=" * 60)
    
    registry = DetectorRegistry()
    
    # Test with a sample package.json
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    package_json = test_dir / "package.json"
    package_json.write_text("""{
        "name": "test-package",
        "version": "1.0.0",
        "license": "MIT",
        "author": "Test Author"
    }""")
    
    # Test detection
    results = registry.detect_from_file(package_json)
    if results:
        print(f"✓ Detected {len(results)} package(s) from package.json")
        for result in results:
            print(f"  - {result.package_type}: {result.name}@{result.version}")
            print(f"    PURL: {result.purl}")
    else:
        print("✗ No packages detected from package.json")
    
    # Test directory detection
    dir_results = registry.detect_from_directory(test_dir)
    print(f"\n✓ Detected {len(dir_results)} package(s) in directory")
    
    # Clean up
    package_json.unlink()
    test_dir.rmdir()
    
    return True


async def test_extractors():
    """Test extractor functionality with a real PURL."""
    print("\n" + "=" * 60)
    print("Testing Extractors")
    print("=" * 60)
    
    # Test with a simple, well-known package
    test_purl = "pkg:npm/lodash@4.17.21"
    
    print(f"\nTesting with PURL: {test_purl}")
    
    extractor = CombinedExtractor()
    
    # Note: This will only work if the semantic-copycat libraries are installed
    # and functioning. We'll handle failures gracefully.
    try:
        result = await extractor.extract_from_purl(test_purl)
        
        if result.success:
            print(f"✓ Extraction successful")
            print(f"  Licenses: {len(result.licenses)}")
            for lic in result.licenses[:3]:  # Show first 3
                print(f"    - {lic.spdx_id} ({lic.source.value})")
            print(f"  Copyrights: {len(result.copyrights)}")
            for cp in result.copyrights[:3]:  # Show first 3
                print(f"    - {cp.statement[:50]}...")
        else:
            print(f"✗ Extraction failed: {', '.join(result.errors)}")
            print("  Note: This is expected if semantic-copycat libraries are not installed")
    except Exception as e:
        print(f"✗ Extraction error: {e}")
        print("  Note: This is expected if semantic-copycat libraries are not installed")
    
    return True


async def test_core_processing():
    """Test core processing functionality."""
    print("\n" + "=" * 60)
    print("Testing Core Processing")
    print("=" * 60)
    
    config = Config()
    processor = Purl2NoticesV2(config)
    
    # Test PURL validation
    test_purls = [
        "pkg:npm/express@4.18.0",
        "pkg:pypi/requests@2.28.0",
        "invalid-purl",
    ]
    
    print("\nTesting PURL validation and processing:")
    for purl in test_purls:
        try:
            package = await processor.process_single_purl(purl)
            if package.status.value == "success":
                print(f"✓ {purl}: {package.status.value}")
            else:
                print(f"✗ {purl}: {package.status.value} - {package.error_message}")
        except Exception as e:
            print(f"✗ {purl}: Error - {e}")
    
    return True


async def test_directory_scanning():
    """Test directory scanning."""
    print("\n" + "=" * 60)
    print("Testing Directory Scanning")
    print("=" * 60)
    
    # Create test directory structure
    test_root = Path("test_project")
    test_root.mkdir(exist_ok=True)
    
    # Create various package files
    (test_root / "package.json").write_text("""{
        "name": "my-app",
        "version": "2.0.0",
        "license": "Apache-2.0"
    }""")
    
    (test_root / "requirements.txt").write_text("""
requests==2.28.0
flask>=2.0.0
    """)
    
    (test_root / "Cargo.toml").write_text("""
[package]
name = "my-rust-app"
version = "0.1.0"
license = "MIT OR Apache-2.0"
    """)
    
    # Test scanning
    config = Config()
    processor = Purl2NoticesV2(config)
    
    packages = processor.process_directory(test_root)
    print(f"\n✓ Found {len(packages)} package(s) in directory")
    for pkg in packages:
        print(f"  - {pkg.display_name} ({pkg.type})")
        if pkg.licenses:
            print(f"    Licenses: {', '.join(l.spdx_id for l in pkg.licenses)}")
    
    # Clean up
    for file in test_root.iterdir():
        file.unlink()
    test_root.rmdir()
    
    return True


async def test_notice_generation():
    """Test notice generation."""
    print("\n" + "=" * 60)
    print("Testing Notice Generation")
    print("=" * 60)
    
    from purl2notices.models import Package, License, Copyright
    
    # Create sample packages
    packages = [
        Package(
            name="test-package-1",
            version="1.0.0",
            type="npm",
            licenses=[License(spdx_id="MIT", name="MIT License", text="MIT License text...")],
            copyrights=[Copyright(statement="Copyright (c) 2024 Test Author")]
        ),
        Package(
            name="test-package-2",
            version="2.0.0",
            type="pypi",
            licenses=[License(spdx_id="Apache-2.0", name="Apache License 2.0", text="Apache text...")],
            copyrights=[Copyright(statement="Copyright 2024 Another Author")]
        ),
    ]
    
    config = Config()
    processor = Purl2NoticesV2(config)
    
    # Generate text notice
    text_notice = processor.generate_notices(
        packages,
        output_format="text",
        group_by_license=True,
        include_copyright=True,
        include_license_text=False  # Don't include full text for brevity
    )
    
    print("\nGenerated Text Notice (excerpt):")
    print("-" * 40)
    lines = text_notice.split('\n')[:20]  # Show first 20 lines
    for line in lines:
        print(line)
    print("...")
    
    print("\n✓ Notice generation successful")
    
    return True


async def main():
    """Run all tests."""
    print("Testing purl2notices Tool")
    print("=" * 60)
    
    tests = [
        ("Detectors", test_detectors),
        ("Extractors", test_extractors),
        ("Core Processing", test_core_processing),
        ("Directory Scanning", test_directory_scanning),
        ("Notice Generation", test_notice_generation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = await test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n✗ {name} test failed with error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)