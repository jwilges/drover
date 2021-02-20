from typing import Optional

from fastapi.params import Header
from fastapi.routing import APIRouter
from starlette.requests import Request

from xkcd_api.api import get_html_xkcd_comic, get_xkcd_comic

router = APIRouter(redirect_slashes=True)


@router.get('/')
def get(request: Request, accept: Optional[str] = Header(None)):
    comic = get_xkcd_comic()
    if 'text/html' in accept:
        return get_html_xkcd_comic(comic, request)
    return comic


@router.get('/{id}')
def get(id: int, request: Request, accept: Optional[str] = Header(None)):
    comic = get_xkcd_comic(id)
    if 'text/html' in accept:
        return get_html_xkcd_comic(comic, request)
    return comic
