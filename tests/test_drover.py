# pylint: disable=protected-access
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

import boto3
import pytest

from drover import Drover, SettingsError
from drover.models import Settings, Stage


def get_supported_compatible_runtime():
    return 'python3.8'


def get_basic_settings(expected_stage_name: str) -> Settings:
    expected_stage = Stage(
        region_name='region_name',
        function_name='function_name',
        compatible_runtime=get_supported_compatible_runtime(),
        function_file_patterns=[
            '^function.*'
        ])
    expected_settings = Settings(
        stages={
            expected_stage_name: expected_stage
        })
    return expected_settings


class TestDrover(TestCase):
    def test_init_with_valid_settings_and_invalid_stage_name(self):
        expected_invalid_stage_name = 'stage-invalid'
        expected_settings = get_basic_settings('stage')
        expected_compatible_runtime_library_path = Path('path')

        mock_boto3_client = MagicMock()

        with patch.object(Drover, '_get_runtime_library_path', return_value=expected_compatible_runtime_library_path), \
             patch.object(boto3, 'client', return_value=mock_boto3_client):
            with pytest.raises(SettingsError, match=r'^Invalid stage name.*'):
                Drover(expected_settings, expected_invalid_stage_name, interactive=False)

    def test_init_with_valid_settings_and_stage(self):
        expected_stage_name = 'stage'
        expected_settings = get_basic_settings(expected_stage_name)
        expected_stage = expected_settings.stages[expected_stage_name]
        expected_interactive = False
        expected_requirements_layer_name = 'function_name-requirements'
        expected_compatible_runtime_library_path = Path('path')

        mock_boto3_client = MagicMock()

        with patch.object(Drover, '_get_runtime_library_path', return_value=expected_compatible_runtime_library_path) as mock_get_runtime_library_path, \
             patch.object(boto3, 'client', return_value=mock_boto3_client) as mock_boto3_client_cls:
            drover = Drover(expected_settings, expected_stage_name, interactive=expected_interactive)
            mock_get_runtime_library_path.assert_called_once_with(expected_stage.compatible_runtime)
            mock_boto3_client_cls.assert_called_once_with('lambda', region_name=expected_stage.region_name)

        assert drover.settings == expected_settings
        assert drover.interactive == expected_interactive
        assert drover.stage == expected_stage
        assert drover.stage.requirements_layer_name == expected_requirements_layer_name
        assert drover.compatible_runtime_library_path == expected_compatible_runtime_library_path
        assert drover.lambda_client == mock_boto3_client

    def test_runtime_library_path_supports_python(self):
        for python_version in ('python3.6', 'python3.7', 'python3.8'):
            with self.subTest(python_version=python_version):
                assert Drover._get_runtime_library_path(python_version).name == 'python'
