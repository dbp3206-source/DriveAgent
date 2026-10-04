"""Bounded transport for Medium CDN images found in an owner's opened mail.

Not a general URL proxy. No mail text, OAuth cookie or provider key is forwarded.
The short-lived index is disposable; reopening the mail renews it after a restart.
"""

import asyncio
import hashlib
import ipaddress
import logging
import socket
import time
from collections import OrderedDict
from contextvars import ContextVar
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

import httpx

MAX_BYTES = 2_000_000
MAX_SOURCES = 2048
TTL_SECONDS = 600
TRUSTED_HOST = "miro.medium.com"
_private_image_request = ContextVar("private_mail_image_request", default=False)


class _ImageLogFilter(logging.Filter):
    def filter(self, record):
        # HTTPX normally logs the entire URL, which may contain mail-specific
        # query parameters. Suppress only this scoped image request, not other logs.
        return not _private_image_request.get()


logging.getLogger("httpx").addFilter(_ImageLogFilter())


class MailImageError(ValueError):
    pass


def supported_url(url: str) -> bool:
    if len(url) > 4096 or any(ord(ch) < 32 for ch in url):
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and parts.hostname == TRUSTED_HOST
                and parts.port in {None, 443} and not parts.username
                and not parts.password and not parts.fragment)
    except ValueError:
        return False


class _Images(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag.casefold() != "img" or len(self.urls) >= 192:
            return
        source = dict(attrs).get("src", "") or ""
        if supported_url(source):
            self.urls.add(source)


class MailImageIndex:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.sources: OrderedDict[tuple[str, str, str], tuple[float, str]] = OrderedDict()

    def register(self, owner: str, message: str, html: str) -> dict[str, str]:
        parser = _Images()
        parser.feed(html)
        result = {}
        for url in sorted(parser.urls):
            identifier = hashlib.sha256(url.encode()).hexdigest()
            key = (owner, message, identifier)
            self.sources[key] = (self.clock() + TTL_SECONDS, url)
            self.sources.move_to_end(key)
            result[url] = f"/api/gmail/messages/{quote(message, safe='')}/images/{identifier}"
        while len(self.sources) > MAX_SOURCES:
            self.sources.popitem(last=False)
        return result

    def lookup(self, owner: str, message: str, identifier: str) -> str | None:
        key = (owner, message, identifier)
        record = self.sources.get(key)
        if not record:
            return None
        if record[0] <= self.clock():
            del self.sources[key]
            return None
        return record[1]


async def _public_destination(url: str):
    if not supported_url(url):
        raise MailImageError("Máy chủ ảnh không được hỗ trợ.")
    records = await asyncio.to_thread(socket.getaddrinfo, TRUSTED_HOST, 443,
                                      type=socket.SOCK_STREAM)
    if not records or any(not ipaddress.ip_address(record[4][0]).is_global
                          for record in records):
        raise MailImageError("Không tải ảnh từ địa chỉ nội bộ.")


def _raster_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise MailImageError("Nội dung nhận được không phải ảnh được hỗ trợ.")


async def fetch_mail_image(url: str, client: httpx.AsyncClient) -> tuple[bytes, str]:
    token = _private_image_request.set(True)
    try:
        return await _fetch_mail_image(url, client)
    finally:
        _private_image_request.reset(token)


async def _fetch_mail_image(url: str, client: httpx.AsyncClient) -> tuple[bytes, str]:
    async with asyncio.timeout(12):
        current = url
        for _ in range(3):
            await _public_destination(current)
            async with client.stream("GET", current, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    current = urljoin(current, response.headers.get("location", ""))
                    if not supported_url(current):
                        raise MailImageError("Ảnh chuyển tới máy chủ không được hỗ trợ.")
                    continue
                response.raise_for_status()
                if response.headers.get("content-type", "").split(";", 1)[0].lower() not in {
                    "image/png", "image/jpeg", "image/gif", "image/webp",
                }:
                    raise MailImageError("Máy chủ không trả về ảnh được hỗ trợ.")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise MailImageError("Ảnh vượt giới hạn dung lượng.")
                    chunks.append(chunk)
                content = b"".join(chunks)
                return content, _raster_type(content)
        raise MailImageError("Ảnh chuyển hướng quá nhiều lần.")
