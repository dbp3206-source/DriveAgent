import logging
import socket
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app.services import mail_images
from app.services.mail_images import MailImageError, MailImageIndex, fetch_mail_image, supported_url

URL = "https://miro.medium.com/max/1200/logo.png"
PNG = b"\x89PNG\r\n\x1a\n" + b"test-image"


@pytest.mark.parametrize("url", [
    "http://miro.medium.com/a.png", "https://127.0.0.1/a.png",
    "https://miro.medium.com.evil.test/a.png", "https://miro.medium.com@localhost/a.png",
    "https://miro.medium.com:8443/a.png", "https://miro.medium.com/a.png#fragment",
    "https://miro.medium.com/a\n.png", "https://medium.com/_/stat?event=opened",
])
def test_transport_is_not_an_arbitrary_or_tracking_url_proxy(url):
    assert not supported_url(url)


def test_sources_are_bound_to_owner_opened_message_and_expire():
    clock = [0]
    index = MailImageIndex(lambda: clock[0])
    sources = index.register("owner-a", "message/1", f'<img src="{URL}"><a href="{URL}">x</a>')
    identifier = sources[URL].rsplit("/", 1)[1]
    assert "message%2F1" in sources[URL]
    assert index.lookup("owner-a", "message/1", identifier) == URL
    assert index.lookup("owner-b", "message/1", identifier) is None
    assert index.lookup("owner-a", "another", identifier) is None
    assert index.register("owner-a", "empty", '<img src="https://localhost/a.png">') == {}
    clock[0] = 601
    assert index.lookup("owner-a", "message/1", identifier) is None


def test_index_has_a_hard_memory_bound(monkeypatch):
    monkeypatch.setattr(mail_images, "MAX_SOURCES", 2)
    index = MailImageIndex()
    for i in range(3):
        index.register("owner", str(i), f'<img src="{URL}?version={i}">')
    assert len(index.sources) == 2


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    ])


@pytest.mark.asyncio
async def test_fetch_raster_without_cookies_or_authorization(public_dns):
    def respond(request):
        assert "authorization" not in request.headers
        assert "cookie" not in request.headers
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await fetch_mail_image(URL, client) == (PNG, "image/png")


@pytest.mark.asyncio
async def test_internal_dns_is_refused_before_request(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
    ])
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: pytest.fail("internal address must never be fetched")
    )) as client:
        with pytest.raises(MailImageError):
            await fetch_mail_image(URL, client)


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["https://localhost/a", "http://miro.medium.com/a",
                                     "https://evil.test/a"])
async def test_redirect_cannot_escape_trusted_cdn(public_dns, target):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(302, headers={"location": target})
    )) as client:
        with pytest.raises(MailImageError):
            await fetch_mail_image(URL, client)


@pytest.mark.asyncio
@pytest.mark.parametrize("data,mime", [(b"<script>bad</script>", "image/png"),
                                      (PNG, "text/html"), (b"<svg/>", "image/svg+xml")])
async def test_active_or_mislabeled_content_is_refused(public_dns, data, mime):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=data, headers={"content-type": mime})
    )) as client:
        with pytest.raises(MailImageError):
            await fetch_mail_image(URL, client)


@pytest.mark.asyncio
async def test_oversize_is_refused_not_truncated(public_dns, monkeypatch):
    monkeypatch.setattr(mail_images, "MAX_BYTES", 4)
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    )) as client:
        with pytest.raises(MailImageError):
            await fetch_mail_image(URL, client)


@pytest.mark.asyncio
async def test_endpoint_refuses_other_owner_and_unknown_role(monkeypatch):
    from app.api import gmail
    index = MailImageIndex()
    sources = index.register("owner-a", "message", f'<img src="{URL}">')
    identifier = sources[URL].rsplit("/", 1)[1]
    monkeypatch.setattr(gmail, "_mail_images", index)
    with pytest.raises(HTTPException) as error:
        await gmail.external_image(
            "message", identifier, SimpleNamespace(id="owner-b", role="viewer")
        )
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        await gmail.external_image(
            "message", identifier, SimpleNamespace(id="owner-a", role="unknown")
        )
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_mail_image_url_is_not_printed_in_httpx_logs(public_dns, caplog):
    caplog.set_level(logging.INFO, logger="httpx")
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    )) as client:
        await fetch_mail_image(URL + "?mail_private=opaque", client)
        await client.get("https://public.example/ordinary")
    assert "mail_private" not in caplog.text
    assert "public.example/ordinary" in caplog.text
