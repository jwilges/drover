"""Generic functionality related to files and I/O"""
import csv
import email.parser
import email.policy
import hashlib
import re
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Pattern, Sequence


@dataclass
class ArchiveMapping:
    """A mapping between an archive file name and its corresponding source filesystem path"""
    source_file_name: Path
    archive_file_name: Path


@dataclass
class FunctionLayerMappings:
    """A function and requirements layer mapping and digest container"""
    function_mappings: Sequence[ArchiveMapping] = field(default=list)
    function_digest: str = None
    requirements_mappings: Sequence[ArchiveMapping] = field(default=list)
    requirements_digest: str = None


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


def get_digest(source_file_names: Sequence[Path], block_size: int = 8192) -> str:
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
                # See: https://www.python.org/dev/peps/pep-0314/#including-metadata-in-packages
                parser = email.parser.BytesHeaderParser(policy=email.policy.default)
                source_headers = sorted(parser.parse(source_file).items())
                for header, value in source_headers:
                    digest.update(header.encode())
                    digest.update(value.encode())
            else:
                digest.update(source_file.read())

    return digest.hexdigest()


def get_relative_file_names(source_path: Path, exclude_patterns: Sequence[Pattern] = None) -> Iterable[Path]:
    """Return an unsorted iterable of files recursively beneath the source path

    Args:
        source_path: a filesystem path from which to recursively iterate all files
        exclude_patterns: an optional sequence of regular expressions which will be used to exclude files

    Returns: an unsorted iterable of files recursively beneath the source path"""
    exclude_patterns = exclude_patterns or []
    for root, _directory_names, file_names in os.walk(source_path):
        for file_name in file_names:
            relative_file_name = Path(os.path.join(root, file_name)).relative_to(source_path)
            if not any([pattern.match(str(relative_file_name)) for pattern in exclude_patterns]):
                yield relative_file_name


def write_archive(archive_file_name: Path, archive_mappings: Iterable[ArchiveMapping]) -> None:
    """Write a zip file archive composed of the specified archive file mappings

    Args:
        archive_file_name: a writable file
        archive_mappings: an iterable of mappings of filesystem file names to archive file names"""
    with zipfile.ZipFile(archive_file_name, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for mapping in archive_mappings:
            archive.write(filename=mapping.source_file_name, arcname=mapping.archive_file_name)
