from unittest import TestCase

from drover import Drover


class TestDrover(TestCase):
    def test_runtime_library_path_supports_python(self):
        for python_version in ('python3.6', 'python3.7', 'python3.8'):
            with self.subTest(python_version=python_version):
                assert Drover._get_runtime_library_path(python_version).name == 'python'
