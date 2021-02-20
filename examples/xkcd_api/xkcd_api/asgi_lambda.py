"""An AWS API Gateway to Lambda proxy integration entry point to the XKCD API"""
import os
from pathlib import Path

from xkcd_api import create_app
from xkcd_api.aws import LambdaIntegration
from xkcd_api.models import read_api_settings

api_settings_file_name = Path(os.environ.get('API_SETTINGS_FILE', 'settings.yml'))

handler = LambdaIntegration.create_asgi_handler(
    create_application=create_app,
    api_settings=read_api_settings(api_settings_file_name),
)
