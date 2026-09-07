"""Exercise the pinned SDK against an entirely synthetic HTTP transport."""

import asyncio
import importlib
from pathlib import Path
from threading import Event, get_ident
from urllib.parse import parse_qs

import httpx
import pytest

from custom_components.parro.api import (
    ParroAccountSelectionRequired,
    ParroApi,
    ParroAuthError,
    ParroConnectionError,
    ParroError,
    async_login,
)

IDP = "https://inloggen.parnassys.net"
API = "https://rest-v2.parro.com/rest/v2"
ACCOUNT = {"email": "synthetic@example.invalid", "links": [{"rel": "self", "id": 81}]}
TOKENS = {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"}


@pytest.fixture
def server(monkeypatch):
    """Route actual sync httpx requests, including SDK auth, to one handler."""
    original_init = httpx.Client.__init__
    requests = []
    request_threads = []
    state = {"handler": lambda request: httpx.Response(500)}

    def handle(request):
        requests.append(request)
        request_threads.append(get_ident())
        return state["handler"](request)

    def client_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handle)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", client_init)
    state.update(requests=requests, threads=request_threads)
    return state


def login_server(server, *, choices=None, wrong_state=False, action="/login"):
    state = {}

    def handler(request):
        if request.url.path == "/idp/oauth2/authorize":
            state["oauth_state"] = request.url.params["state"]
            return httpx.Response(
                200,
                text=f'<form action="{action}"><input type="email" name="emailadres"><input type="password" name="wachtwoord"><input type="hidden" name="csrf" value="synthetic-csrf"></form>',
            )
        if request.url.path == "/login":
            state["credentials"] = parse_qs(request.content.decode())
            if choices is not None:
                markup = "accountKeuze"
                for index, (name, role) in enumerate(choices):
                    markup += f'<li id="id{index}"><span class="account-list__name"><span>{name}</span></span><span class="account-list__role"><span>{role}</span></span></li>'
                    markup += f'"u":"./accountKeuze-accounts-account-{index}","c":"id{index}"'
                return httpx.Response(200, text=markup)
            received_state = "wrong-state" if wrong_state else state["oauth_state"]
            return httpx.Response(
                302,
                headers={"location": f"parro://oauth2?code=synthetic-code&state={received_state}"},
            )
        if "accountKeuze-accounts-account-" in request.url.path:
            state["chosen_name"] = choices[int(request.url.path.rsplit("-", 1)[-1])][0]
            return httpx.Response(
                200,
                headers={
                    "Ajax-Location": f"parro://oauth2?code=synthetic-code&state={state['oauth_state']}"
                },
            )
        if request.url.path == "/idp/oauth2/token":
            state["token_request"] = parse_qs(request.content.decode())
            return httpx.Response(
                200, json={**TOKENS, "expires_in": 3600, "id_token": "discard-this"}
            )
        if request.url.path == "/rest/v2/account/me":
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(404)

    server["handler"] = handler
    return state


async def test_login_sdk_http_no_cli_storage(hass, server, monkeypatch):
    sdk = await hass.async_add_executor_job(importlib.import_module, "parro.client")
    original_save = sdk._save_tokens
    original_write = Path.write_text
    original_exists = Path.exists

    def forbid_token_write(path, *args, **kwargs):
        assert path != sdk.TOKEN_PATH, "The integration must not write the CLI token file"
        return original_write(path, *args, **kwargs)

    def forbid_token_read(path):
        assert path != sdk.TOKEN_PATH, "The integration must not discover a CLI token file"
        return original_exists(path)

    monkeypatch.setattr(Path, "write_text", forbid_token_write)
    monkeypatch.setattr(Path, "exists", forbid_token_read)
    state = login_server(server)
    loop_thread = get_ident()
    result = await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    assert result.account_id == "81"
    assert result.title == "Parro"
    assert result.tokens["access_token"] == TOKENS["access_token"]
    assert result.tokens["expires_at"] > 0
    assert "id_token" not in result.tokens
    assert state["credentials"]["wachtwoord"] == ["synthetic-password"]
    assert state["token_request"]["code"] == ["synthetic-code"]
    assert "code_verifier" in state["token_request"]
    assert sdk._save_tokens is original_save
    assert all(thread != loop_thread for thread in server["threads"])


