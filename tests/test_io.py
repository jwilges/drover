import os
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

from drover.io import ArchiveMapping, get_relative_file_names, write_archive


class TestGetRelativeFileNames(TestCase):
    def test_without_excludes(self):
        expected_source_path = '/'
        expected_relative_file_names = set((
            Path('file_0'),
            Path('path_a/file_a_0'),
            Path('path_a/file_a_1'),
            Path('path_b/file_b_0')))
        expected_walk = (
            ('/', ('path_a', 'path_b',), ('file_0',)),
            ('/path_a', (), ('file_a_0', 'file_a_1')),
            ('/path_b', (), ('file_b_0',)),
        )
        with patch.object(os, 'walk', return_value=expected_walk) as mock_walk:
            names = set(get_relative_file_names(expected_source_path))
            mock_walk.assert_called_once_with(str(expected_source_path))
            assert names == expected_relative_file_names


class TestWriteArchive(TestCase):
    def test_write_empty_archive(self):
        expected_archive_file_name = Path('archive.zip')
        mock_zip_file = MagicMock(spec=zipfile.ZipFile)
        with patch.object(zipfile, 'ZipFile') as mock_zip_file_cls:
            mock_zip_file_cls.return_value.__enter__.return_value = mock_zip_file
            write_archive(expected_archive_file_name, [])
            mock_zip_file_cls.assert_called_once_with(
                expected_archive_file_name, 'w',
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9)
            mock_zip_file.write.assert_not_called()

    def test_write_non_empty_archive(self):
        expected_archive_file_name = Path('archive.zip')
        expected_archive_mappings = [
            ArchiveMapping(source_file_name=Path('source/a'), archive_file_name=Path('archive/a')),
            ArchiveMapping(source_file_name=Path('source/b'), archive_file_name=Path('archive/b')),
        ]
        mock_zip_file = MagicMock(spec=zipfile.ZipFile)
        with patch.object(zipfile, 'ZipFile') as mock_zip_file_cls:
            mock_zip_file_cls.return_value.__enter__.return_value = mock_zip_file
            write_archive(expected_archive_file_name, expected_archive_mappings)
            mock_zip_file_cls.assert_called_once_with(
                expected_archive_file_name, 'w',
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=9)
        for expected_archive_mapping in expected_archive_mappings:
            mock_zip_file.write.assert_any_call(
                filename=expected_archive_mapping.source_file_name,
                arcname=expected_archive_mapping.archive_file_name)
