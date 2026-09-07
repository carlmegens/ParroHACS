"""Private per-account feed cache and bounded, authenticated photo delivery."""

from __future__ import annotations

import asyncio
import re
import secrets
import socket
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from io import BytesIO
from ipaddress import IPv6Address, ip_address, ip_network
from typing import Any
from urllib.parse import urljoin, urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult
from homeassistant.core import HomeAssistant
from PIL import Image, ImageOps, UnidentifiedImageError
from yarl import URL

from .api import ParroApi, ParroAuthError, ParroConnectionError, ParroError
from .const import DEFAULT_FEED_LIMIT, MAX_FEED_LIMIT, MAX_LIMIT

FEED_TTL = 300
STALE_TTL = 3600
MAX_FEED_CACHES = 4
MEDIA_REF_TTL = 1800
MAX_MEDIA_REFS = 256
IMAGE_TTL = 900
MAX_CACHED_IMAGES = 12
MAX_IMAGE_CACHE_BYTES = 12 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_EDGE = 1600
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 3
_NAT64 = (ip_network("64:ff9b::/96"), ip_network("64:ff9b:1::/48"))
_now = time.monotonic


class ParroMediaError(ParroError):
    """Photo is unavailable; never include a source URL in the exception."""

    def __init__(self) -> None:
        super().__init__("The Parro photo is unavailable")


def _public_ip(value: str) -> bool:
    try:
        address = ip_address(value)
    except ValueError:
        return False
    if not address.is_global or address.is_multicast or address.is_reserved:
        return False
    if isinstance(address, IPv6Address) and (
        address.scope_id is not None
        or address.ipv4_mapped is not None
        or address.sixtofour is not None
        or address.teredo is not None
        or any(address in network for network in _NAT64)
    ):
        return False
    return True


def _validated_url(value: Any) -> str:
    """Validate literals here; DNS answers are validated by the connector resolver."""
    if (
        not isinstance(value, str)
        or not 0 < len(value) <= 8192
        or any(ord(char) < 33 for char in value)
    ):
        raise ParroMediaError()
    try:
        # Validate the same canonical host aiohttp will connect to. IDNA can
        # turn Unicode digits/dots into an IP literal that bypasses DNS.
        parsed = URL(value)
        raw = urlsplit(value)
        hostname = parsed.host
        port = parsed.port
    except ValueError:
        raise ParroMediaError() from None
    if (
        parsed.scheme != "https"
        or not hostname
        or port not in (None, 443)
        or parsed.user is not None
        or parsed.password is not None
        or raw.username is not None
        or raw.password is not None
        or "#" in value
        or "%" in hostname
    ):
        raise ParroMediaError()
    host = hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ParroMediaError()
    try:
        ip_address(host)
    except ValueError:
        if "." not in host:
            raise ParroMediaError() from None
    else:
        if not _public_ip(host):
            raise ParroMediaError()
    return str(parsed)


class _PublicResolver(AbstractResolver):
    """Validate the exact DNS answers used for a connection, including reconnects."""

    def __init__(self) -> None:
        self._resolver = aiohttp.ThreadedResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        try:
            results = await self._resolver.resolve(host, port, family)
        except OSError, aiohttp.ClientError:
            raise ParroMediaError() from None
        if not results or any(not _public_ip(result["host"]) for result in results):
            raise ParroMediaError()
        return results

    async def close(self) -> None:
        await self._resolver.close()


