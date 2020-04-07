"""Command-line interface functionality for the Drover interface"""
import argparse
import logging
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from drover import __version__, Drover, SettingsError, UpdateError
from drover.models import Settings

_logger = logging.getLogger(__name__)


def _parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.partition('\n')[0])
    parser.add_argument('--version', '-V', action='version', version=f'%(prog)s {__version__}')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--verbose', '-v', action='count', default=0, help='increase output verbosity')
    group.add_argument('--quiet', action='store_true', help='disable output')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--interactive', action='store_true', help='enable interactive output (i.e. for a PTY)')
    group.add_argument('--non-interactive', action='store_true', help='disable interactive output')

    parser.add_argument('--settings-file', default=Path('drover.yml'), type=Path,
                        help='Settings file name (default: "drover.yml")')
    parser.add_argument('--install-path', default=Path(), type=Path,
                        help='Package install path (e.g. from "pip install -t"; default: working directory)')
    parser.add_argument('stage', type=str)
    return parser.parse_args()


def _parse_settings(settings_file_name: Path) -> Settings:
    try:
        with open(settings_file_name, 'r') as settings_file:
            return Settings.parse_obj(yaml.safe_load(settings_file))
    except (ValueError, ValidationError) as e:
        _logger.error('Settings file is invalid: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)
    except FileNotFoundError as e:
        _logger.error('Settings file does not exist: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)


def main():
    """The main command-line entry point for the Drover interface"""
    arguments = _parse_arguments()

    if not arguments.quiet:
        logging.basicConfig(format='%(message)s', stream=sys.stdout)
        logging_level = max(1, logging.INFO - (10 * arguments.verbose))
        logging.getLogger(__name__.split('.')[0]).setLevel(logging_level)

    interactive = True if arguments.interactive else False if arguments.non_interactive else sys.__stdin__.isatty()

    settings_file_name = arguments.settings_file
    install_path: Path = arguments.install_path

    settings: Settings = _parse_settings(settings_file_name)

    try:
        drover = Drover(settings, arguments.stage, interactive=interactive)
        drover.update(install_path)
    except SettingsError as e:
        _logger.error('Initialization failed: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)
    except UpdateError as e:
        _logger.error('Update failed: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)
