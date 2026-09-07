"""Synthetic feed caching, group routing and data minimization tests."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from custom_components.parro import feed as feed_module
from custom_components.parro.api import ParroAuthError, ParroConnectionError, ParroError
from custom_components.parro.feed import ParroFeed, ParroMediaError


@pytest.fixture
def source():
    return {
        "groups": [{"id": "12", "name": "Synthetic group"}],
        "items": [
            {
                "id": "91",
                "title": "<b>School update</b>",
                "contents": '<p>Hello &amp; welcome</p><script>private_script()</script><img src="https://cdn.example.invalid/photo?secret=synthetic-token"><p>Next week</p>',
                "created_at": "2026-09-08T08:00:00Z",
                "sort_date": "2026-09-08T08:00:00Z",
                "group_id": "12",
                "sender": "Synthetic teacher",
                "image_sources": [
                    {
                        "url": "https://cdn.example.invalid/photo?secret=synthetic-token",
                        "name": "School photo",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def api(source):
    instance = AsyncMock()
    instance._async_fetch_feed_source.return_value = source
    return instance


@pytest.fixture
def clock(monkeypatch):
    value = [1000.0]
    monkeypatch.setattr(feed_module, "_now", lambda: value[0])
    return value


async def test_feed_only_returns_plain_text_and_opaque_media_handles(hass, api, source):
    feed = ParroFeed(hass, api)
    result = await feed.async_get_feed()
    assert set(result) == {"items", "groups", "returned", "limit", "updated_at", "stale"}
    item = result["items"][0]
    assert item["title"] == "School update"
    assert item["contents"] == "Hello & welcome\n\nNext week"
    assert item["group_name"] == "Synthetic group"
    assert item["images"][0]["name"] == "School photo"
    assert len(item["images"][0]["id"]) == 32
    assert result["returned"] == 1
    assert result["limit"] == 5
    assert result["stale"] is False
    assert result["updated_at"].endswith("+00:00")
    assert "synthetic-token" not in str(result)
    assert "https://" not in str(result)
    assert "private_script" not in str(result)
    assert "image_sources" not in str(result)
    assert "synthetic-token" not in repr(next(iter(feed._refs.values())))
    assert source["items"][0]["title"] == "<b>School update</b>"
    await feed.async_close()


async def test_feed_cache_is_shared_across_limits_and_concurrent_cards(hass, api, source, clock):
    source["items"] *= 10
    feed = ParroFeed(hass, api)
    first, second = await asyncio.gather(feed.async_get_feed(2), feed.async_get_feed(7))
    assert first["returned"] == 2
    assert second["returned"] == 7
    api._async_fetch_feed_source.assert_awaited_once_with(limit=50, group_id=None)
    first["items"][0]["title"] = "Consumer mutation"
    assert (await feed.async_get_feed())["items"][0]["title"] == "School update"
    clock[0] += feed_module.FEED_TTL + 1
    await feed.async_get_feed()
    assert api._async_fetch_feed_source.await_count == 2
    await feed.async_close()


async def test_feed_group_routing_and_cache_bound(hass, api, clock):
    feed = ParroFeed(hass, api)
    for group_id in range(1, feed_module.MAX_FEED_CACHES + 3):
        await feed.async_get_feed(group_id=str(group_id))
    assert len(feed._feeds) == feed_module.MAX_FEED_CACHES
    api._async_fetch_feed_source.assert_awaited_with(limit=50, group_id=str(group_id))
    assert "1" not in feed._feeds
    await feed.async_close()


async def test_missing_or_unsafe_photos_keep_the_school_text(hass, api, source):
    source["items"][0]["image_sources"] = [
        {"url": "http://cdn.example.invalid/photo", "name": "Unsafe"},
        {"url": "https://127.0.0.1/photo", "name": "Local"},
        {"url": None, "name": "Missing"},
    ]
    feed = ParroFeed(hass, api)
    result = await feed.async_get_feed()
    assert result["items"][0]["images"] == []
    assert result["items"][0]["title"] == "School update"
    await feed.async_close()


async def test_duplicate_photo_urls_share_one_handle(hass, api, source):
    source["items"][0]["image_sources"] *= 3
    feed = ParroFeed(hass, api)
    result = await feed.async_get_feed()
    assert len(result["items"][0]["images"]) == 1
    assert len(feed._refs) == 1
    await feed.async_close()


async def test_transient_errors_return_explicit_stale_data_not_empty_success(hass, api, clock):
    feed = ParroFeed(hass, api)
    original = await feed.async_get_feed()
    clock[0] += feed_module.FEED_TTL + 1
    api._async_fetch_feed_source.side_effect = ParroConnectionError("Unable to reach Parro")
    stale = await feed.async_get_feed()
    assert stale["stale"] is True
    assert stale["updated_at"] == original["updated_at"]
    assert stale["items"] == original["items"]
    clock[0] += feed_module.STALE_TTL + 1
    with pytest.raises(ParroConnectionError):
        await feed.async_get_feed()
    await feed.async_close()


@pytest.mark.parametrize("error", [ParroAuthError("Expired"), ParroError("Unavailable group")])
async def test_auth_and_invalid_group_errors_are_not_hidden_by_stale_cache(hass, api, clock, error):
    feed = ParroFeed(hass, api)
    await feed.async_get_feed()
    clock[0] += feed_module.FEED_TTL + 1
    api._async_fetch_feed_source.side_effect = error
    with pytest.raises(type(error)):
        await feed.async_get_feed()
    if isinstance(error, ParroAuthError):
        assert not feed._feeds and not feed._refs and not feed._images
        api._async_fetch_feed_source.side_effect = ParroConnectionError("Unavailable")
        with pytest.raises(ParroConnectionError):
            await feed.async_get_feed()
    await feed.async_close()


async def test_first_connection_failure_is_an_error(hass, api):
    feed = ParroFeed(hass, api)
    api._async_fetch_feed_source.side_effect = ParroConnectionError("Unable to reach Parro")
    with pytest.raises(ParroConnectionError):
        await feed.async_get_feed()
    await feed.async_close()


async def test_media_reference_bounds_expiry_and_entry_isolation(hass, api, clock, monkeypatch):
    monkeypatch.setattr(feed_module, "MAX_MEDIA_REFS", 2)
    feed = ParroFeed(hass, api)
    first = feed._media_id("https://cdn.example.invalid/one")
    second = feed._media_id("https://cdn.example.invalid/two")
    third = feed._media_id("https://cdn.example.invalid/three")
    assert first not in feed._refs
    assert len(feed._refs) == len(feed._by_url) == 2
    other = ParroFeed(hass, api)
    with pytest.raises(ParroMediaError):
        await other.async_get_image(second)
    clock[0] += feed_module.MEDIA_REF_TTL + 1
    with pytest.raises(ParroMediaError):
        await feed.async_get_image(third)
    assert not feed._refs and not feed._by_url
    await feed.async_close()
    await other.async_close()


@pytest.mark.parametrize("limit", [0, 21, 51, True, "5", 1.5])
async def test_feed_rejects_bad_limits_before_api(hass, api, limit):
    feed = ParroFeed(hass, api)
    with pytest.raises(ParroError):
        await feed.async_get_feed(limit=limit)
    api._async_fetch_feed_source.assert_not_awaited()
    await feed.async_close()


@pytest.mark.parametrize("group_id", ["../12", "https://private.invalid", "0", "-1", True, 12])
async def test_feed_rejects_bad_group_ids_before_api(hass, api, group_id):
    feed = ParroFeed(hass, api)
    with pytest.raises(ParroError):
        await feed.async_get_feed(group_id=group_id)
    api._async_fetch_feed_source.assert_not_awaited()
    await feed.async_close()


async def test_close_clears_all_content_and_refuses_work(hass, api):
    feed = ParroFeed(hass, api)
    result = await feed.async_get_feed()
    media_id = result["items"][0]["images"][0]["id"]
    await feed.async_close()
    await feed.async_close()
    assert not feed._feeds and not feed._refs and not feed._by_url and not feed._images
    with pytest.raises(ParroError):
        await feed.async_get_feed()
    with pytest.raises(ParroError):
        await feed.async_get_image(media_id)
    api.async_close.assert_not_awaited()


async def test_photo_source_url_removed_if_it_occurs_as_plain_text(hass, api, source):
    original = deepcopy(source)
    source["items"][0]["contents"] += original["items"][0]["image_sources"][0]["url"]
    feed = ParroFeed(hass, api)
    assert "synthetic-token" not in str(await feed.async_get_feed())
    await feed.async_close()
