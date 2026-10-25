from typing import Annotated, cast

import httpx
from fastapi import Depends, Request


def get_http_client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.http_client)


HttpClientDependency = Annotated[httpx.AsyncClient, Depends(get_http_client)]
