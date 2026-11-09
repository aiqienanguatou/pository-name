import os
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

TARGET = os.getenv("ECH0_UPSTREAM", "http://127.0.0.1:6277").rstrip("/")
TIMEOUT = httpx.Timeout(connect=10.0, read=None, write=None, pool=10.0)

app = FastAPI(
    title="Ech0 reverse proxy",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Hop-by-hop headers must not be forwarded by a reverse proxy.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade",
}


@app.on_event("startup")
async def startup():
    app.state.client = httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=False,
    )


@app.on_event("shutdown")
async def shutdown():
    await app.state.client.aclose()


async def proxy(request: Request, path: str = ""):
    # Preserve the original path and query string.
    upstream_url = f"{TARGET}/{path}"
    if request.url.query:
        upstream_url += f"?{request.url.query}"

    headers = []
    for name, value in request.headers.raw:
        lname = name.decode("latin-1").lower()
        if lname not in HOP_BY_HOP and lname not in {
            "host", "content-length", "accept-encoding"
        }:
            headers.append((name, value))

    # Tell Ech0 that the public-facing request uses HTTPS.
    headers.extend([
        (b"x-forwarded-proto", b"https"),
        (b"x-forwarded-host", request.headers.get("host", "").encode("latin-1")),
    ])

    body = await request.body()
    upstream_request = app.state.client.build_request(
        method=request.method,
        url=upstream_url,
        headers=headers,
        content=body,
    )
    upstream_response = await app.state.client.send(
        upstream_request,
        stream=True,
    )

    response_headers = [
        (name, value)
        for name, value in upstream_response.headers.raw
        if name.decode("latin-1").lower() not in HOP_BY_HOP
    ]

    async def stream_body():
        try:
            async for chunk in upstream_response.aiter_raw():
                yield chunk
        finally:
            await upstream_response.aclose()

    response = StreamingResponse(
        stream_body(),
        status_code=upstream_response.status_code,
        background=BackgroundTask(upstream_response.aclose),
    )
    # Preserve repeated headers such as Set-Cookie.
    response.raw_headers = response_headers
    return response


@app.api_route("/", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_root(request: Request):
    return await proxy(request, "")


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_all(request: Request, path: str):
    return await proxy(request, path)
