"""An ASGI application entry point to the XKCD API"""
import os
from pathlib import Path

from xkcd_api import create_app
from xkcd_api.models import read_api_settings

api_settings_file_name = Path(os.environ.get('API_SETTINGS_FILE', 'settings.yml'))
log_settings_file_name = Path(os.environ.get('LOG_SETTINGS_FILE', 'logging.yml'))

app = create_app(
    api_settings=read_api_settings(api_settings_file_name),
    log_settings_file_name=log_settings_file_name,
)
