"""CLI interface for purl2notices."""

import sys
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .core import Purl2Notices
from .config import Config
from .cache import CacheManager
from .validators import FileValidator
from .constants import NON_OSS_INDICATORS, COMMON_OSS_PATTERNS
from .models import Package, ProcessingStatus


def setup_logging(verbose: int) -> None:
    """Setup logging based on verbosity level."""
    if verbose == 0:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    else:
        level = logging.WARNING
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Suppress verbose warnings from semantic-copycat-oslili
    if verbose < 2:  # Unless in debug mode
        logging.getLogger('semantic_copycat_oslili').setLevel(logging.ERROR)
        logging.getLogger('upmex').setLevel(logging.ERROR)


@click.command()
@click.version_option(version=__version__, prog_name='purl2notices')
@click.option('--install-completion', is_flag=True, help='Install shell completion')
@click.option('--show-completion', is_flag=True, help='Show shell completion script')
@click.option(
    '--input', '-i',
    help='Input (PURL, file path, directory, or cache file)'
)
@click.option(
    '--mode', '-m',
    type=click.Choice(['auto', 'single', 'kissbom', 'scan', 'archive', 'cache']),
    default='auto',
    help='Operation mode (auto-detected by default)'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file path (default: stdout)'
)
@click.option(
    '--format', '-f',
    type=click.Choice(['text', 'html', 'json']),
    default='text',
    help='Output format'
)
@click.option(
    '--cache', '-c',
    type=click.Path(),
    help='Cache file location (enables caching)'
)
@click.option(
    '--no-cache',
    is_flag=True,
    help='Disable caching'
)
@click.option(
    '--template', '-t',
    type=click.Path(exists=True, path_type=Path),
    help='Custom template file'
)
@click.option(
    '--config',
    type=click.Path(exists=True, path_type=Path),
    help='Configuration file'
)
@click.option(
    '--verbose', '-v',
    count=True,
    help='Increase verbosity (can be used multiple times)'
)
@click.option(
    '--parallel', '-p',
    type=int,
    default=4,
    help='Number of parallel workers for batch processing'
)
@click.option(
    '--recursive', '-r',
    is_flag=True,
    default=True,
    help='Recursive directory scan'
)
@click.option(
    '--max-depth', '-d',
    type=int,
    default=10,
    help='Maximum directory depth for scanning'
)
@click.option(
    '--exclude', '-e',
    multiple=True,
    help='Exclude patterns for directory scan (can be used multiple times)'
)
@click.option(
    '--group-by-license',
    is_flag=True,
    default=True,
    help='Group packages by license in output'
)
@click.option(
    '--no-copyright',
    is_flag=True,
    help='Exclude copyright notices from output'
)
@click.option(
    '--no-license-text',
    is_flag=True,
    help='Exclude license texts from output'
)
@click.option(
    '--continue-on-error',
    is_flag=True,
    help='Continue processing on errors'
)
@click.option(
    '--log-file',
    type=click.Path(),
    help='Log file path'
)
@click.option(
    '--overrides',
    type=click.Path(path_type=Path),
    help='User overrides configuration file'
)
@click.option(
    '--merge-cache',
    type=click.Path(path_type=Path),
    multiple=True,
    help='Additional cache files to merge (can be used multiple times)'
)
def main(
    install_completion: bool,
    show_completion: bool,
    input: Optional[str],
    mode: str,
    output: Optional[str],
    format: str,
    cache: Optional[str],
    no_cache: bool,
    template: Optional[Path],
    config: Optional[Path],
    verbose: int,
    parallel: int,
    recursive: bool,
    max_depth: int,
    exclude: tuple,
    group_by_license: bool,
    no_copyright: bool,
    no_license_text: bool,
    continue_on_error: bool,
    log_file: Optional[str],
    overrides: Optional[Path],
    merge_cache: tuple
):
    """
    Generate legal notices (attribution to authors and copyrights) for software packages.
    
    Examples:
    
        # Process single PURL
        purl2notices -i pkg:npm/express@4.0.0
        
        # Process KissBOM file
        purl2notices -i packages.txt -o NOTICE.txt
        
        # Scan directory
        purl2notices -i ./src --recursive
        
        # Use cache file
        purl2notices -i project.cdx.json -o NOTICE.html -f html
        
        # Generate and use cache
        purl2notices -i packages.txt --cache project.cache.json
        purl2notices --cache project.cache.json -o NOTICE.txt
        
        # Merge multiple cache files
        purl2notices -i cache1.json --merge-cache cache2.json --merge-cache cache3.json -o NOTICE.txt
    """
    # Handle shell completion
    if install_completion:
        import os
        shell = os.environ.get('SHELL', '').split('/')[-1]
        if 'bash' in shell:
            click.echo("# Add to ~/.bashrc:")
            click.echo('eval "$(_PURL2NOTICES_COMPLETE=bash_source purl2notices)"')
        elif 'zsh' in shell:
            click.echo("# Add to ~/.zshrc:")
            click.echo('eval "$(_PURL2NOTICES_COMPLETE=zsh_source purl2notices)"')
        elif 'fish' in shell:
            click.echo("# Add to ~/.config/fish/config.fish:")
            click.echo('_PURL2NOTICES_COMPLETE=fish_source purl2notices | source')
        else:
            click.echo("Shell completion is available for bash, zsh, and fish")
        return
    
    if show_completion:
        import os
        shell = os.environ.get('SHELL', '').split('/')[-1]
        if 'bash' in shell:
            os.environ['_PURL2NOTICES_COMPLETE'] = 'bash_source'
        elif 'zsh' in shell:
            os.environ['_PURL2NOTICES_COMPLETE'] = 'zsh_source'
        elif 'fish' in shell:
            os.environ['_PURL2NOTICES_COMPLETE'] = 'fish_source'
        else:
            click.echo("Shell completion is available for bash, zsh, and fish")
            return
        
        # This will trigger Click's completion mechanism
        import sys
        sys.argv = ['purl2notices']
        ctx = click.get_current_context()
        ctx.complete()
        return
    
    # Show help if no input provided at all
    ctx = click.get_current_context()
    if not input and not cache:
        click.echo(ctx.get_help())
        ctx.exit(0)
    
    # Setup logging
    setup_logging(verbose)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        logging.getLogger().addHandler(file_handler)
    
    logger = logging.getLogger(__name__)
    
    # Load configuration
    config_obj = Config(config)
    
    # Apply CLI overrides
    if verbose:
        config_obj.set("general.verbose", verbose)
    if parallel:
        config_obj.set("general.parallel_workers", parallel)
    if continue_on_error:
        config_obj.set("general.continue_on_error", True)
    if exclude:
        existing = config_obj.get("scanning.exclude_patterns", [])
        existing.extend(list(exclude))
        config_obj.set("scanning.exclude_patterns", existing)
    if not recursive:
        config_obj.set("scanning.recursive", False)
    if max_depth:
        config_obj.set("scanning.max_depth", max_depth)
    
    # Determine cache file
    cache_file = None
    if not no_cache:
        if cache:
            cache_file = Path(cache)
        else:
            # Use default cache location for saving, but not for loading
            cache_file = Path(config_obj.get("cache.location", "purl2notices.cache.json"))
    
    # Auto-detect mode if needed
    if mode == 'auto':
        if input:
            detected = FileValidator.detect_input_type(input)
            if detected == 'purl':
                mode = 'single'
            elif detected == 'kissbom':
                mode = 'kissbom'
            elif detected == 'cache':
                mode = 'cache'
            elif detected == 'archive':
                mode = 'archive'
            elif detected == 'directory':
                mode = 'scan'
            else:
                click.echo(f"Error: Could not detect input type for: {input}", err=True)
                sys.exit(1)
        else:
            click.echo("Error: No input provided", err=True)
            sys.exit(1)
    
    # Initialize processor
    processor = Purl2Notices(config_obj)
    
    # Process based on mode
    packages = []
    
    try:
        if mode == 'single':
            if not input:
                click.echo("Error: Input required for single mode", err=True)
                sys.exit(1)
            
            logger.info(f"Processing single PURL: {input}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            package = loop.run_until_complete(processor.process_single_purl(input))
            loop.close()
            packages = [package]
        
        elif mode == 'kissbom':
            if not input:
                click.echo("Error: Input file required for kissbom mode", err=True)
                sys.exit(1)
            
            input_path = Path(input)
            is_valid, error, purl_list = FileValidator.validate_kissbom(input_path)
            
            if not is_valid:
                click.echo(f"Error: {error}", err=True)
                sys.exit(1)
            
            logger.info(f"Processing {len(purl_list)} PURLs from {input}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            packages = loop.run_until_complete(
                processor.process_batch(purl_list, parallel=parallel)
            )
            loop.close()
        
        elif mode == 'scan':
            if not input:
                click.echo("Error: Directory path required for scan mode", err=True)
                sys.exit(1)
            
            directory = Path(input)
            if not directory.exists() or not directory.is_dir():
                click.echo(f"Error: Invalid directory: {input}", err=True)
                sys.exit(1)
            
            logger.info(f"Scanning directory: {input}")
            packages = processor.process_directory(directory)
        
        elif mode == 'archive':
            if not input:
                click.echo("Error: Archive file required for archive mode", err=True)
                sys.exit(1)
            
            archive_path = Path(input)
            if not archive_path.exists():
                click.echo(f"Error: Archive file not found: {input}", err=True)
                sys.exit(1)
            
            logger.info(f"Processing archive: {input}")
            # Process archive file through extractor
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            extraction = loop.run_until_complete(
                processor.extractor.extract_from_path(archive_path)
            )
            loop.close()
            
            # Create package from extraction
            package = Package(
                name=archive_path.stem,
                source_path=str(archive_path)
            )
            
            if extraction.success:
                package = processor._extraction_to_package(package, extraction)
            else:
                package.status = ProcessingStatus.FAILED
                package.error_message = "; ".join(extraction.errors) if extraction.errors else "Failed to extract from archive"
            
            packages = [package]
        
        elif mode == 'cache':
            if not input:
                click.echo("Error: Cache file required for cache mode", err=True)
                sys.exit(1)
            
            cache_path = Path(input)
            if not cache_path.exists():
                click.echo(f"Error: Cache file not found: {input}", err=True)
                sys.exit(1)
            
            logger.info(f"Loading from cache: {input}")
            packages = processor.process_cache(cache_path, overrides)
        
        # Merge additional cache files if provided
        if merge_cache:
            logger.info(f"Merging {len(merge_cache)} additional cache files")
            for merge_file in merge_cache:
                merge_path = Path(merge_file)
                if merge_path.exists():
                    logger.info(f"Merging cache from: {merge_path}")
                    merge_manager = CacheManager(merge_path, Path("purl2notices.overrides.json"))
                    merge_packages = merge_manager.load(apply_overrides=False)
                    
                    # Add to packages list
                    existing_purls = {pkg.purl for pkg in packages if pkg.purl}
                    for pkg in merge_packages:
                        if pkg.purl not in existing_purls:
                            packages.append(pkg)
                            existing_purls.add(pkg.purl)
                else:
                    logger.warning(f"Cache file not found: {merge_path}")
        
        # Save to cache if enabled
        if cache_file and mode != 'cache':
            logger.info(f"Saving to cache: {cache_file}")
            override_file = overrides or Path("purl2notices.overrides.json")
            cache_manager = CacheManager(cache_file, override_file)
            cache_manager.save(packages)
        
        # Check for packages without licenses and non-SPDX/commercial licenses
        no_license_packages = []
        failed_packages = []
        non_oss_packages = []  # Packages with commercial/proprietary/non-SPDX licenses
        
        # Build set of valid SPDX license IDs from files
        licenses_dir = Path(__file__).parent / "data" / "licenses"
        valid_spdx_ids = set()
        if licenses_dir.exists():
            for license_file in licenses_dir.glob("*.txt"):
                # Remove .txt extension to get license ID
                valid_spdx_ids.add(license_file.stem)
        
        # Also build lowercase mapping for case-insensitive matching
        valid_spdx_lower = {lid.lower(): lid for lid in valid_spdx_ids}
        
        for pkg in packages:
            if pkg.status.value in ['unavailable', 'failed']:
                failed_packages.append((pkg.display_name, pkg.error_message or 'Unknown error'))
            elif not pkg.licenses:
                no_license_packages.append(pkg.display_name)
                logger.error(f"No license found for package: {pkg.display_name}")
            else:
                # Check for non-SPDX or commercial licenses
                for license_info in pkg.licenses:
                    license_id = (license_info.spdx_id or license_info.name or '').lower()
                    
                    # Check if it's a known non-OSS license
                    is_non_oss = any(indicator in license_id for indicator in NON_OSS_INDICATORS)
                    
                    # Also check if it's not a recognized SPDX license
                    is_unrecognized_spdx = False
                    if license_info.spdx_id:
                        # Check exact match or case-insensitive match
                        if license_info.spdx_id not in valid_spdx_ids:
                            # Try case-insensitive match
                            spdx_lower = license_info.spdx_id.lower()
                            if spdx_lower not in valid_spdx_lower:
                                # Check for common OSS license patterns without version
                                if not any(oss in spdx_lower for oss in COMMON_OSS_PATTERNS):
                                    is_unrecognized_spdx = True
                    
                    if license_id and (is_non_oss or is_unrecognized_spdx):
                        license_display = license_info.spdx_id or license_info.name or 'Unknown'
                        non_oss_packages.append((pkg.display_name, license_display))
                        logger.warning(f"Non-OSS or unrecognized license found for {pkg.display_name}: {license_display}")
                        break  # Only report once per package
        
        # Always create error.log if there are any errors
        error_log_file = log_file or Path("error.log")
        has_errors = no_license_packages or failed_packages or non_oss_packages
        
        if has_errors:
            with open(error_log_file, 'w') as f:
                f.write(f"=== purl2notices Error Log - {datetime.now().isoformat()} ===\n\n")
                
                if failed_packages:
                    f.write(f"Failed to process {len(failed_packages)} package(s):\n")
                    for pkg_name, error_msg in failed_packages:
                        f.write(f"  - {pkg_name}: {error_msg}\n")
                    f.write("\n")
                
                if no_license_packages:
                    f.write(f"No licenses found for {len(no_license_packages)} package(s):\n")
                    for pkg_name in no_license_packages:
                        f.write(f"  - {pkg_name}\n")
                    f.write("\n")
                
                if non_oss_packages:
                    f.write(f"Non-OSS or unrecognized licenses found in {len(non_oss_packages)} package(s):\n")
                    for pkg_name, license_name in non_oss_packages:
                        f.write(f"  - {pkg_name}: {license_name}\n")
        
        # Report to console
        if failed_packages:
            click.echo(f"\nWARNING: Failed to process {len(failed_packages)} package(s):", err=True)
            for pkg_name, error_msg in failed_packages[:5]:  # Show first 5
                click.echo(f"  - {pkg_name}: {error_msg}", err=True)
            if len(failed_packages) > 5:
                click.echo(f"  ... and {len(failed_packages) - 5} more", err=True)
        
        if no_license_packages:
            click.echo(f"\nERROR: No licenses found for {len(no_license_packages)} package(s):", err=True)
            for pkg_name in no_license_packages[:10]:  # Show first 10
                click.echo(f"  - {pkg_name}", err=True)
            if len(no_license_packages) > 10:
                click.echo(f"  ... and {len(no_license_packages) - 10} more", err=True)
        
        if non_oss_packages:
            click.echo(f"\nWARNING: Non-OSS or unrecognized licenses in {len(non_oss_packages)} package(s):", err=True)
            for pkg_name, license_name in non_oss_packages[:5]:  # Show first 5
                click.echo(f"  - {pkg_name}: {license_name}", err=True)
            if len(non_oss_packages) > 5:
                click.echo(f"  ... and {len(non_oss_packages) - 5} more", err=True)
        
        if has_errors:
            click.echo(f"\nErrors written to: {error_log_file}", err=True)
        
        # Generate notices
        notices = processor.generate_notices(
            packages=packages,
            output_format=format,
            template_path=template,
            group_by_license=group_by_license,
            include_copyright=not no_copyright,
            include_license_text=not no_license_text
        )
        
        # Output results
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(notices)
            logger.info(f"Legal notices written to: {output}")
        else:
            click.echo(notices)
        
        # Print summary
        if verbose:
            click.echo(f"\nProcessed {len(packages)} packages", err=True)
            failed = [p for p in packages if p.status.value == 'failed']
            if failed:
                click.echo(f"Failed: {len(failed)} packages", err=True)
            
            if processor.error_log:
                click.echo("\nErrors encountered:", err=True)
                for error in processor.error_log[:10]:  # Show first 10 errors
                    click.echo(f"  - {error}", err=True)
                if len(processor.error_log) > 10:
                    click.echo(f"  ... and {len(processor.error_log) - 10} more", err=True)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()