"""Extractor using osslili library."""

import logging
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import Optional

from .base import (
    BaseExtractor, ExtractionResult, ExtractionSource,
    LicenseInfo, CopyrightInfo, CATEGORY_DECLARED, CATEGORY_THIRD_PARTY,
    THIRD_PARTY_CATEGORIES, detection_root, is_bundled_path
)


logger = logging.getLogger(__name__)


class OssliliExtractor(BaseExtractor):
    """Extractor that uses osslili for license/copyright detection."""

    # A license file is small. Anything larger is not one, and inlining it
    # into a notices file would be worse than falling back to the template.
    MAX_LICENSE_TEXT_BYTES = 256 * 1024

    # Match types where osslili is naming a file that IS the license, rather
    # than a file that merely states an identifier. package.json declares
    # "license": "MIT"; reading it as license text would emit JSON.
    LICENSE_FILE_MATCH_TYPES = frozenset({"license_file", "license_text", "full_text"})

    @staticmethod
    def _category_for(lic_data, root: str) -> str:
        """The category to record, correcting for what the path says.

        A detector category is only overridden towards third-party, never away
        from it: a path that looks like the package's own does not make a
        license the detector called third-party into a declaration.
        """
        category = getattr(lic_data, 'category', None) or CATEGORY_DECLARED
        if category in THIRD_PARTY_CATEGORIES:
            return category
        if is_bundled_path(getattr(lic_data, 'source_file', None), root):
            return CATEGORY_THIRD_PARTY
        return category

    def _shipped_license_text(self, lic_data, root: Path) -> Optional[str]:
        """Read the license as the package actually ships it.

        osslili names the file a license was found in but does not carry its
        contents, so without this the only text available is the SPDX template,
        which is emitted with its `<year>` and `<copyright holders>` fields
        still literal. The shipped file already has the holders filled in and is
        what the project actually wrote, so it is the better answer.

        What the name means depends on what was scanned. For a directory it is a
        path on disk; for an archive it is a path inside that archive, which
        never exists on disk and so has to be read from the archive itself.

        Returns None when there is nothing to read, which leaves the existing
        template fallback in place.
        """
        if getattr(lic_data, "text", ""):
            return None

        if getattr(lic_data, "match_type", None) not in self.LICENSE_FILE_MATCH_TYPES:
            return None

        source_file = getattr(lic_data, "source_file", None)
        if not source_file:
            return None

        try:
            if root.is_dir():
                return self._text_from_directory(source_file, root)
            if root.is_file():
                return self._text_from_archive(source_file, root)
        except (OSError, ValueError) as e:
            logger.debug("Could not read license file %s: %s", source_file, e)
        return None

    def _text_from_directory(self, source_file: str, root: Path) -> Optional[str]:
        """Read a license file from the tree that was scanned."""
        candidate = Path(source_file)
        if not candidate.is_absolute():
            candidate = root / candidate

        resolved = candidate.resolve()
        # A name that climbs out of what was scanned is not this package's
        # license, whatever it happens to contain. relative_to rather than
        # is_relative_to, which needs 3.9 and this package supports 3.8.
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            logger.debug("License file outside the scanned root: %s", source_file)
            return None

        if not resolved.is_file():
            return None
        if resolved.stat().st_size > self.MAX_LICENSE_TEXT_BYTES:
            logger.debug("License file too large to inline: %s", resolved)
            return None
        return resolved.read_text(encoding="utf-8", errors="replace")

    def _text_from_archive(self, source_file: str, archive: Path) -> Optional[str]:
        """Read a license file out of the archive that was scanned.

        The member is read as a stream and capped rather than extracted, so a
        member that lies about its size cannot spend more than the cap.
        """
        member = source_file.lstrip("/")
        cap = self.MAX_LICENSE_TEXT_BYTES

        if zipfile.is_zipfile(archive):
            try:
                with zipfile.ZipFile(archive) as zf:
                    try:
                        info = zf.getinfo(member)
                    except KeyError:
                        return None
                    if info.is_dir() or info.file_size > cap:
                        return None
                    # tarfile refuses a symlink through isfile(); zipfile does
                    # not, and reading one yields the link target as text.
                    if stat.S_ISLNK(info.external_attr >> 16):
                        logger.debug("Refusing symlinked license member: %s", member)
                        return None
                    with zf.open(info) as fh:
                        return self._read_capped(fh, cap)
            except (zipfile.BadZipFile, RuntimeError) as e:
                logger.debug("Could not read %s from %s: %s", member, archive, e)
                return None

        try:
            with tarfile.open(archive) as tf:
                try:
                    info = tf.getmember(member)
                except KeyError:
                    return None
                if not info.isfile() or info.size > cap:
                    return None
                fh = tf.extractfile(info)
                if fh is None:
                    return None
                with fh:
                    return self._read_capped(fh, cap)
        except tarfile.TarError as e:
            logger.debug("Could not read %s from %s: %s", member, archive, e)
            return None

    @staticmethod
    def _read_capped(fh, cap: int) -> Optional[str]:
        """Read at most cap bytes, refusing anything that runs past it."""
        data = fh.read(cap + 1)
        if len(data) > cap:
            return None
        return data.decode("utf-8", errors="replace")

    async def extract_from_purl(self, purl: str) -> ExtractionResult:
        """osslili works with local files, not PURLs directly."""
        return ExtractionResult(
            success=False,
            errors=["osslili requires local files or directories"],
            source=ExtractionSource.OSSLILI
        )
    
    async def extract_from_path(self, path: Path) -> ExtractionResult:
        """Extract license and copyright info using osslili."""
        try:
            try:
                from osslili import LicenseCopyrightDetector
            except ImportError:
                logger.warning("osslili not installed, returning empty result")
                return ExtractionResult(
                    success=False,
                    errors=["osslili library not available"],
                    source=ExtractionSource.OSSLILI
                )
            
            # Extract information
            detector = LicenseCopyrightDetector()
            result = detector.process_local_path(str(path))
            
            if not result:
                return ExtractionResult(
                    success=False,
                    errors=[f"No information extracted from {path}"],
                    source=ExtractionSource.OSSLILI
                )
            
            # Parse licenses
            licenses = []
            if hasattr(result, 'licenses') and result.licenses:
                # osslili has a third-party category but does not assign it, so
                # the licenses of code a package carries arrive labelled exactly
                # like the package's own. The path each was found at is the
                # signal it does give: a package states its own terms at its
                # root, and a license under a subdirectory came with the code
                # there. Without this the whole tree reads as one declaration,
                # so numpy reports the licenses of everything it vendors as
                # its own.
                root = detection_root(
                    (getattr(lic, 'source_file', None) for lic in result.licenses),
                    # A directory was scanned as itself, so its own path is the
                    # root. An archive is reported relative to itself, and the
                    # top-level directory inside it has to be derived.
                    scanned_root=path if path.is_dir() else None,
                )
                for lic_data in result.licenses:
                    license_info = LicenseInfo(
                        spdx_id=self.normalize_license_id(
                            getattr(lic_data, 'spdx_id', '') or
                            getattr(lic_data, 'name', 'NOASSERTION')
                        ),
                        name=getattr(lic_data, 'name', '') or getattr(lic_data, 'spdx_id', ''),
                        text=(self._shipped_license_text(lic_data, path)
                              or getattr(lic_data, 'text', '')),
                        source=ExtractionSource.OSSLILI,
                        confidence=getattr(lic_data, 'confidence', 0.8),
                        # osslili already separates a license the package
                        # states from one it merely mentions, and names the file
                        # each came from. Carrying that through is what lets the
                        # combining step rank them; the output model does not
                        # hold it yet, so the notices file cannot show it.
                        category=self._category_for(lic_data, root),
                        match_type=getattr(lic_data, 'match_type', None),
                        detection_method=getattr(lic_data, 'detection_method', None),
                        source_file=getattr(lic_data, 'source_file', None),
                    )
                    licenses.append(license_info)
            
            # Parse copyrights
            copyrights = []
            if hasattr(result, 'copyrights') and result.copyrights:
                for copyright_data in result.copyrights:
                    copyright_info = CopyrightInfo(
                        statement=getattr(copyright_data, 'statement', ''),
                        year_start=getattr(copyright_data, 'years', None),
                        year_end=None,
                        holders=[getattr(copyright_data, 'holder', '')] if getattr(copyright_data, 'holder', '') else [],
                        source=ExtractionSource.OSSLILI,
                        confidence=getattr(copyright_data, 'confidence', 0.8)
                    )
                    if copyright_info.statement:
                        copyrights.append(copyright_info)
            
            # Additional metadata
            metadata = {
                'package_name': getattr(result, 'package_name', ''),
                'package_version': getattr(result, 'package_version', ''),
            }
            
            return ExtractionResult(
                success=True,
                licenses=self.deduplicate_licenses(licenses),
                copyrights=self.deduplicate_copyrights(copyrights),
                metadata=metadata,
                source=ExtractionSource.OSSLILI
            )
            
        except ImportError:
            logger.error("osslili library not installed")
            return ExtractionResult(
                success=False,
                errors=["osslili library not available"],
                source=ExtractionSource.OSSLILI
            )
        except Exception as e:
            logger.error(f"Error extracting with osslili: {e}")
            return ExtractionResult(
                success=False,
                errors=[str(e)],
                source=ExtractionSource.OSSLILI
            )