class _PlainText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "template"):
            self.hidden += 1
        elif not self.hidden and tag in ("br", "p", "div", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "template"):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ("p", "div", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _plain_text(value: Any, maximum: int = 20000) -> str:
    if not isinstance(value, str):
        return ""
    parser = _PlainText()
    parser.feed(value[:maximum])
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()[:maximum]


def _decode_image(data: bytes) -> bytes:
    """Decode in the executor, then output a small JPEG with no original metadata."""
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                raise ParroMediaError()
            if (
                source.width <= 0
                or source.height <= 0
                or source.width * source.height > MAX_IMAGE_PIXELS
            ):
                raise ParroMediaError()
            source.seek(0)
            image = ImageOps.exif_transpose(source)
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
            rgba = image.convert("RGBA")
            clean = Image.new("RGB", rgba.size, "white")
            clean.paste(rgba, mask=rgba.getchannel("A"))
            result = BytesIO()
            clean.save(result, format="JPEG", quality=85, optimize=True)
            encoded = result.getvalue()
            if len(encoded) > MAX_OUTPUT_BYTES:
                raise ParroMediaError()
            return encoded
    except UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError:
        raise ParroMediaError() from None


@dataclass
class _FeedCache:
    value: dict[str, Any]
    created: float


@dataclass(repr=False)
class _MediaRef:
    url: str = field(repr=False)
    expires: float


@dataclass
class _ImageCache:
    data: bytes = field(repr=False)
    expires: float


class ParroFeed:
    """Cache feed responses across cards, retaining private source URLs only here."""

    def __init__(self, hass: HomeAssistant, api: ParroApi) -> None:
        self.hass = hass
        self.api = api
        self._feeds: OrderedDict[str | None, _FeedCache] = OrderedDict()
        self._refs: OrderedDict[str, _MediaRef] = OrderedDict()
        self._by_url: dict[str, str] = {}
        self._images: OrderedDict[str, _ImageCache] = OrderedDict()
        self._feed_lock = asyncio.Lock()
        self._image_lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None
        self._resolver: _PublicResolver | None = None
        self._closed = False

    def _require_open(self) -> None:
        if self._closed:
            raise ParroError("The Parro feed is closed")

    def _clear_data(self) -> None:
        self._feeds.clear()
        self._refs.clear()
        self._by_url.clear()
        self._images.clear()

    def _remove_ref(self, media_id: str) -> None:
        ref = self._refs.pop(media_id, None)
        if ref is not None:
            self._by_url.pop(ref.url, None)
        self._images.pop(media_id, None)

    def _prune(self) -> None:
        now = _now()
        for media_id, ref in list(self._refs.items()):
            if ref.expires <= now:
                self._remove_ref(media_id)
        for media_id, cached in list(self._images.items()):
            if cached.expires <= now:
                self._images.pop(media_id)
        for group_id, cached in list(self._feeds.items()):
            if now - cached.created > STALE_TTL:
                self._feeds.pop(group_id)

    def _media_id(self, url: str) -> str:
        if media_id := self._by_url.get(url):
            self._refs[media_id].expires = _now() + MEDIA_REF_TTL
            self._refs.move_to_end(media_id)
            return media_id
        media_id = secrets.token_urlsafe(24)
        self._refs[media_id] = _MediaRef(url, _now() + MEDIA_REF_TTL)
        self._by_url[url] = media_id
        while len(self._refs) > MAX_MEDIA_REFS:
            self._remove_ref(next(iter(self._refs)))
        return media_id

    def _build_feed(self, source: dict[str, Any]) -> dict[str, Any]:
        groups = [
            {"id": group["id"], "name": _plain_text(group.get("name"), 256)}
            for group in source["groups"]
        ]
        group_names = {group["id"]: group["name"] for group in groups}
        items = []
        for item in source["items"][:MAX_FEED_LIMIT]:
            images = []
            private_urls = set()
            seen_urls = set()
            for candidate in item.get("image_sources", [])[:3]:
                if isinstance(candidate.get("url"), str):
                    private_urls.add(candidate["url"])
                try:
                    url = _validated_url(candidate.get("url"))
                except ParroMediaError:
                    continue
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                private_urls.add(url)
                images.append(
                    {
                        "id": self._media_id(url),
                        "name": _plain_text(candidate.get("name"), 256) or "Foto",
                    }
                )

            def safe_text(value: Any, maximum: int = 20000) -> str:
                text = _plain_text(value, maximum)
                for private_url in private_urls:
                    text = text.replace(private_url, "")
                return text.strip()

            for image in images:
                image["name"] = safe_text(image["name"], 256) or "Foto"
            items.append(
                {
                    "id": item.get("id"),
                    "title": safe_text(item.get("title"), 1000),
                    "contents": safe_text(item.get("contents")),
                    "created_at": item.get("created_at"),
                    "sort_date": item.get("sort_date"),
                    "group_id": item.get("group_id"),
                    "group_name": group_names.get(item.get("group_id")),
                    "sender": safe_text(item.get("sender"), 256),
                    "images": images,
                }
            )
        return {"items": items, "groups": groups, "updated_at": datetime.now(UTC).isoformat()}

    def _response(self, cached: _FeedCache, limit: int, *, stale: bool) -> dict[str, Any]:
        result = deepcopy(cached.value)
        result["items"] = result["items"][:limit]
        for item in result["items"]:
            item["images"] = [image for image in item["images"] if image["id"] in self._refs]
            for image in item["images"]:
                self._refs.move_to_end(image["id"])
        return {**result, "returned": len(result["items"]), "limit": limit, "stale": stale}

    async def async_get_feed(
        self, limit: int = DEFAULT_FEED_LIMIT, group_id: str | None = None
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_FEED_LIMIT:
            raise ParroError("The Parro feed limit must be between 1 and 20")
        if group_id is not None and (
            not isinstance(group_id, str)
            or not re.fullmatch(r"[0-9]{1,20}", group_id)
            or int(group_id) <= 0
        ):
            raise ParroError("The selected Parro group is unavailable")
        async with self._feed_lock:
            self._require_open()
            self._prune()
            cached = self._feeds.get(group_id)
            if cached is not None and _now() - cached.created < FEED_TTL:
                self._feeds.move_to_end(group_id)
                return self._response(cached, limit, stale=False)
            try:
                source = await self.api._async_fetch_feed_source(limit=MAX_LIMIT, group_id=group_id)
            except ParroAuthError:
                self._clear_data()
                raise
            except ParroConnectionError:
                self._require_open()
                if cached is None:
                    raise
                return self._response(cached, limit, stale=True)
            self._require_open()
            cached = _FeedCache(self._build_feed(source), _now())
            self._feeds[group_id] = cached
            self._feeds.move_to_end(group_id)
            while len(self._feeds) > MAX_FEED_CACHES:
                self._feeds.popitem(last=False)
            return self._response(cached, limit, stale=False)

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._resolver = _PublicResolver()
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(
                    resolver=self._resolver, use_dns_cache=False, limit=2, force_close=True
                ),
                cookie_jar=aiohttp.DummyCookieJar(),
                timeout=aiohttp.ClientTimeout(total=15, connect=5, sock_read=5),
                trust_env=False,
                auto_decompress=False,
                headers={
                    "Accept": "image/jpeg,image/png,image/webp",
                    "User-Agent": "HomeAssistant-Parro",
                },
            )
        return self._session

    async def _download(self, source: str) -> bytes:
        url = _validated_url(source)
        try:
            async with asyncio.timeout(20):
                for _ in range(MAX_REDIRECTS + 1):
                    async with self._get_session().get(url, allow_redirects=False) as response:
                        if response.status in (301, 302, 303, 307, 308):
                            location = response.headers.get("Location")
                            if not location:
                                raise ParroMediaError()
                            url = _validated_url(urljoin(url, location))
                            continue
                        if (
                            response.status != 200
                            or response.headers.get("Content-Encoding", "identity").lower()
                            != "identity"
                        ):
                            raise ParroMediaError()
                        if (
                            response.content_length is not None
                            and response.content_length > MAX_DOWNLOAD_BYTES
                        ):
                            raise ParroMediaError()
                        data = bytearray()
                        async for chunk in response.content.iter_chunked(65536):
                            data.extend(chunk)
                            if len(data) > MAX_DOWNLOAD_BYTES:
                                raise ParroMediaError()
                        return bytes(data)
        except aiohttp.ClientError, TimeoutError, OSError, ValueError:
            raise ParroMediaError() from None
        raise ParroMediaError()

    async def async_get_image(self, media_id: str) -> tuple[bytes, str]:
        if not isinstance(media_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32}", media_id):
            raise ParroMediaError()
        async with self._image_lock:
            self._require_open()
            self._prune()
            if media_id not in self._refs:
                raise ParroMediaError()
            if cached := self._images.get(media_id):
                self._images.move_to_end(media_id)
                return cached.data, "image/jpeg"
            data = await self._download(self._refs[media_id].url)
            encoded = await self.hass.async_add_executor_job(_decode_image, data)
            self._require_open()
            if media_id not in self._refs:
                raise ParroMediaError()
            self._images[media_id] = _ImageCache(encoded, _now() + IMAGE_TTL)
            while (
                len(self._images) > MAX_CACHED_IMAGES
                or sum(len(item.data) for item in self._images.values()) > MAX_IMAGE_CACHE_BYTES
            ):
                self._images.popitem(last=False)
            return encoded, "image/jpeg"

    async def async_close(self) -> None:
        self._closed = True
        async with self._feed_lock, self._image_lock:
            if self._session is not None:
                await self._session.close()
                self._session = None
            if self._resolver is not None:
                await self._resolver.close()
                self._resolver = None
            self._clear_data()