async def test_account_choice_exact_stable_selector_then_real_account_id(hass, server):
    choices = [("Guardian Alpha", "Ouder"), ("Guardian Alpha Beta", "Ouder")]
    state = login_server(server, choices=choices)
    with pytest.raises(ParroAccountSelectionRequired) as selection:
        await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    accounts = selection.value.accounts
    assert len(accounts) == 2
    assert all(set(account) == {"id", "name"} for account in accounts)
    selected = accounts[0]["id"]
    choices.reverse()
    result = await async_login(hass, "synthetic@example.invalid", "synthetic-password", selected)
    assert state["chosen_name"] == "Guardian Alpha"
    assert result.account_id == "81"
    assert result.account_id != selected


async def test_ambiguous_account_choices_fail_closed(hass, server):
    login_server(server, choices=[("Same name", "Ouder"), ("Same name", "Ouder")])
    with pytest.raises(ParroError, match="ambiguous"):
        await async_login(hass, "synthetic@example.invalid", "synthetic-password")


@pytest.mark.parametrize(
    "action",
    [
        "https://example.invalid/login",
        "http://inloggen.parnassys.net/login",
        "https://inloggen.parnassys.net:8443/login",
        "https://user:pass@inloggen.parnassys.net/login",
    ],
)
async def test_credentials_never_posted_to_other_origins(hass, server, action):
    login_server(server, action=action)
    with pytest.raises(ParroError, match="destination"):
        await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    assert len(server["requests"]) == 1


async def test_oauth_state_must_match(hass, server):
    login_server(server, wrong_state=True)
    with pytest.raises(ParroAuthError, match="state"):
        await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    assert not any(request.url.path.endswith("/token") for request in server["requests"])


async def test_login_redirects_bounded(hass, server):
    server["handler"] = lambda request: httpx.Response(302, headers={"location": "/endless"})
    with pytest.raises(ParroError, match="Too many"):
        await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    assert len(server["requests"]) == 40


@pytest.mark.parametrize(
    "status,expected",
    [
        (401, ParroAuthError),
        (403, ParroAuthError),
        (429, ParroConnectionError),
        (503, ParroConnectionError),
    ],
)
async def test_login_http_errors_are_classified_before_parsing(hass, server, status, expected):
    server["handler"] = lambda request: httpx.Response(status, text="private error body")
    with pytest.raises(expected) as error:
        await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    assert "private" not in str(error.value)


async def test_empty_credentials_never_prompt_or_read_environment(hass, server):
    with pytest.raises(ParroAuthError):
        await async_login(hass, "", "")
    assert not server["requests"]


def api_server(server, *, collections=None):
    collections = collections or {}

    def handler(request):
        path = request.url.path.removeprefix("/rest/v2")
        if path == "/account/me":
            return httpx.Response(200, json=ACCOUNT)
        if path in collections:
            value = collections[path]
            return value if isinstance(value, httpx.Response) else httpx.Response(200, json=value)
        return httpx.Response(200, json={"items": []})

    server["handler"] = handler
    return handler


