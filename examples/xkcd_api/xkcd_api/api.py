import logging
import re
from http import HTTPStatus
from pathlib import Path
from typing import Optional

import httpx
from fastapi.templating import Jinja2Templates
from jinja2 import Markup, escape
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse

from xkcd_api import state as api_state
from xkcd_api.models import XKCDComic

_logger = logging.getLogger(__name__)
_templates = Jinja2Templates(directory=Path(__file__).parent / 'templates')


def get_xkcd_comic(id: Optional[int] = None) -> XKCDComic:
    get_endpoint = f'/{id}/info.0.json' if id else '/info.0.json'
    request_url = f'{api_state.settings.xkcd_root_url}{get_endpoint}'
    _logger.info('XKCD request: %s', request_url)

    response = httpx.get(request_url)
    if response.is_error:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=response.content)
    r = XKCDComic.parse_obj(response.json())
    _logger.debug('XKCD response: %r', r)
    return r


def get_html_xkcd_comic(comic: XKCDComic, request: Request) -> HTMLResponse:
    def format_line(line: str) -> str:
        line = escape(line)
        emphasis_format = re.compile(r'^(?:\[\[(?P<emphasized>[^\]]+)\]\])(?P<suffix>.+)?')
        emphasis = emphasis_format.match(line)
        if emphasis:
            emphasis = emphasis.groupdict()
            line = f'<i>{emphasis["emphasized"]}</i>'
            if emphasis.get("suffix"):
                line += f' &mdash; {emphasis["suffix"]}'
        return Markup(f'<p>{line}</p>')

    formatted_text = (format_line(line) for line in comic.text.splitlines())
    return _templates.TemplateResponse(
        'comic.html.j2',
        context={
            'request': request,
            'title': comic.title,
            'image': comic.image,
            'text': formatted_text
        }
    )
