"""A demonstration REST API that proxies requests to the XKCD API (https://xkcd.com)"""
import logging
import logging.config
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from fastapi import FastAPI, Request

import xkcd_api.state as api_state
from xkcd_api.__metadata__ import DESCRIPTION, NAME, VERSION
from xkcd_api.models import APISettings
from xkcd_api.routes import router as root_router

_logger = logging.getLogger(__name__)


def create_app(
    api_settings: APISettings,
    log_settings_file_name: Optional[Path] = None,
    prefix: str = ""
) -> FastAPI:
    """Create a new FastAPI ASGI application

    Args:
        api_settings: environment-specific API settings
        log_settings_file_name: logging settings file name
    """

    log_settings: Optional[Dict[str, Any]] = None
    if log_settings_file_name:
        with open(log_settings_file_name, 'r') as log_settings_file:
            log_settings = yaml.safe_load(log_settings_file)

    if log_settings:
        logging.config.dictConfig(log_settings)
    else:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger().setLevel(logging.INFO)

    if not api_settings:
        raise ValueError('Application must be initialized with settings')
    api_state.settings = api_settings

    _logger.info(repr(api_settings))
    _logger.info('Initialized API settings and logging')

    api = FastAPI(
        title=NAME,
        description=DESCRIPTION,
        version=VERSION,
        openapi_prefix=prefix,
    )
    _logger.info(f'Initialized API v{VERSION}')

    @api.exception_handler(Exception)
    async def handle_exception(request: Request, error: Exception):
        _logger.error(f'URL: {request.url!s}', exc_info=error)

    api.include_router(root_router)
    _logger.info('Initialized API routes')

    return api
