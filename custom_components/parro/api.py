"""Bounded, read-only adapter around parro 1.1.0.

The CLI SDK normally writes OAuth tokens to the user's home directory. Each
adapter owns a separately loaded SDK module whose storage hooks are disabled;
the installed module is never monkeypatched. All SDK imports and HTTP calls
run in Home Assistant's executor.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import inspect
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from types import ModuleType, SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from homeassistant.core import HomeAssistant

from .const import DEFAULT_LIMIT, MAX_LIMIT


class ParroError(Exception):
    """Unsupported or malformed response, without private server details."""


class ParroAuthError(ParroError):
    """The account requires a new sign-in."""


class ParroConnectionError(ParroError):
    """The server could not be reached or is temporarily unavailable."""


class ParroLoginFlowError(ParroError):
    """A technical sign-in failure with a safe, finite diagnostic reason."""

    REASONS = frozenset(
        {
            "state_mismatch",
            "login_not_completed",
            "token_exchange_failed",
            "unexpected_destination",
            "redirect_limit",
            "unsupported_account_chooser",
            "unsupported_login_form",
        }
    )

    def __init__(self, reason: str) -> None:
        if not isinstance(reason, str) or reason not in self.REASONS:
            raise ValueError("Unsupported Parro login failure reason")
        super().__init__(reason)
        self.reason = reason


class ParroAccountSelectionRequired(ParroError):
    """The IDP requires an explicit identity choice."""

    def __init__(self, accounts: list[dict[str, str]]) -> None:
        super().__init__("Choose a Parro identity")
        self.accounts = accounts


@dataclass(frozen=True)
class LoginResult:
    """Only tokens and the verified account ID survive the config flow."""

    tokens: dict[str, Any]
    account_id: str
    title: str


def _error(err: Exception, *, login: bool = False, refresh: bool = False) -> ParroError:
    if isinstance(err, ParroError):
        return err
    if isinstance(err, httpx.HTTPStatusError):
        status = err.response.status_code
        if status == 429 or status >= 500:
            return ParroConnectionError("Parro is temporarily unavailable")
        if login and err.request.url.path == "/idp/oauth2/token":
            return ParroLoginFlowError("token_exchange_failed")
        if status in (401, 403) or (refresh and status == 400):
            return ParroAuthError("Parro sign-in has expired or was rejected")
    if isinstance(err, httpx.RequestError):
        return ParroConnectionError("Unable to reach Parro")
    # SDK RuntimeErrors may contain credentials, account names, or token bodies.
    if login:
        if isinstance(err, RuntimeError):
            if str(err).startswith("Token exchange mislukt"):
                return ParroLoginFlowError("token_exchange_failed")
            if str(err).startswith("Kon het login formulier niet vinden"):
                return ParroLoginFlowError("unsupported_login_form")
        # The SDK's HTML substring check and generic failure cannot establish
        # that credentials were rejected. Never surface their raw messages.
        return ParroLoginFlowError("login_not_completed")
    return ParroError("Parro returned an unsupported response")


def _tokens(data: Any, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("access_token"), str):
        raise ParroAuthError("Parro did not return an access token")
    if not data["access_token"]:
        raise ParroAuthError("Parro did not return an access token")
    result: dict[str, Any] = {"access_token": data["access_token"]}
    refresh = data.get("refresh_token", (previous or {}).get("refresh_token"))
    if isinstance(refresh, str) and refresh:
        result["refresh_token"] = refresh
    expires = data.get("expires_in")
    if isinstance(expires, (int, float)) and not isinstance(expires, bool) and expires > 0:
        result["expires_at"] = time.time() + expires
    elif isinstance(data.get("expires_at"), (int, float)):
        result["expires_at"] = data["expires_at"]
    return result


def _id(item: Any, relation: str = "self") -> str | None:
    if not isinstance(item, dict):
        return None
    links = item.get("links", [])
    if isinstance(links, list):
        for link in links:
            if isinstance(link, dict) and link.get("rel") == relation:
                value = link.get("id")
                if isinstance(value, (str, int)) and not isinstance(value, bool):
                    return str(value) if str(value) else None
    if relation == "self":
        value = item.get("id")
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value) if str(value) else None
    return None


def _text(value: Any, maximum: int = 20000) -> str | None:
    return value[:maximum] if isinstance(value, str) else None


def _number(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _name(identity: Any) -> str | None:
    if not isinstance(identity, dict):
        return None
    if display := _text(identity.get("displayName"), 256):
        return display
    parts = [_text(identity.get(key), 100) for key in ("firstName", "surnamePrefix", "surname")]
    return " ".join(part for part in parts if part) or None


def _items(data: Any) -> list[dict[str, Any]]:
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ParroError("Parro returned an unsupported collection")
    return items


def _limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        raise ParroError(f"Limit must be between 1 and {MAX_LIMIT}")
    return limit


def _sdk_module() -> ModuleType:
    """Load an isolated SDK instance; called only inside the executor."""
    spec = importlib.util.find_spec("parro.client")
    if spec is None or spec.origin is None:
        raise ParroError("The Parro SDK is unavailable")
    isolated = importlib.util.spec_from_file_location("parro._homeassistant_client", spec.origin)
    if isolated is None or isolated.loader is None:
        raise ParroError("The Parro SDK is unavailable")
    module = importlib.util.module_from_spec(isolated)
    isolated.loader.exec_module(module)
    module._save_tokens = lambda _data: None
    module._load_tokens = lambda: None

    class AuthClient(httpx.Client):
        """Keep credentials on the IDP origin and verify OAuth state."""

        _oauth_state: str | None = None
        _request_count = 0

        def send(self, request: httpx.Request, **kwargs: Any) -> httpx.Response:
            self._request_count += 1
            if self._request_count > 40:
                raise ParroLoginFlowError("redirect_limit")
            if (
                request.url.scheme != "https"
                or request.url.host != "inloggen.parnassys.net"
                or request.url.port not in (None, 443)
                or request.url.username
                or request.url.password
            ):
                raise ParroLoginFlowError("unexpected_destination")
            if request.url.path == "/idp/oauth2/authorize":
                states = request.url.params.get_list("state")
                if self._oauth_state is None:
                    if len(states) != 1 or not states[0]:
                        raise ParroLoginFlowError("state_mismatch")
                    self._oauth_state = states[0]
                elif states and states != [self._oauth_state]:
                    raise ParroLoginFlowError("state_mismatch")
            response = super().send(request, **kwargs)
            if response.is_error:
                response.raise_for_status()
            location = response.headers.get("location", "")
            if location.startswith("parro://"):
                _check_state(location, self._oauth_state)
            return response

    module.httpx = SimpleNamespace(Client=AuthClient, Response=httpx.Response, post=httpx.post)

    def choose_account(client: Any, page_url: str, html: str, account: str | None) -> str:
        choices = module._parse_account_chooser(html)
        if not choices:
            raise ParroLoginFlowError("unsupported_account_chooser")
        selectors: dict[str, dict[str, str]] = {}
        for choice in choices:
            fingerprint = f"{choice['name']}\0{choice['role']}"
            choice_id = hashlib.sha256(fingerprint.encode()).hexdigest()[:24]
            if choice_id in selectors or not choice["name"]:
                raise ParroLoginFlowError("unsupported_account_chooser")
            selectors[choice_id] = choice
        if account is None:
            raise ParroAccountSelectionRequired(
                [
                    {
                        "id": key,
                        "name": f"{value['name']} ({value['role']})"
                        if value["role"]
                        else value["name"],
                    }
                    for key, value in selectors.items()
                ]
            )
        if account not in selectors:
            raise ParroLoginFlowError("unsupported_account_chooser")
        chosen = selectors[account]
        base = re.search(r'Wicket\.Ajax\.baseUrl="([^"]*)"', html)
        response = client.get(
            urljoin(page_url, chosen["url"]),
            headers={
                "Wicket-Ajax": "true",
                "Wicket-Ajax-BaseURL": base.group(1) if base else urlparse(page_url).path,
                "Wicket-FocusedElementId": chosen["focus_id"],
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        response.raise_for_status()
        location = response.headers.get("ajax-location", "")
        if not location:
            redirect = re.search(r"<redirect><!\[CDATA\[(.*?)\]\]></redirect>", response.text)
            location = redirect.group(1) if redirect else ""
        if not location:
            raise ParroLoginFlowError("unsupported_account_chooser")
        if location.startswith("parro://"):
            _check_state(location, client._oauth_state)
        return location

    module._choose_account = choose_account
    sdk_client = module.ParroClient

    class BoundedClient(sdk_client):
        """Validate SDK envelopes and make at most one request per collection."""

        def __enter__(self) -> Any:
            # Always pass an explicit access token, never the CLI token lookup.
            self._client = httpx.Client(
                base_url=module.REST_API,
                timeout=30,
                headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
            )
            self.complete: dict[str, bool] = {}
            return self

        def _items(self, path: str, **params: Any) -> list[dict[str, Any]]:
            return self._collection(path, 100, **params)

        def _items_paged(self, path: str, limit: int, **params: Any) -> list[dict[str, Any]]:
            return self._collection(path, _limit(limit), **params)

        def _collection(self, path: str, limit: int, **params: Any) -> list[dict[str, Any]]:
            response = self._client.get(
                path, params=params or None, headers={"Range": f"items=0-{limit - 1}"}
            )
            if response.status_code == 416:
                self.complete[path] = True
                return []
            response.raise_for_status()
            items = _items(response.json())
            # Totals are unreliable: never use them as the count. A total that
            # suggests more data still makes a short page unsafe to count.
            content_range = re.fullmatch(
                r"items\s+(\d+)-(\d+)/(\d+|\*)", response.headers.get("Content-Range", "")
            )
            more_reported = bool(
                content_range
                and content_range.group(3) != "*"
                and int(content_range.group(3)) > len(items)
            )
            self.complete[path] = len(items) < limit and not more_reported
            return items[:limit]

    module.ParroClient = BoundedClient
    return module


def _check_state(location: str, expected: str | None) -> None:
    parsed = urlparse(location)
    values = parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme != "parro"
        or parsed.netloc != "oauth2"
        or parsed.path
        or not expected
        or values.get("state") != [expected]
    ):
        raise ParroLoginFlowError("state_mismatch")


async def async_login(
    hass: HomeAssistant, username: str, password: str, account_id: str | None = None
) -> LoginResult:
    """Authenticate without saving credentials or selecting the first identity."""
    if (
        not isinstance(username, str)
        or not username.strip()
        or not isinstance(password, str)
        or not password
    ):
        raise ParroAuthError("Enter a username and password")

    def login() -> LoginResult:
        try:
            module = _sdk_module()
            raw_tokens = module.ParroAuth.login(username, password, account=account_id)
            try:
                tokens = _tokens(raw_tokens)
            except ParroAuthError:
                raise ParroLoginFlowError("token_exchange_failed") from None
            with module.ParroClient(tokens["access_token"]) as client:
                account = client.get_account()
            verified_id = _id(account)
            if not verified_id:
                raise ParroLoginFlowError("login_not_completed")
            return LoginResult(tokens, verified_id, "Parro")
        except Exception as err:
            raise _error(err, login=True) from None

    return await hass.async_add_executor_job(login)


def _attachments(value: Any) -> list[dict[str, Any]]:
    """Allow only metadata; never attachment URLs or embedded/private objects."""
    if not isinstance(value, list):
        return []
    result = []
    for attachment in value[:MAX_LIMIT]:
        if not isinstance(attachment, dict):
            continue
        entries = attachment.get("entries", [])
        result.append(
            {
                "id": _id(attachment),
                "name": _text(attachment.get("name", attachment.get("filename")), 256),
                "type": _text(attachment.get("attachmentType"), 100),
                "size": _number(attachment.get("size")),
                "entries": [
                    {
                        "type": _text(entry.get("type"), 100),
                        "size": _number(entry.get("size")),
                        "mime_type": _text(entry.get("mimeType"), 100),
                    }
                    for entry in entries[:10]
                    if isinstance(entry, dict)
                ]
                if isinstance(entries, list)
                else [],
            }
        )
    return result


class ParroApi:
    """Serialize SDK access, refresh once on 401, and keep tokens in HA."""

    def __init__(
        self,
        hass: HomeAssistant,
        tokens: dict[str, Any],
        account_id: str,
        on_tokens_changed: Callable[[dict[str, Any]], Any],
    ) -> None:
        self.hass = hass
        self._tokens = _tokens(tokens)
        self._last_notified = dict(self._tokens)
        self._account_id = str(account_id)
        self._on_tokens_changed = on_tokens_changed
        self._async_lock = asyncio.Lock()
        self._thread_lock = Lock()
        self._closed = False
        self._sdk: ModuleType | None = None
        self._client: Any = None
        self._verified = False

    def _ensure_client(self) -> None:
        if self._sdk is None:
            self._sdk = _sdk_module()
        if self._client is None:
            self._client = self._sdk.ParroClient(self._tokens["access_token"])
            self._client.__enter__()
            self._verified = False

    def _refresh(self) -> None:
        refresh = self._tokens.get("refresh_token")
        if not refresh:
            raise ParroAuthError("Parro requires a new sign-in")
        try:
            updated = _tokens(self._sdk.ParroAuth.refresh(refresh), self._tokens)
        except Exception as err:
            raise _error(err, refresh=True) from None
        if self._client:
            self._client.__exit__(None, None, None)
            self._client = None
        self._tokens = updated
        self._ensure_client()

    def _invoke(self, operation: Callable[[Any], Any]) -> Any:
        if not self._verified:
            if _id(self._client.get_account()) != self._account_id:
                raise ParroAuthError("Parro returned a different account")
            self._verified = True
        return operation(self._client)

    def _execute(
        self, operation: Callable[[Any], Any]
    ) -> tuple[Any, ParroError | None, dict[str, Any]]:
        with self._thread_lock:
            try:
                if self._closed:
                    raise ParroError("The Parro connection is closed")
                self._ensure_client()
                expired = self._tokens.get("expires_at", float("inf")) <= time.time() + 60
                if expired:
                    self._refresh()
                try:
                    result = self._invoke(operation)
                except httpx.HTTPStatusError as err:
                    if err.response.status_code != 401 or expired:
                        raise
                    self._refresh()
                    result = self._invoke(operation)
                return result, None, dict(self._tokens)
            except Exception as err:
                return None, _error(err), dict(self._tokens)

    async def _async_call(self, operation: Callable[[Any], Any]) -> Any:
        async with self._async_lock:
            # A refresh may rotate its token even if the caller is cancelled.
            # Drain the executor and save that token before releasing the lock.
            job = self.hass.async_add_executor_job(self._execute, operation)
            cancelled = False
            while True:
                try:
                    result, error, tokens = await asyncio.shield(job)
                    break
                except asyncio.CancelledError:
                    if job.cancelled():
                        # HA may cancel the executor future itself on shutdown;
                        # it can no longer be drained. Never spin on that future.
                        raise
                    cancelled = True
            if tokens != self._last_notified:
                changed = self._on_tokens_changed(dict(tokens))
                if inspect.isawaitable(changed):
                    await changed
                self._last_notified = tokens
            if cancelled:
                raise asyncio.CancelledError
            if error:
                raise error from None
            return result

    async def async_fetch_summary(self) -> dict[str, int | None]:
        """Poll counters only; a capped collection cannot supply an exact total."""

        def summary(client: Any) -> dict[str, int | None]:
            children = client.get_children()
            groups = client.get_groups()
            unread = client.get_unread_counts()

            def total(key: str) -> int | None:
                values = [_number(item.get(key)) for item in unread]
                if (
                    not values
                    or not client.complete["/identity/unreadcounts"]
                    or any(value is None for value in values)
                ):
                    return None
                return sum(values)

            return {
                "children_count": len(children) if client.complete["/child"] else None,
                "groups_count": len(groups) if client.complete["/group"] else None,
                "unread_announcements": total("numberOfUnreadAnnouncements"),
                "unread_chatrooms": total("numberOfUnreadChatRooms"),
            }

        return await self._async_call(summary)

    async def async_get_announcements(self, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
        limit = _limit(limit)
        items = await self._async_call(lambda client: client.get_announcements(limit=limit))
        return [
            {
                "id": _id(item),
                "title": _text(item.get("title"), 1000),
                "contents": _text(item.get("contents")),
                "created_at": _text(item.get("createdAt"), 100),
                "sort_date": _text(item.get("sortDate"), 100),
                "read": item.get("read") if isinstance(item.get("read"), bool) else None,
                "sender": _name(item.get("owner")),
                "group_id": _id(item, "group"),
                "attachments": _attachments(item.get("attachments")),
            }
            for item in items[:limit]
        ]

    async def async_get_chatrooms(self, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
        limit = _limit(limit)
        items = await self._async_call(lambda client: client._items_paged("/chatroom", limit))
        return [
            {
                "id": _id(item),
                "title": _text(item.get("title", item.get("subject", item.get("name"))), 1000),
                "type": _text(item.get("type"), 100),
                "sort_date": _text(item.get("sortDate"), 100),
                "unread_count": _number(item.get("unreadCount")),
            }
            for item in items[:limit]
        ]

    async def async_get_messages(
        self, chatroom_id: str | int, limit: int = DEFAULT_LIMIT
    ) -> list[dict[str, Any]]:
        limit = _limit(limit)
        if (
            isinstance(chatroom_id, bool)
            or not isinstance(chatroom_id, (str, int))
            or not re.fullmatch(r"[0-9]{1,20}", str(chatroom_id))
            or int(chatroom_id) <= 0
        ):
            raise ParroError("Chatroom ID must be a positive numeric ID")
        items = await self._async_call(
            lambda client: client.get_chat_messages(int(chatroom_id), limit=limit)
        )
        return [
            {
                "id": _id(item),
                "text": _text(item.get("text", item.get("contents"))),
                "created_at": _text(item.get("createdAt"), 100),
                "last_modified_at": _text(item.get("lastModifiedAt"), 100),
                "read": item.get("read") if isinstance(item.get("read"), bool) else None,
                "sender": _name(item.get("identity")),
                "attachments": _attachments(item.get("attachments")),
            }
            for item in items[:limit]
        ]

    async def async_get_calendar_urls(self, limit: int = DEFAULT_LIMIT) -> list[str]:
        limit = _limit(limit)

        def calendar(client: Any) -> list[str]:
            data = client._get("/calendar/sync")
            if not isinstance(data, dict) or not isinstance(data.get("strings"), list):
                raise ParroError("Parro returned unsupported calendar URLs")
            urls = data["strings"]
            if any(
                not isinstance(url, str)
                or urlparse(url).scheme not in ("https", "webcal")
                or not urlparse(url).netloc
                for url in urls
            ):
                raise ParroError("Parro returned unsupported calendar URLs")
            return urls[:limit]

        return await self._async_call(calendar)

    async def async_close(self) -> None:
        """Wait for in-flight HTTP calls before closing the client, once."""

        def close() -> None:
            with self._thread_lock:
                self._closed = True
                if self._client:
                    self._client.__exit__(None, None, None)
                    self._client = None

        async with self._async_lock:
            await self.hass.async_add_executor_job(close)
