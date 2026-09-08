"""Synthetic chat cache, data isolation and lifecycle regression tests."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from custom_components.parro import feed as feed_module
from custom_components.parro.api import ParroAuthError, ParroConnectionError, ParroError
from custom_components.parro.chat_feed import ParroChatFeed
from custom_components.parro.feed import ParroFeed, ParroMediaError


@pytest.fixture
def source():
    room = {
        "id": "12",
        "title": "<b>Synthetic teacher</b>",
        "type": "PRIVATE",
        "unread_count": None,
        "sort_date": "2026-09-08T08:00:00Z",
    }
    return {
        "conversation": room,
        "conversations": [room],
        "items": [
            {
                "id": "91",
                "contents": "<p>Good morning</p><script>hidden()</script>",
                "sender": "<b>Teacher</b>",
                "created_at": "2026-09-08T08:00:00Z",
                "sort_date": "2026-09-08T08:00:00Z",
                "image_sources": [
                    {
                        "url": "https://cdn.example.invalid/photo?token=synthetic-secret",
                        "name": "<b>Photo</b>",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def api(source):
    instance = AsyncMock()
    instance._async_fetch_chat_source.return_value = source
    instance.async_get_chatrooms.return_value = source["conversations"]
    return instance


@pytest.fixture
def clock(monkeypatch):
    value = [1000.0]
    monkeypatch.setattr(feed_module, "_now", lambda: value[0])
    return value


async def test_messages_are_plain_text_with_opaque_photos_and_exact_contract(hass, api):
    feed = ParroChatFeed(hass, api)
    result = await feed.async_get_messages("12")
    assert set(result) == {"items", "conversation", "returned", "limit", "updated_at", "stale"}
    assert result["conversation"] == {"id": "12", "title": "Synthetic teacher"}
    item = result["items"][0]
    assert set(item) == {"id", "contents", "sender", "created_at", "sort_date", "images"}
    assert item["contents"] == "Good morning"
    assert item["sender"] == "Teacher"
    assert item["images"][0]["name"] == "Photo"
    assert len(item["images"][0]["id"]) == 32
    assert result["updated_at"].endswith("+00:00")
    assert result["returned"] == 1 and result["limit"] == 20 and result["stale"] is False
    assert "synthetic-secret" not in str(result)
    assert "http" not in str(result)
    assert "hidden()" not in str(result)
    await feed.async_close()


async def test_conversations_are_metadata_only_bounded_and_shared_across_limits(hass, api, source):
    api.async_get_chatrooms.return_value = [
        {**source["conversation"], "id": str(index)} for index in range(1, 101)
    ]
    feed = ParroChatFeed(hass, api)
    first, second = await asyncio.gather(
        feed.async_get_conversations(2), feed.async_get_conversations()
    )
    assert first["returned"] == 2 and second["returned"] == 50
    assert set(first["items"][0]) == {"id", "title", "type", "sort_date", "unread_count"}
    assert first["items"][0]["unread_count"] is None
    assert first["items"][0]["title"] == "Synthetic teacher"
    api.async_get_chatrooms.assert_awaited_once_with(limit=50)
    api._async_fetch_chat_source.assert_not_awaited()
    first["items"][0]["title"] = "Changed by consumer"
    assert (await feed.async_get_conversations())["items"][0]["title"] == "Synthetic teacher"
    await feed.async_close()


async def test_message_cache_serves_different_limits_and_seeds_room_list(hass, api, source, clock):
    source["items"] *= 30
    feed = ParroChatFeed(hass, api)
    first, second = await asyncio.gather(
        feed.async_get_messages("12", 2), feed.async_get_messages("12", 20)
    )
    assert first["returned"] == 2 and second["returned"] == 20
    api._async_fetch_chat_source.assert_awaited_once_with("12", limit=20)
    assert (await feed.async_get_conversations())["items"][0]["id"] == "12"
    api.async_get_chatrooms.assert_not_awaited()
    first["items"][0]["contents"] = "Changed by consumer"
    assert (await feed.async_get_messages("12"))["items"][0]["contents"] == "Good morning"
    clock[0] += feed_module.FEED_TTL
    await feed.async_get_messages("12")
    assert api._async_fetch_chat_source.await_count == 2
    await feed.async_close()


@pytest.mark.parametrize("kind", ["conversations", "messages"])
async def test_connection_only_stale_fallback_expires_after_one_hour(hass, api, clock, kind):
    feed = ParroChatFeed(hass, api)
    get = (
        feed.async_get_conversations
        if kind == "conversations"
        else lambda: feed.async_get_messages("12")
    )
    backend = api.async_get_chatrooms if kind == "conversations" else api._async_fetch_chat_source
    original = await get()
    clock[0] += feed_module.FEED_TTL + 1
    backend.side_effect = ParroConnectionError("Unavailable")
    stale = await get()
    assert stale["stale"] is True
    assert stale["updated_at"] == original["updated_at"]
    assert stale["items"] == original["items"]
    clock[0] += feed_module.STALE_TTL
    with pytest.raises(ParroConnectionError):
        await get()
    await feed.async_close()


@pytest.mark.parametrize("kind", ["conversations", "messages"])
async def test_auth_failure_clears_all_chat_data_and_prevents_later_stale_fallback(
    hass, api, clock, kind
):
    feed = ParroChatFeed(hass, api)
    original = await feed.async_get_messages("12")
    handle = original["items"][0]["images"][0]["id"]
    clock[0] += feed_module.FEED_TTL + 1
    get = (
        feed.async_get_conversations
        if kind == "conversations"
        else lambda: feed.async_get_messages("12")
    )
    backend = api.async_get_chatrooms if kind == "conversations" else api._async_fetch_chat_source
    backend.side_effect = ParroAuthError("Expired")
    with pytest.raises(ParroAuthError):
        await get()
    assert (
        feed._conversations is None and not feed._messages and not feed._refs and not feed._images
    )
    with pytest.raises(ParroMediaError):
        await feed.async_get_image(handle)
    backend.side_effect = ParroConnectionError("Unavailable")
    with pytest.raises(ParroConnectionError):
        await get()
    await feed.async_close()


async def test_lost_room_membership_revokes_cached_messages_and_photo_handles(hass, api, clock):
    feed = ParroChatFeed(hass, api)
    result = await feed.async_get_messages("12")
    handle = result["items"][0]["images"][0]["id"]
    clock[0] += feed_module.FEED_TTL + 1
    api.async_get_chatrooms.return_value = []
    assert (await feed.async_get_conversations())["returned"] == 0
    assert not feed._messages
    with pytest.raises(ParroMediaError):
        await feed.async_get_image(handle)
    api._async_fetch_chat_source.side_effect = ParroError(
        "The selected Parro conversation is unavailable"
    )
    with pytest.raises(ParroError, match="unavailable"):
        await feed.async_get_messages("12")
    await feed.async_close()


async def test_removed_room_error_never_returns_old_success(hass, api, clock):
    feed = ParroChatFeed(hass, api)
    result = await feed.async_get_messages("12")
    handle = result["items"][0]["images"][0]["id"]
    clock[0] += feed_module.FEED_TTL + 1
    api._async_fetch_chat_source.side_effect = ParroError("Unavailable conversation")
    with pytest.raises(ParroError):
        await feed.async_get_messages("12")
    assert not feed._messages
    with pytest.raises(ParroMediaError):
        await feed.async_get_image(handle)
    await feed.async_close()


async def test_message_cache_is_bounded_across_rooms(hass, api, source):
    rooms = [{**source["conversation"], "id": str(index)} for index in range(1, 10)]
    feed = ParroChatFeed(hass, api)
    for room in rooms:
        item = deepcopy(source["items"][0])
        item["image_sources"][0]["url"] += room["id"]
        api._async_fetch_chat_source.return_value = {
            "items": [item],
            "conversation": room,
            "conversations": rooms,
        }
        await feed.async_get_messages(room["id"])
    assert len(feed._messages) == feed_module.MAX_FEED_CACHES
    assert len(feed._refs) == feed_module.MAX_FEED_CACHES
    assert "1" not in feed._messages
    await feed.async_close()


async def test_removing_room_keeps_photo_shared_with_another_cached_room(hass, api, source, clock):
    rooms = [{**source["conversation"], "id": "12"}, {**source["conversation"], "id": "13"}]
    source["conversations"] = rooms
    feed = ParroChatFeed(hass, api)
    first = await feed.async_get_messages("12")
    source["conversation"] = rooms[1]
    second = await feed.async_get_messages("13")
    shared = first["items"][0]["images"][0]["id"]
    assert second["items"][0]["images"][0]["id"] == shared
    clock[0] += feed_module.FEED_TTL + 1
    api.async_get_chatrooms.return_value = [rooms[1]]
    await feed.async_get_conversations()
    assert "12" not in feed._messages
    assert shared in feed._refs
    api._async_fetch_chat_source.side_effect = ParroConnectionError("Unavailable")
    assert (await feed.async_get_messages("13"))["items"][0]["images"][0]["id"] == shared
    await feed.async_close()


async def test_successful_refresh_revokes_photo_removed_from_message(hass, api, source, clock):
    feed = ParroChatFeed(hass, api)
    original = await feed.async_get_messages("12")
    old_handle = original["items"][0]["images"][0]["id"]
    clock[0] += feed_module.FEED_TTL + 1
    source["items"] = []
    assert (await feed.async_get_messages("12"))["returned"] == 0
    with pytest.raises(ParroMediaError):
        await feed.async_get_image(old_handle)
    await feed.async_close()


async def test_announcement_and_other_account_handles_are_not_chat_handles(hass, api, source):
    api._async_fetch_feed_source.return_value = {"items": source["items"], "groups": []}
    announcement = ParroFeed(hass, api)
    chat = ParroChatFeed(hass, api)
    other_chat = ParroChatFeed(hass, api)
    announcement_id = (await announcement.async_get_feed())["items"][0]["images"][0]["id"]
    chat_id = (await chat.async_get_messages("12"))["items"][0]["images"][0]["id"]
    other_id = (await other_chat.async_get_messages("12"))["items"][0]["images"][0]["id"]
    assert len({announcement_id, chat_id, other_id}) == 3
    for target, wrong_id in [
        (announcement, chat_id),
        (chat, announcement_id),
        (chat, other_id),
        (other_chat, chat_id),
    ]:
        with pytest.raises(ParroMediaError):
            await target.async_get_image(wrong_id)
    await chat.async_close()
    assert announcement._refs and other_chat._refs
    await announcement.async_close()
    await other_chat.async_close()


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.example.invalid/photo",
        "https://127.0.0.1/secret",
        "https://[::1]/secret",
        "https://user:secret@cdn.example.invalid/photo",
    ],
)
async def test_unsafe_chat_photo_does_not_hide_the_message(hass, api, source, url):
    source["items"][0]["image_sources"] = [{"url": url}]
    feed = ParroChatFeed(hass, api)
    result = await feed.async_get_messages("12")
    assert result["items"][0]["contents"] == "Good morning"
    assert result["items"][0]["images"] == []
    assert url not in str(result)
    await feed.async_close()


@pytest.mark.parametrize("kind", ["conversations", "messages"])
async def test_close_during_failed_request_does_not_return_stale_content(hass, api, clock, kind):
    feed = ParroChatFeed(hass, api)
    get = (
        feed.async_get_conversations
        if kind == "conversations"
        else lambda: feed.async_get_messages("12")
    )
    backend = api.async_get_chatrooms if kind == "conversations" else api._async_fetch_chat_source
    await get()
    clock[0] += feed_module.FEED_TTL + 1
    started, release = asyncio.Event(), asyncio.Event()

    async def failing(*args, **kwargs):
        started.set()
        await release.wait()
        raise ParroConnectionError("Unavailable")

    backend.side_effect = failing
    request = asyncio.create_task(get())
    await started.wait()
    close = asyncio.create_task(feed.async_close())
    await asyncio.sleep(0)
    release.set()
    with pytest.raises(ParroError, match="closed"):
        await request
    await close
    assert feed._conversations is None and not feed._messages and not feed._refs
    api.async_close.assert_not_awaited()


@pytest.mark.parametrize("limit", [True, 0, -1, 21, None, "20"])
async def test_message_limits_rejected_without_backend(hass, api, limit):
    feed = ParroChatFeed(hass, api)
    with pytest.raises(ParroError):
        await feed.async_get_messages("12", limit)
    api._async_fetch_chat_source.assert_not_awaited()
    await feed.async_close()


@pytest.mark.parametrize("limit", [True, 0, -1, 51, None, "50"])
async def test_conversation_limits_rejected_without_backend(hass, api, limit):
    feed = ParroChatFeed(hass, api)
    with pytest.raises(ParroError):
        await feed.async_get_conversations(limit)
    api.async_get_chatrooms.assert_not_awaited()
    await feed.async_close()


@pytest.mark.parametrize("room_id", [True, 12, "0", "../12", "https://private.invalid", "1" * 21])
async def test_bad_room_ids_rejected_without_backend(hass, api, room_id):
    feed = ParroChatFeed(hass, api)
    with pytest.raises(ParroError):
        await feed.async_get_messages(room_id)
    api._async_fetch_chat_source.assert_not_awaited()
    await feed.async_close()
