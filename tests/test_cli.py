# pylint: disable=protected-access
from dataclasses import dataclass
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import drover
import drover.cli

from tests.test_drover import get_basic_settings


@dataclass
class MockArguments:
    stage: str
    quiet: bool
    interactive: bool = True
    non_interactive: bool = False
    settings_file: Path = Path('drover.yml')
    install_path: Path = Path('.')


class TestDroverCLI(TestCase):
    def test_basic_run(self):
        expected_stage_name = 'stage'
        expected_settings = get_basic_settings(expected_stage_name)
        expected_interactive = True
        mock_arguments = MockArguments(
            stage='stage',
            quiet=True,
            interactive=expected_interactive, non_interactive=not expected_interactive)
        with patch.object(drover.cli, '_parse_arguments', return_value=mock_arguments) as mock_parse_arguments, \
             patch.object(drover.cli, '_parse_settings', return_value=expected_settings) as mock_parse_settings, \
             patch.object(drover.cli, 'Drover', autospec=drover.Drover) as mock_drover:
            drover.cli.main()
            mock_drover.assert_called_with(expected_settings, expected_stage_name, interactive=expected_interactive)
            mock_parse_arguments.assert_called()
            mock_parse_settings.assert_called_with(mock_arguments.settings_file)
