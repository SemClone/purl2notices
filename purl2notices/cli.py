"""CLI interface for purl2notices."""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

import click
import yaml

from .core import Purl2Notices
from .config import Config
from .cache import CacheManager
from .validators import FileValidator


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


@click.command()
@click.option(
    '--input', '-i',
    help='Input (PURL, file path, directory, or cache file)'
)
@click.option(
    '--mode', '-m',
    type=click.Choice(['auto', 'single', 'kissbom', 'scan', 'cache']),
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
    type=click.Choice(['text', 'html']),
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
def main(
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
    log_file: Optional[str]
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
    """
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
            cache_file = Path(config_obj.get("cache.location", ".purl2notices.cache.json"))
    
    # Auto-detect mode if needed
    if mode == 'auto':
        if not input and cache_file and cache_file.exists():
            mode = 'cache'
            input = str(cache_file)
        elif input:
            detected = FileValidator.detect_input_type(input)
            if detected == 'purl':
                mode = 'single'
            elif detected == 'kissbom':
                mode = 'kissbom'
            elif detected == 'cache':
                mode = 'cache'
            elif detected == 'directory':
                mode = 'scan'
            else:
                click.echo(f"Error: Could not detect input type for: {input}", err=True)
                sys.exit(1)
        else:
            click.echo("Error: No input provided and no cache file found", err=True)
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
        
        elif mode == 'cache':
            if not input:
                click.echo("Error: Cache file required for cache mode", err=True)
                sys.exit(1)
            
            cache_path = Path(input)
            if not cache_path.exists():
                click.echo(f"Error: Cache file not found: {input}", err=True)
                sys.exit(1)
            
            logger.info(f"Loading from cache: {input}")
            packages = processor.process_cache(cache_path)
        
        # Save to cache if enabled
        if cache_file and mode != 'cache':
            logger.info(f"Saving to cache: {cache_file}")
            cache_manager = CacheManager(cache_file)
            cache_manager.save(packages)
        
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