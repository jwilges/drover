import asyncio
import base64
import urllib.parse
from typing import Any, Callable, Iterable, MutableMapping, Sequence, Tuple

from starlette.types import Message

STRING_ENCODING = 'utf-8'


def _normalize(
    multi_mapping: MutableMapping[str, Sequence[str]],
    single_mapping: MutableMapping[str, str],
    encoding: str = None,
    lowercase_keys: bool = False
) -> Iterable[Tuple[object, object]]:
    if encoding:

        def _encode(value: str) -> bytes:
            return value.encode(encoding)
    else:

        def _encode(value: str) -> str:
            return value

    if multi_mapping:
        for key, value in multi_mapping.items():
            yield from (
                (_encode(key.lower() if lowercase_keys else key), _encode(subvalue))
                for subvalue in value
            )
    elif single_mapping:
        for key, value in single_mapping.items():
            yield (_encode(key.lower() if lowercase_keys else key), _encode(value))


def _last(headers: Iterable[Tuple[object, object]], key: object, default: object = None):
    values = tuple(v for k, v in headers if k == key)
    return values[-1] if values else default


class LambdaIntegration:
    @staticmethod
    def create_asgi_handler(
        create_application: Callable, **create_arguments
    ) -> Callable[[MutableMapping[str, object], object], Any]:
        def lambda_handler(event: MutableMapping[str, object],
                           context: object) -> MutableMapping[str, object]:
            """
            Route API Gateway -> Lambda proxy requests as ASGI requests.
            """
            loop = asyncio.get_event_loop()

            method = event['httpMethod']
            path = event['path']
            context_path = event['requestContext']['path']
            # Derive the root path by isolating the API Gateway Proxy's request context path prefix from the request path.
            # For example, if a request to `/example` proxied via an API Gateway deployed to stage `stg` had a request
            # context path of `/stg/example` and a request path of `/example`, the root path should be `/stg`.
            if path in context_path:
                root_path = context_path[:context_path.index(path)]
            else:
                root_path = ''
            # For details about 'multiValueQueryStringParameters' and 'multiValueHeaders', see:
            # <https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#apigateway-multivalue-headers-and-parameters>
            query_parameters: Sequence[Tuple[str, str]] = tuple(
                _normalize(
                    event.get('multiValueQueryStringParameters'),
                    event.get('queryStringParameters')
                )
            )
            headers: Sequence[Tuple[bytes, bytes]] = tuple(
                _normalize(
                    event.get('multiValueHeaders'),
                    event.get('headers'),
                    encoding=STRING_ENCODING,
                    lowercase_keys=True
                )
            )
            port = _last(headers, b'x-forwarded-port', b'').decode(STRING_ENCODING)
            port = int(port) if port else None
            # The client address is provided as the right-most address (that of the most recent proxy).
            # See: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For
            client = (
                _last(headers, b'x-forwarded-for',
                      b'').decode(STRING_ENCODING).split(',')[-1].strip() or None, port
            )
            server = (_last(headers, b'host', b'').decode(STRING_ENCODING) or None, port)
            scheme = _last(headers, b'x-forwarded-proto', b'http').decode(STRING_ENCODING)

            query_string: str = urllib.parse.urlencode(query_parameters)
            query_string_bytes: bytes = query_string.encode(STRING_ENCODING)

            # The connection scope to be used with the application instance
            scope = {
                'type': 'http',
                'http_version': '1.1',
                'scheme': scheme,
                'method': method,
                'root_path': root_path,
                'path': path,
                'query_string': query_string_bytes,
                'headers': headers,
                'client': client,
                'server': server,
                'aws': {
                    'event': event,
                    'context': context
                }
            }
            response = {}

            async def receive() -> Message:
                """
                An awaitable callable that will yield a new `Message` when one is available.
                """
                body = event['body'] or b''
                if event.get('isBase64Encoded', False):
                    body = base64.standard_b64decode(body)
                if isinstance(body, str):
                    body = body.encode(STRING_ENCODING)
                return {'type': 'http.request', 'body': body, 'more_body': False}

            async def send(message: Message) -> None:
                """
                An awaitable callable taking a single `Message` as a positional argument that will
                return once the send has been completed or the connection has been closed.
                """
                if message['type'] == 'http.response.start':
                    response['statusCode'] = message['status']
                    response['isBase64Encoded'] = False
                    response['headers'] = {
                        key.decode(STRING_ENCODING): value.decode(STRING_ENCODING)
                        for key, value in message['headers']
                    }
                if message['type'] == 'http.response.body':
                    response['body'] = message['body'].decode(STRING_ENCODING)

            app = create_application(**create_arguments, prefix=root_path)
            task = loop.create_task(app(scope, receive, send))
            loop.run_until_complete(task)

            return response

        return lambda_handler