async def test_summary_only_polls_counters_and_unknown_is_not_zero(hass, server):
    api_server(
        server,
        collections={
            "/child": {"items": [{"private": "child name"}, {}]},
            "/group": {"items": [{}]},
            "/identity/unreadcounts": {
                "items": [{"numberOfUnreadAnnouncements": 0, "numberOfUnreadChatRooms": 2}]
            },
        },
    )
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    assert await api.async_fetch_summary() == {
        "children_count": 2,
        "groups_count": 1,
        "unread_announcements": 0,
        "unread_chatrooms": 2,
    }
    assert {request.url.path for request in server["requests"]} == {
        "/rest/v2/account/me",
        "/rest/v2/child",
        "/rest/v2/group",
        "/rest/v2/identity/unreadcounts",
    }
    api_server(
        server,
        collections={"/identity/unreadcounts": {"items": [{"numberOfUnreadAnnouncements": 0}, {}]}},
    )
    summary = await api.async_fetch_summary()
    assert summary["unread_announcements"] is None
    assert summary["unread_chatrooms"] is None
    await api.async_close()


@pytest.mark.parametrize(
    "child_response",
    [
        httpx.Response(200, json={"items": [{}] * 100}),
        httpx.Response(200, json={"items": [{}, {}]}, headers={"Content-Range": "items 0-1/20"}),
    ],
)
async def test_partial_collection_is_not_an_exact_total(hass, server, child_response):
    api_server(server, collections={"/child": child_response})
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    assert (await api.async_fetch_summary())["children_count"] is None
    await api.async_close()


