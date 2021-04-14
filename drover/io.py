"""Generic functionality related to files and I/O"""
import csv
import email.parser
import email.policy
import hashlib
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Pattern, Sequence


@dataclass
class ArchiveFileMapping:
    """A mapping between an archive file name and its corresponding source filesystem path"""
    archive_file_name: Path
    source_file_name: Path


@dataclass
class ArchiveMapResult:
    mappings: Sequence[ArchiveFileMapping] = field(default_factory=list)
    unmapped_files: Sequence[Path] = field(default_factory=list)

    def __bool__(self):
        return bool(self.mappings)


@dataclass
class ArchiveDescriptor:
    """An archive file and cumulative digest descriptor"""
    file_mappings: Sequence[ArchiveFileMapping] = field(default_factory=list)
    digest: Optional[str] = None


class ArchiveMapMultipleRootError(ValueError):
    """An error while attempting to map all files for an archive relative to one common root path."""


def format_file_size(size_in_bytes: float) -> str:
    """Return a string representation of the specified size as its largest 2^10 representation

    Examples:
        >>> format_file_size(2048)
        '2.00 KiB'
        >>> format_file_size(16252928.0)
        '15.50 MiB'

    Args:
        size_in_bytes: a size in bytes

    Returns: a string representation of the specified size as its largest 2^10 representation"""
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB'):
        if abs(size_in_bytes) < 1024.0:
            return f'{size_in_bytes:.2f} {unit}'
        size_in_bytes /= 1024.0
    return f'{size_in_bytes:.2f} YiB'


def get_digest(source_file_names: Iterable[Path], block_size: int = 8192) -> Optional[str]:
    """Return a SHA256 hash composed from the content of all source files.

    Args:
        source_file_names: A sequence of source file paths

    Returns: A SHA256 hash composed from the content of all source files."""
    # See the PEP-376 RECORD file specification: <https://www.python.org/dev/peps/pep-0376/#record>
    package_record_pattern = re.compile(r'\.dist-info/RECORD$')
    egg_information_pattern = re.compile(r'\.egg-info/PKG-INFO$')
    digest = hashlib.sha256()
    full = set(source_file_names)
    done = set()
    if not full:
        return None
    for source_file_name in sorted(full):
        if package_record_pattern.search(str(source_file_name)):
            package_parent_path = source_file_name.parent.parent
            with open(source_file_name, 'r', buffering=block_size) as record:
                reader = csv.reader(record, delimiter=',', quotechar='"', lineterminator=os.linesep)
                for item in reader:
                    item_name, item_hash, _other = item[:3]
                    source_file_name = package_parent_path / item_name
                    if item_hash and source_file_name in full:
                        digest.update((str(item_name) + item_hash).encode())
                        done.add(source_file_name)
    remaining = full - done
    for source_file_name in sorted(remaining):
        with open(source_file_name, 'rb', buffering=block_size) as source_file:
            if egg_information_pattern.search(str(source_file_name)):
                # Ensure deterministic field order from PKG-INFO files
                # See: <https://www.python.org/dev/peps/pep-0314/#including-metadata-in-packages>
                parser = email.parser.BytesHeaderParser(policy=email.policy.default)
                source_headers = sorted(parser.parse(source_file).items())
                for header, value in source_headers:
                    digest.update(header.encode())
                    digest.update(value.encode())
            else:
                digest.update(source_file.read())

    return digest.hexdigest()


def iter_file_names(source_path: Path) -> Iterable[Path]:
    """Return an unsorted iterable of file names recursively beneath the source path

    Args:
        source_path: a filesystem path from which to recursively iterate all files

    Returns: an unsorted iterable of file names relative to the source path"""
    seen_nodes = set()
    for root, directory_names, file_names in os.walk(source_path, followlinks=True):
        # Avoid symlink cycles
        # See: <https://stackoverflow.com/questions/36977259/avoiding-infinite-recursion-with-os-walk>
        unseen_directory_names = []
        for directory_name in directory_names:
            directory_stat = (Path(root) / directory_name).stat()
            current_node = directory_stat.st_dev, directory_stat.st_ino
            if current_node not in seen_nodes:
                seen_nodes.add(current_node)
                unseen_directory_names.append(directory_name)
        directory_names[:] = unseen_directory_names
        for file_name in file_names:
            yield Path(root) / file_name


def map_archive(
    source_file_names: Iterable[Path],
    source_root: Path,
    archive_root: Path,
    include_patterns: Optional[Iterable[Pattern]] = None,
    exclude_patterns: Optional[Iterable[Pattern]] = None
) -> ArchiveMapResult:
    """Return a separated result with archive file mappings for mapped files and a list of source file paths for unmapped files

    Args:
        include_patterns: an optional sequence of regular expressions which will be used to include files
                          (default: include all files)
        exclude_patterns: an optional sequence of regular expressions which will be used to exclude files
                          (default: exclude no files)

    Raises: ArchiveMapMultipleRootError

    Returns: a result with archive file mappings for mapped files and a list of source file paths for unmapped files"""
    include_patterns: Iterable[Pattern] = include_patterns or []
    exclude_patterns: Iterable[Pattern] = exclude_patterns or []
    mappings: List[ArchiveFileMapping] = []
    unmapped: List[Path] = []

    for source_file_name in source_file_names:
        try:
            relative_file_name = source_file_name.relative_to(source_root)
        except ValueError as e:
            raise ArchiveMapMultipleRootError(
                f'Not all source file names are subpaths of {source_root}'
            ) from e
        included = not any([p.match(str(relative_file_name)) for p in exclude_patterns])
        if include_patterns:
            included &= any([p.match(str(relative_file_name)) for p in include_patterns])
        if included:
            mappings.append(
                ArchiveFileMapping(
                    archive_file_name=archive_root / relative_file_name,
                    source_file_name=source_file_name
                )
            )
        else:
            unmapped.append(source_file_name)

    return ArchiveMapResult(mappings, unmapped)


def write_archive(archive_file_name: Path, archive_mappings: Iterable[ArchiveFileMapping]) -> None:
    """Write a zip file archive composed of the specified archive file mappings

    Args:
        archive_file_name: a writable file
        archive_mappings: an iterable of mappings of filesystem file names to archive file names"""
    with zipfile.ZipFile(
        archive_file_name, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for mapping in archive_mappings:
            archive.write(filename=mapping.source_file_name, arcname=mapping.archive_file_name)
