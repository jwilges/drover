"""Generic functionality related to files and I/O"""
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Pattern, Sequence


@dataclass
class ArchiveMapping:
    """A mapping between an archive file name and its corresponding source filesystem path"""
    source_file_name: Path
    archive_file_name: Path


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
        archive_mappings: an iterable of mappings of filesystem file names to archive file names
    """
    with zipfile.ZipFile(archive_file_name, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for mapping in archive_mappings:
            archive.write(filename=mapping.source_file_name, arcname=mapping.archive_file_name)
