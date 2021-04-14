"""Command-line interface functionality for the Drover interface"""
import argparse
import logging
import sys
from pathlib import Path
from typing import IO, Optional, Tuple

import yaml
from pydantic import ValidationError

from drover import Drover, SettingsError, UpdateError
from drover.__metadata__ import DESCRIPTION, VERSION
from drover.models import Settings

_logger = logging.getLogger(__name__)


class LogLevelRangeFilter(logging.Filter):
    """A log filter to omit records outside of an inclusive log level range."""
    def __init__(
        self,
        minimum_level: int = logging.NOTSET,
        maximum_level: int = logging.CRITICAL,
        name: str = ''
    ):
        super().__init__(name=name)
        self.minimum_level = minimum_level
        self.maximum_level = maximum_level

    def filter(self, record) -> bool:
        """Return `True` if the record log level is in the range `[minimum_level, maximum_level]`."""
        return record.levelno >= self.minimum_level and record.levelno <= self.maximum_level


# yapf: disable
def _parse_arguments() -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
    root_parser = argparse.ArgumentParser(description=DESCRIPTION)

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
    root_parser.add_argument('package', type=str)

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


def _get_stream_handler(
    stream: IO,
    log_format: str,
    minimum_level: int = logging.NOTSET,
    maximum_level: int = logging.CRITICAL
) -> logging.Handler:
    formatter = logging.Formatter(fmt=log_format)
    handler = logging.StreamHandler(stream)
    handler.addFilter(LogLevelRangeFilter(minimum_level, maximum_level))
    handler.setFormatter(formatter)
    handler.setLevel(minimum_level)
    return handler


def _configure_logging(verbosity: Optional[int] = None):
    if verbosity is not None:
        package_level = max(1, logging.INFO - (10 * verbosity))
        external_level = package_level if package_level < logging.DEBUG else logging.WARNING

        package_handlers = (
            _get_stream_handler(sys.stdout, '%(message)s', package_level, logging.WARNING - 1),
            _get_stream_handler(sys.stderr, '%(levelname)s: %(message)s', logging.WARNING),
        )
        root_handlers = (
            _get_stream_handler(
                sys.stdout, '%(name)s: %(message)s', external_level, logging.WARNING - 1
            ),
            _get_stream_handler(
                sys.stderr, '%(levelname)s: %(name)s: %(message)s', logging.WARNING
            ),
        )
        logging.basicConfig(handlers=root_handlers, level=external_level)

        package_logger = logging.getLogger(Drover.__module__)
        package_logger.setLevel(package_level)
        package_logger.propagate = False
        for handler in package_handlers:
            package_logger.addHandler(handler)
    else:
        logging.basicConfig(handlers=(logging.NullHandler(), ))


def main():
    """The main command-line entry point for the Drover interface"""
    _argument_parser, arguments = _parse_arguments()
    _configure_logging(arguments.verbosity)

    settings_file_name = arguments.settings_file
    install_path: Path = arguments.install_path

    settings: Settings = _parse_settings(settings_file_name)

    try:
        drover = Drover(settings, arguments.package, interactive=arguments.interactive)
        drover.update(install_path)
    except SettingsError as e:
        _logger.error('Initialization failed: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)
    except UpdateError as e:
        _logger.error('Update failed: %s', e)
        _logger.debug('', exc_info=e)
        sys.exit(1)
