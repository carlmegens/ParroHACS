"""Exercise account permissions through real HA WebSocket and HTTP routes."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.parro.api import ParroAuthError, ParroConnectionError, ParroError

FEED = {
    "items": [{"id": "11", "contents": "Synthetic private school text", "images": []}],
    "groups": [{"id": "10", "name": "Synthetic group"}],
    "returned": 1,
    "limit": 5,
    "updated_at": "2026-01-01T12:00:00+00:00",
    "stale": False,
}


@pytest.fixture
async def account(hass, config_entry, mock_api):
    config_entry.add_to_hass(hass)
    with patch("custom_components.parro.ParroApi", return_value=mock_api):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    feed = config_entry.runtime_data.feed
    with (
        patch.object(feed, "async_get_feed", AsyncMock(return_value=FEED)),
        patch.object(
            feed, "async_get_image", AsyncMock(return_value=(b"synthetic-jpeg", "image/jpeg"))
        ),
    ):
        yield config_entry


async def ws_request(client, message):
    await client.send_json_auto_id(message)
    return await client.receive_json()


@pytest.mark.parametrize("allowed", [False, True])
async def test_viewer_access_is_per_account(
    hass, account, hass_read_only_user, hass_read_only_access_token, hass_ws_client, allowed
):
    other = MockConfigEntry(domain="parro", title="Hidden account", unique_id="other", data={})
    other.add_to_hass(hass)
    if allowed:
        hass.config_entries.async_update_entry(
            account, options={"dashboard_viewers": [hass_read_only_user.id]}
        )
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    response = await ws_request(client, {"type": "parro/accounts"})
    expected = [{"config_entry_id": account.entry_id, "title": account.title}] if allowed else []
    assert response["result"] == {"accounts": expected}
    response = await ws_request(client, {"type": "parro/feed", "config_entry_id": account.entry_id})
    if allowed:
        assert response["result"] == FEED
        account.runtime_data.feed.async_get_feed.assert_awaited_once_with(limit=5, group_id=None)
    else:
        assert response["error"]["code"] == "unauthorized"
        account.runtime_data.feed.async_get_feed.assert_not_awaited()
    response = await ws_request(client, {"type": "parro/feed", "config_entry_id": other.entry_id})
    assert response["error"]["code"] == "unauthorized"


async def test_administrator_has_default_access(hass, account, hass_ws_client):
    client = await hass_ws_client(hass)
    response = await ws_request(client, {"type": "parro/accounts"})
    assert response["result"]["accounts"][0]["config_entry_id"] == account.entry_id
    response = await ws_request(
        client,
        {"type": "parro/feed", "config_entry_id": account.entry_id, "limit": 20, "group_id": "10"},
    )
    assert response["success"]
    account.runtime_data.feed.async_get_feed.assert_awaited_once_with(limit=20, group_id="10")


@pytest.mark.parametrize(
    "fields",
    [
        {"limit": 0},
        {"limit": 21},
        {"limit": True},
        {"limit": "5"},
        {"group_id": "0"},
        {"group_id": "../10"},
        {"group_id": "1\n"},
        {"source_url": "https://example.invalid"},
    ],
)
async def test_ws_rejects_invalid_requests_before_fetch(hass, account, hass_ws_client, fields):
    client = await hass_ws_client(hass)
    response = await ws_request(
        client, {"type": "parro/feed", "config_entry_id": account.entry_id, **fields}
    )
    assert response["error"]["code"] == "invalid_format"
    account.runtime_data.feed.async_get_feed.assert_not_awaited()


@pytest.mark.parametrize("suffix", ["feed", "image/" + "x" * 32])
@pytest.mark.parametrize("allowed", [False, True])
async def test_http_requires_account_access_and_disables_caching(
    hass, account, hass_client, hass_read_only_user, hass_read_only_access_token, suffix, allowed
):
    if allowed:
        hass.config_entries.async_update_entry(
            account, options={"dashboard_viewers": [hass_read_only_user.id]}
        )
    client = await hass_client(hass_read_only_access_token)
    response = await client.get(f"/api/parro/{account.entry_id}/{suffix}")
    assert response.status == (200 if allowed else 403)
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    if allowed:
        if suffix == "feed":
            assert await response.json() == FEED
        else:
            assert response.content_type == "image/jpeg"
            assert await response.read() == b"synthetic-jpeg"
    else:
        account.runtime_data.feed.async_get_feed.assert_not_awaited()
        account.runtime_data.feed.async_get_image.assert_not_awaited()


@pytest.mark.parametrize("suffix", ["feed", "image/" + "x" * 32])
async def test_http_rejects_unauthenticated_read(account, hass_client_no_auth, suffix):
    client = await hass_client_no_auth()
    response = await client.get(f"/api/parro/{account.entry_id}/{suffix}")
    assert response.status == 401
    account.runtime_data.feed.async_get_feed.assert_not_awaited()
    account.runtime_data.feed.async_get_image.assert_not_awaited()


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=21",
        "limit=1&limit=2",
        "group_id=1&group_id=2",
        "group_id=0",
        "group_id=../1",
        "limit=abc",
        "url=https://example.invalid",
    ],
)
async def test_http_invalid_input_never_reaches_api(account, hass_client, query):
    client = await hass_client()
    response = await client.get(f"/api/parro/{account.entry_id}/feed?{query}")
    assert response.status == 400
    if query != "group_id=../1":  # HA's security middleware rejects traversal first.
        assert await response.json() == {"code": "invalid_request"}
    account.runtime_data.feed.async_get_feed.assert_not_awaited()


@pytest.mark.parametrize("suffix", ["feed", "image/" + "x" * 32])
@pytest.mark.parametrize("change", ["revoke", "disable_user", "unload", "reload"])
async def test_access_change_during_read_withholds_result(
    hass, account, hass_client, hass_read_only_user, hass_read_only_access_token, suffix, change
):
    hass.config_entries.async_update_entry(
        account, options={"dashboard_viewers": [hass_read_only_user.id]}
    )
    coordinator = account.runtime_data

    async def changing_read(*args, **kwargs):
        if change == "revoke":
            hass.config_entries.async_update_entry(account, options={})
        elif change == "disable_user":
            await hass.auth.async_update_user(hass_read_only_user, is_active=False)
        elif change == "unload":
            account.mock_state(hass, ConfigEntryState.NOT_LOADED)
        else:
            account.runtime_data = object()
        return FEED if suffix == "feed" else (b"private-image", "image/jpeg")

    method = (
        coordinator.feed.async_get_feed if suffix == "feed" else coordinator.feed.async_get_image
    )
    method.side_effect = changing_read
    client = await hass_client(hass_read_only_access_token)
    try:
        response = await client.get(f"/api/parro/{account.entry_id}/{suffix}")
        assert response.status in (403, 503)
        assert "private" not in await response.text()
    finally:
        account.runtime_data = coordinator


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ParroConnectionError("private URL"), "cannot_connect"),
        (ParroError("private payload"), "unsupported_response"),
        (RuntimeError("private secret"), "unsupported_response"),
        (ParroAuthError("private token"), "authentication_expired"),
    ],
)
async def test_feed_failure_is_safe_and_auth_requests_reauth(
    hass, account, hass_ws_client, caplog, error, code
):
    account.runtime_data.feed.async_get_feed.side_effect = error
    client = await hass_ws_client(hass)
    response = await ws_request(client, {"type": "parro/feed", "config_entry_id": account.entry_id})
    assert response["error"]["code"] == code
    assert "private" not in str(response)
    assert "private" not in caplog.text
    if isinstance(error, ParroAuthError):
        await hass.async_block_till_done()
        assert any(
            flow["context"]["source"] == "reauth"
            for flow in hass.config_entries.flow.async_progress()
        )


async def test_dashboard_viewer_still_cannot_read_private_chats(hass, account, hass_read_only_user):
    hass.config_entries.async_update_entry(
        account, options={"dashboard_viewers": [hass_read_only_user.id]}
    )
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "parro",
            "get_chatrooms",
            {"config_entry_id": account.entry_id},
            blocking=True,
            return_response=True,
            context=Context(user_id=hass_read_only_user.id),
        )


async def test_viewer_revoked_on_existing_websocket(
    hass, account, hass_read_only_user, hass_read_only_access_token, hass_ws_client
):
    hass.config_entries.async_update_entry(
        account, options={"dashboard_viewers": [hass_read_only_user.id]}
    )
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    assert (await ws_request(client, {"type": "parro/feed", "config_entry_id": account.entry_id}))[
        "success"
    ]
    hass.config_entries.async_update_entry(account, options={})
    response = await ws_request(client, {"type": "parro/feed", "config_entry_id": account.entry_id})
    assert response["error"]["code"] == "unauthorized"
    assert account.runtime_data.feed.async_get_feed.await_count == 1


@pytest.fixture
async def chat_account(account):
    feed = account.runtime_data.chat_feed
    with (
        patch.object(
            feed,
            "async_get_conversations",
            AsyncMock(return_value={"items": [{"id": "10", "title": "Synthetic conversation"}]}),
        ),
        patch.object(feed, "async_get_messages", AsyncMock(return_value=FEED)),
        patch.object(
            feed, "async_get_image", AsyncMock(return_value=(b"synthetic-chat-jpeg", "image/jpeg"))
        ),
    ):
        yield account


@pytest.mark.parametrize("permission", [None, "dashboard_viewers", "chat_viewers"])
async def test_chat_access_does_not_inherit_announcement_permission(
    hass, chat_account, hass_read_only_user, hass_read_only_access_token, hass_ws_client, permission
):
    if permission:
        hass.config_entries.async_update_entry(
            chat_account, options={permission: [hass_read_only_user.id]}
        )
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    accounts = await ws_request(client, {"type": "parro/accounts", "source": "messages"})
    assert bool(accounts["result"]["accounts"]) == (permission == "chat_viewers")
    announcements = await ws_request(client, {"type": "parro/accounts"})
    assert bool(announcements["result"]["accounts"]) == (permission == "dashboard_viewers")
    for kind, fields in [("conversations", {}), ("messages", {"chatroom_id": "10"})]:
        response = await ws_request(
            client, {"type": "parro/" + kind, "config_entry_id": chat_account.entry_id, **fields}
        )
        assert response["success"] == (permission == "chat_viewers")
        if permission != "chat_viewers":
            assert response["error"]["code"] == "unauthorized"
    if permission != "chat_viewers":
        chat_account.runtime_data.chat_feed.async_get_messages.assert_not_awaited()
        chat_account.runtime_data.chat_feed.async_get_conversations.assert_not_awaited()


@pytest.mark.parametrize(
    "suffix", ["conversations", "messages?chatroom_id=10", "chat_image/" + "x" * 32]
)
@pytest.mark.parametrize("permission", ["dashboard_viewers", "chat_viewers"])
async def test_chat_http_uses_separate_acl_and_image_store(
    hass,
    chat_account,
    hass_client,
    hass_read_only_user,
    hass_read_only_access_token,
    suffix,
    permission,
):
    hass.config_entries.async_update_entry(
        chat_account, options={permission: [hass_read_only_user.id]}
    )
    client = await hass_client(hass_read_only_access_token)
    response = await client.get(f"/api/parro/{chat_account.entry_id}/{suffix}")
    assert response.status == (200 if permission == "chat_viewers" else 403)
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    if permission == "chat_viewers" and suffix.startswith("chat_image"):
        assert await response.read() == b"synthetic-chat-jpeg"
    chat_account.runtime_data.feed.async_get_image.assert_not_awaited()
    chat_account.runtime_data.feed.async_get_feed.assert_not_awaited()


@pytest.mark.parametrize(
    "suffix", ["conversations", "messages?chatroom_id=10", "chat_image/" + "x" * 32]
)
@pytest.mark.parametrize("change", ["revoke", "disable_user", "unload", "reload"])
async def test_chat_access_change_while_reading_withholds_content(
    hass,
    chat_account,
    hass_client,
    hass_read_only_user,
    hass_read_only_access_token,
    suffix,
    change,
):
    hass.config_entries.async_update_entry(
        chat_account, options={"chat_viewers": [hass_read_only_user.id]}
    )
    coordinator = chat_account.runtime_data

    async def changing_read(*args, **kwargs):
        if change == "revoke":
            hass.config_entries.async_update_entry(chat_account, options={})
        elif change == "disable_user":
            await hass.auth.async_update_user(hass_read_only_user, is_active=False)
        elif change == "unload":
            chat_account.mock_state(hass, ConfigEntryState.NOT_LOADED)
        else:
            chat_account.runtime_data = object()
        return (b"private-photo", "image/jpeg") if suffix.startswith("chat_image") else FEED

    method = (
        "async_get_image"
        if suffix.startswith("chat_image")
        else "async_get_" + suffix.split("?")[0]
    )
    getattr(coordinator.chat_feed, method).side_effect = changing_read
    client = await hass_client(hass_read_only_access_token)
    try:
        response = await client.get(f"/api/parro/{chat_account.entry_id}/{suffix}")
        assert response.status in (403, 503)
        assert "private" not in await response.text()
    finally:
        chat_account.runtime_data = coordinator


@pytest.mark.parametrize(
    "suffix", ["conversations", "messages?chatroom_id=10", "chat_image/" + "x" * 32]
)
async def test_chat_http_requires_login(chat_account, hass_client_no_auth, suffix):
    response = await (await hass_client_no_auth()).get(
        f"/api/parro/{chat_account.entry_id}/{suffix}"
    )
    assert response.status == 401


@pytest.mark.parametrize(
    "suffix",
    [
        "conversations?limit=51",
        "conversations?chatroom_id=10",
        "messages",
        "messages?chatroom_id=0",
        "messages?chatroom_id=1&chatroom_id=2",
        "messages?chatroom_id=1&limit=21",
        "messages?chatroom_id=1&url=https://example.invalid",
    ],
)
async def test_chat_http_rejects_invalid_input(chat_account, hass_client, suffix):
    response = await (await hass_client()).get(f"/api/parro/{chat_account.entry_id}/{suffix}")
    assert response.status == 400
    chat_account.runtime_data.chat_feed.async_get_messages.assert_not_awaited()
    chat_account.runtime_data.chat_feed.async_get_conversations.assert_not_awaited()


async def test_chat_admin_default_and_service_privilege_remains_separate(
    hass, chat_account, hass_ws_client, hass_read_only_user
):
    client = await hass_ws_client(hass)
    response = await ws_request(
        client,
        {"type": "parro/messages", "config_entry_id": chat_account.entry_id, "chatroom_id": "10"},
    )
    assert response["result"] == FEED
    chat_account.runtime_data.chat_feed.async_get_messages.assert_awaited_once_with(
        limit=20, chatroom_id="10"
    )
    hass.config_entries.async_update_entry(
        chat_account, options={"chat_viewers": [hass_read_only_user.id]}
    )
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "parro",
            "get_messages",
            {"config_entry_id": chat_account.entry_id, "chatroom_id": "10"},
            blocking=True,
            return_response=True,
            context=Context(user_id=hass_read_only_user.id),
        )


@pytest.mark.parametrize("origin", ["feed", "messages", "summary"])
async def test_auth_expiry_blocks_and_closes_both_content_sources(
    hass, chat_account, hass_client, hass_ws_client, mock_api, origin
):
    coordinator = chat_account.runtime_data
    client = await hass_ws_client(hass)
    if origin == "summary":
        mock_api.async_fetch_summary.side_effect = ParroAuthError("private-token")
        await coordinator.async_refresh()
    else:
        store = coordinator.feed if origin == "feed" else coordinator.chat_feed
        getattr(store, "async_get_" + origin).side_effect = ParroAuthError("private-token")
        response = await ws_request(
            client,
            {
                "type": "parro/" + origin,
                "config_entry_id": chat_account.entry_id,
                **({"chatroom_id": "10"} if origin == "messages" else {}),
            },
        )
        assert response["error"]["code"] == "authentication_expired"
    assert coordinator.content_auth_failed
    assert coordinator.feed._closed and coordinator.chat_feed._closed
    http = await hass_client()
    for suffix in [
        "feed",
        "messages?chatroom_id=10",
        "image/" + "x" * 32,
        "chat_image/" + "x" * 32,
    ]:
        response = await http.get(f"/api/parro/{chat_account.entry_id}/{suffix}")
        assert response.status == 503
        assert await response.json() == {"code": "authentication_expired"}