async def test_refresh_after_401_retries_once_and_persists_on_loop(hass, server):
    counts = {"refresh": 0}
    changes = []
    loop_thread = get_ident()

    def handler(request):
        if request.url.path.endswith("/token"):
            counts["refresh"] += 1
            assert parse_qs(request.content.decode())["refresh_token"] == ["synthetic-refresh"]
            return httpx.Response(
                200, json={"access_token": "new-access", "refresh_token": "rotated-refresh"}
            )
        if request.headers.get("Authorization") == "Bearer synthetic-access":
            return httpx.Response(401, json={"private": "secret server details"})
        if request.url.path.endswith("/account/me"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(200, json={"items": []})

    def changed(tokens):
        assert get_ident() == loop_thread
        changes.append(tokens)

    server["handler"] = handler
    api = ParroApi(hass, TOKENS, "81", changed)
    assert await api.async_get_announcements() == []
    assert counts["refresh"] == 1
    assert changes == [{"access_token": "new-access", "refresh_token": "rotated-refresh"}]
    assert await api.async_get_announcements() == []
    assert len(changes) == 1
    await api.async_close()


async def test_known_expiry_refreshes_before_request_and_preserves_refresh_token(hass, server):
    changes = []

    def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "new-access", "expires_in": 3600})
        assert request.headers.get("Authorization") == "Bearer new-access"
        if request.url.path.endswith("/account/me"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(200, json={"items": []})

    server["handler"] = handler
    api = ParroApi(hass, {**TOKENS, "expires_at": 1}, "81", changes.append)
    assert await api.async_get_chatrooms() == []
    assert changes[0]["refresh_token"] == "synthetic-refresh"
    assert server["requests"][0].url.path.endswith("/token")
    await api.async_close()


async def test_refresh_does_not_write_cli_tokens(hass, server, monkeypatch):
    original_write = Path.write_text

    def forbid_token_write(path, *args, **kwargs):
        assert not str(path).endswith("/parro/tokens.json")
        return original_write(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", forbid_token_write)

    def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "new-access"})
        if request.url.path.endswith("/account/me"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(200, json={"items": []})

    server["handler"] = handler
    api = ParroApi(hass, {**TOKENS, "expires_at": 1}, "81", lambda tokens: None)
    await api.async_get_chatrooms()
    await api.async_close()


async def test_missing_refresh_token_requires_reauth_without_disk_lookup(hass, server):
    api_server(server)
    api = ParroApi(
        hass, {"access_token": "synthetic-access", "expires_at": 1}, "81", lambda tokens: None
    )
    with pytest.raises(ParroAuthError):
        await api.async_get_chatrooms()
    assert not server["requests"]
    await api.async_close()


@pytest.mark.parametrize("refresh_status", [200, 400, 401])
async def test_rejected_refresh_or_second_401_requires_reauth(hass, server, refresh_status):
    def handler(request):
        if request.url.path.endswith("/token"):
            return httpx.Response(
                refresh_status, json={"access_token": "new-access", "error_description": "private"}
            )
        return httpx.Response(401)

    server["handler"] = handler
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    with pytest.raises(ParroAuthError) as error:
        await api.async_get_announcements()
    assert "private" not in str(error.value)
    assert (
        len([request for request in server["requests"] if request.url.path.endswith("/token")]) == 1
    )
    await api.async_close()


async def test_different_account_cannot_return_content(hass, server):
    api_server(server)
    api = ParroApi(hass, TOKENS, "another-account", lambda tokens: None)
    with pytest.raises(ParroAuthError, match="different account"):
        await api.async_get_announcements()
    assert len(server["requests"]) == 1
    await api.async_close()


@pytest.mark.parametrize(
    "failure,expected",
    [
        (httpx.ConnectError("private URL"), ParroConnectionError),
        (httpx.ReadTimeout("private URL"), ParroConnectionError),
        (httpx.Response(503, text="private server error"), ParroConnectionError),
        (httpx.Response(429, text="private server error"), ParroConnectionError),
        (httpx.Response(200, text="not JSON: private"), ParroError),
        (httpx.Response(200, json={"unexpected": "private"}), ParroError),
        (httpx.Response(200, json={"items": ["private"]}), ParroError),
    ],
)
async def test_network_and_malformed_responses_are_sanitized(hass, server, failure, expected):
    def handler(request):
        if request.url.path.endswith("/account/me"):
            return httpx.Response(200, json=ACCOUNT)
        if isinstance(failure, Exception):
            raise failure
        return failure

    server["handler"] = handler
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    with pytest.raises(expected) as error:
        await api.async_get_announcements()
    assert "private" not in str(error.value)
    await api.async_close()


async def test_actions_limit_requests_and_allow_only_normalized_fields(hass, server):
    attachment = {
        "name": "exercise.pdf",
        "attachmentType": "PDF",
        "secret": "omit",
        "entries": [{"type": "SOURCE", "size": 123, "url": "https://private.invalid/token=secret"}],
    }
    api_server(
        server,
        collections={
            "/event": {
                "items": [
                    {
                        "links": [{"rel": "self", "id": 9}, {"rel": "group", "id": 3}],
                        "title": "Synthetic school update",
                        "contents": "A" * 25000,
                        "owner": {"displayName": "Synthetic teacher", "email": "omit"},
                        "attachments": [attachment],
                        "private": "omit",
                    }
                ]
                * 100
            },
            "/chatroom": {
                "items": [
                    {
                        "links": [{"rel": "self", "id": 7}],
                        "title": "Synthetic room",
                        "unreadCount": 1,
                        "participants": ["omit"],
                    }
                ]
                * 100
            },
            "/chatroom/7/chatmessage": {
                "items": [
                    {
                        "links": [{"rel": "self", "id": 8}],
                        "text": "Synthetic message",
                        "createdAt": "2026-09-01T10:00:00Z",
                        "lastModifiedAt": "2026-09-02T11:00:00Z",
                        "identity": {"firstName": "Synthetic", "surname": "Teacher"},
                        "attachments": [attachment],
                    }
                ]
                * 100
            },
            "/calendar/sync": {"strings": ["https://calendar.invalid/private.ics"] * 100},
        },
    )
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    announcements = await api.async_get_announcements(2)
    assert len(announcements) == 2
    assert announcements[0]["id"] == "9"
    assert announcements[0]["group_id"] == "3"
    assert len(announcements[0]["contents"]) == 20000
    assert "secret" not in str(announcements)
    assert "url" not in str(announcements)
    assert len(await api.async_get_chatrooms(3)) == 3
    messages = await api.async_get_messages("7", 4)
    assert len(messages) == 4
    assert messages[0]["sender"] == "Synthetic Teacher"
    assert messages[0]["created_at"] == "2026-09-01T10:00:00Z"
    assert messages[0]["last_modified_at"] == "2026-09-02T11:00:00Z"
    assert "url" not in str(messages)
    assert len(await api.async_get_calendar_urls(5)) == 5
    ranges = {request.url.path: request.headers.get("Range") for request in server["requests"]}
    assert ranges["/rest/v2/event"] == "items=0-1"
    assert ranges["/rest/v2/chatroom"] == "items=0-2"
    assert ranges["/rest/v2/chatroom/7/chatmessage"] == "items=0-3"
    assert len(server["requests"]) == 5
    await api.async_close()


@pytest.mark.parametrize("limit", [0, -1, 51, 100000, True, "20", 1.5])
async def test_limits_rejected_before_network(hass, server, limit):
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    for operation in (
        api.async_get_announcements,
        api.async_get_chatrooms,
        api.async_get_calendar_urls,
    ):
        with pytest.raises(ParroError, match="Limit"):
            await operation(limit)
    with pytest.raises(ParroError, match="Limit"):
        await api.async_get_messages(1, limit)
    assert not server["requests"]
    await api.async_close()


@pytest.mark.parametrize(
    "room_id",
    [0, -1, True, "../account", "1/../../account", "https://example.invalid", "1?mark=true"],
)
async def test_room_path_injection_rejected_before_network(hass, server, room_id):
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    with pytest.raises(ParroError, match="Chatroom ID"):
        await api.async_get_messages(room_id)
    assert not server["requests"]
    await api.async_close()


async def test_closed_api_rejects_work_and_close_is_idempotent(hass, server):
    api_server(server)
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    await api.async_get_chatrooms()
    await api.async_close()
    await api.async_close()
    previous = len(server["requests"])
    with pytest.raises(ParroError, match="closed"):
        await api.async_get_chatrooms()
    assert len(server["requests"]) == previous


async def test_empty_range_and_default_maximum_limits(hass, server):
    api_server(server, collections={"/event": httpx.Response(416)})
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    assert await api.async_get_announcements() == []
    assert server["requests"][-1].headers["Range"] == "items=0-19"
    assert await api.async_get_announcements(50) == []
    assert server["requests"][-1].headers["Range"] == "items=0-49"
    await api.async_close()


async def test_cancelled_executor_future_does_not_spin(hass, monkeypatch):
    job = asyncio.get_running_loop().create_future()
    job.cancel()
    monkeypatch.setattr(hass, "async_add_executor_job", lambda *args: job)
    api = ParroApi(hass, TOKENS, "81", lambda tokens: None)
    with pytest.raises(asyncio.CancelledError):
        await api.async_get_chatrooms()


async def test_cancelled_refresh_saves_rotated_token_before_close(hass, server):
    refreshing = asyncio.Event()
    release_refresh = Event()
    loop = asyncio.get_running_loop()
    changes = []

    def handler(request):
        if request.url.path.endswith("/token"):
            loop.call_soon_threadsafe(refreshing.set)
            assert release_refresh.wait(timeout=5)
            return httpx.Response(
                200, json={"access_token": "new-access", "refresh_token": "rotated-refresh"}
            )
        if request.headers.get("Authorization") == "Bearer synthetic-access":
            return httpx.Response(401)
        if request.url.path.endswith("/account/me"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(200, json={"items": []})

    server["handler"] = handler
    api = ParroApi(hass, TOKENS, "81", changes.append)
    operation = asyncio.create_task(api.async_get_chatrooms())
    await asyncio.wait_for(refreshing.wait(), timeout=5)
    operation.cancel()
    close = asyncio.create_task(api.async_close())
    await asyncio.sleep(0)
    assert not close.done()
    release_refresh.set()
    with pytest.raises(asyncio.CancelledError):
        await operation
    await close
    assert changes == [{"access_token": "new-access", "refresh_token": "rotated-refresh"}]
