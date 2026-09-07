"""Private feed adapter contract against actual SDK HTTP request shapes."""

import httpx
import pytest

from custom_components.parro.api import ParroApi, ParroError
from custom_components.parro.feed import ParroFeed


@pytest.fixture
def feed_api_server(monkeypatch):
    original_init = httpx.Client.__init__
    state = {
        "requests": [],
        "groups": [{"links": [{"rel": "self", "id": 12}], "name": "Synthetic group"}],
        "items": [],
    }

    def handler(request):
        state["requests"].append(request)
        if request.url.path.endswith("/account/me"):
            return httpx.Response(200, json={"links": [{"rel": "self", "id": 81}]})
        if request.url.path.endswith("/group"):
            return httpx.Response(200, json={"items": state["groups"]})
        if request.url.path.endswith("/event"):
            return httpx.Response(200, json={"items": state["items"]})
        return httpx.Response(404)

    def client_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", client_init)
    return state


def photo(index=0, kind="image", entry_type="SOURCE"):
    return {
        "attachmentType": kind,
        "name": f"Synthetic photo {index}",
        "entries": [
            {
                "type": entry_type,
                "url": f"https://cdn.example.invalid/photo{index}?token=synthetic-secret",
            }
        ],
    }


async def test_private_source_fetches_account_groups_and_only_bounded_photo_sources(
    hass, feed_api_server
):
    feed_api_server["items"] = [
        {
            "links": [{"rel": "self", "id": 91}, {"rel": "group", "id": 12}],
            "title": "Synthetic update",
            "contents": "<p>Text</p>",
            "attachments": [photo(index) for index in range(10)],
            "unrelated_private_field": "must not survive",
        }
    ] * 100
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    source = await api._async_fetch_feed_source(limit=5, group_id="12")
    assert source["groups"] == [{"id": "12", "name": "Synthetic group"}]
    assert len(source["items"]) == 5
    item = source["items"][0]
    assert item["group_id"] == "12"
    assert len(item["image_sources"]) == 3
    assert "synthetic-secret" in item["image_sources"][0]["url"]
    assert "unrelated_private_field" not in item
    request = feed_api_server["requests"][-1]
    assert request.url.params["group"] == "12"
    assert request.url.params["dtype"] == "event.RAnnouncementEvent"
    assert request.headers["Range"] == "items=0-4"
    public_action = await api.async_get_announcements(limit=1)
    assert "synthetic-secret" not in str(public_action)
    assert "image_sources" not in str(public_action)
    await api.async_close()


async def test_selected_group_must_belong_to_authenticated_account(hass, feed_api_server):
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    with pytest.raises(ParroError, match="unavailable"):
        await api._async_fetch_feed_source(group_id="99")
    assert not any(request.url.path.endswith("/event") for request in feed_api_server["requests"])
    await api.async_close()


async def test_only_demonstrated_image_source_shape_is_included(hass, feed_api_server):
    feed_api_server["items"] = [
        {
            "attachments": [
                photo(kind="PDF"),
                photo(entry_type="PREVIEW"),
                None,
                {"attachmentType": "image", "entries": [None]},
                photo(9, kind="IMAGE"),
            ],
        }
    ]
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    source = await api._async_fetch_feed_source(group_id="12")
    assert len(source["items"][0]["image_sources"]) == 1
    assert source["items"][0]["image_sources"][0]["name"] == "Synthetic photo 9"
    assert source["items"][0]["group_id"] == "12"
    await api.async_close()


async def test_real_sdk_http_to_private_feed_has_opaque_images_and_safe_text(hass, feed_api_server):
    """Exercise SDK, adapter and feed together without mocking any layer between them."""
    feed_api_server["items"] = [
        {
            "links": [{"rel": "self", "id": 91}, {"rel": "group", "id": 12}],
            "title": "<b>Synthetic update</b>",
            "contents": '<p>School news</p><img src="https://cdn.example.invalid/hidden">',
            "owner": {"displayName": "Synthetic teacher"},
            "attachments": [photo()],
        }
    ]
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    feed = ParroFeed(hass, api)
    result = await feed.async_get_feed(group_id="12")
    assert result["returned"] == 1
    assert result["items"][0]["title"] == "Synthetic update"
    assert result["items"][0]["contents"] == "School news"
    assert result["items"][0]["group_name"] == "Synthetic group"
    assert result["items"][0]["sender"] == "Synthetic teacher"
    assert len(result["items"][0]["images"][0]["id"]) == 32
    assert "synthetic-secret" not in str(result)
    assert "https://" not in str(result)
    assert len(feed_api_server["requests"]) == 3
    assert feed_api_server["requests"][-1].headers["Range"] == "items=0-49"
    assert await feed.async_get_feed(group_id="12") == result
    assert len(feed_api_server["requests"]) == 3
    await feed.async_close()
    await api.async_close()
    assert not feed._refs and not feed._feeds


@pytest.mark.parametrize("group_id", ["../12", "0", True, 12, "https://private.invalid"])
async def test_malformed_group_ids_do_not_reach_server(hass, feed_api_server, group_id):
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    with pytest.raises(ParroError):
        await api._async_fetch_feed_source(group_id=group_id)
    assert not feed_api_server["requests"]
    await api.async_close()
