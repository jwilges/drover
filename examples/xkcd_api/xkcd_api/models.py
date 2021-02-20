from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic.networks import AnyHttpUrl


class APISettings(BaseModel):
    """XKCD API settings"""
    xkcd_root_url: AnyHttpUrl


class XKCDComic(BaseModel):
    """XKCD comic metadata"""
    title: str
    image: str = Field('', alias='img')
    alt: str = ''
    transcript: Optional[str] = ''

    @property
    def text(self) -> str:
        return self.transcript or self.alt


def read_api_settings(settings_file_name: Path) -> APISettings:
    with open(settings_file_name, 'r') as settings_file:
        settings = yaml.safe_load(settings_file)
    return APISettings.parse_obj(settings)
