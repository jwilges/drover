"""Command-line interface functionality for the Drover interface"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple

import yaml
from pydantic import ValidationError

from drover import Drover, SettingsError, UpdateError
from drover.__metadata__ import DESCRIPTION, VERSION
from drover.models import Settings

_logger = logging.getLogger(__name__)


class MaximumLogLevelLogFilter(logging.Filter):
    """A log filter to omit records greater or equal to a specified log level."""
    def __init__(self, maximum_level: int, name: str = ''):
        super().__init__(name=name)
        self.maximum_level = maximum_level

    def filter(self, record) -> bool:
        """Return `True` if the record log level does not meet or exceed the maximum log level."""
        return record.levelno < self.maximum_level


# yapf: disable
def _parse_arguments() -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
    root_parser = argparse.ArgumentParser(description=DESCRIPTION)
    # root_subparsers = root_parser.add_subparsers(dest='action', required=True)

    root_parser.add_argument('--version', '-V', action='version', version=f'%(prog)s {VERSION}')
    group = root_parser.add_mutually_exclusive_group()
    group.add_argument('--verbose', '-v', dest='verbosity', action='count', default=0,
                       help='increase output verbosity')
    group.add_argument('--quiet', '-q', dest='verbosity', action='store_const', const=None,
                       help='disable output')
    group = root_parser.add_mutually_exclusive_group()
    group.add_argument('--interactive', dest='interactive', action='store_true', default=sys.__stdin__.isatty(),
                       help='enable interactive output (i.e. for a PTY)')
    group.add_argument('--non-interactive', dest='interactive', action='store_false',
                       help='disable interactive output')

    root_parser.add_argument('--settings-file', default=Path('drover.yml'), type=Path,
                             help='Settings file name (default: "drover.yml")')
    root_parser.add_argument('--install-path', default=Path(), type=Path,
                             help='Package install path (e.g. from "pip install -t"; default: working directory)')
    root_parser.add_argument('stage', type=str)

    return root_parser, root_parser.parse_args()


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
# yapf: enable


def _configure_logging(verbosity: Optional[int]):
    if verbosity is not None:
        console_level = max(1, logging.INFO - (10 * verbosity))
        console_formatter = logging.Formatter(fmt='%(message)s')
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.addFilter(MaximumLogLevelLogFilter(logging.WARNING))
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(console_level)
        error_formatter = logging.Formatter(fmt='%(levelname)s: %(message)s')
        error_handler = logging.StreamHandler(sys.stderr)
        error_handler.setFormatter(error_formatter)
        error_handler.setLevel(logging.WARNING)
        logging.basicConfig(handlers=(console_handler, error_handler), level=console_level)
        _logger.setLevel(console_level)
    else:
        logging.basicConfig(handlers=(logging.NullHandler(), ))


def main():
    """The main command-line entry point for the Drover interface"""
    argument_parser, arguments = _parse_arguments()
    _configure_logging(arguments.verbosity)

    settings_file_name = arguments.settings_file
    install_path: Path = arguments.install_path

    settings: Settings = _parse_settings(settings_file_name)

    try:
        drover = Drover(settings, arguments.stage, interactive=arguments.interactive)
        drover.update(install_path)
    except SettingsError as e:
        _logger.error('Initialization failed: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)
    except UpdateError as e:
        _logger.error('Update failed: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)
