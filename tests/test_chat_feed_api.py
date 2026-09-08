"""Actual SDK HTTP shapes through private chat feed, using synthetic data only."""

from io import BytesIO
from unittest.mock import AsyncMock

import httpx
import pytest
from PIL import Image

from custom_components.parro.api import ParroApi, ParroAuthError, ParroConnectionError, ParroError
from custom_components.parro.chat_feed import ParroChatFeed


@pytest.fixture
def chat_server(monkeypatch):
    original_init = httpx.Client.__init__
    state = {
        "requests": [],
        "rooms": [{"links": [{"rel": "self", "id": 12}], "title": "Synthetic teacher"}],
        "messages": [],
        "message_status": 200,
    }

    def handler(request):
        state["requests"].append(request)
        if request.url.path.endswith("/account/me"):
            return httpx.Response(200, json={"links": [{"rel": "self", "id": 81}]})
        if request.url.path.endswith("/chatroom"):
            return httpx.Response(200, json={"items": state["rooms"]})
        if request.url.path.endswith("/chatroom/12/chatmessage"):
            return httpx.Response(
                state["message_status"], json={"items": state["messages"], "secret": "not-for-user"}
            )
        return httpx.Response(404)

    def client_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", client_init)
    return state


def photo():
    """Official public web app's RChatTextMessage.attachment shape.

    https://talk.parro.com/main.dart.js, inspected anonymously 2026-09-08:
    RChatTextMessage decodes singular attachment as RChatMessageAttachment;
    its inherited RAttachment decodes attachmentType and entries.
    """
    return {
        "dtype": "attachment.RChatMessageAttachment",
        "attachmentType": "image",
        "entries": [
            {
                "dtype": "attachment.RAttachmentImageEntry",
                "type": "SOURCE",
                "url": "https://cdn.example.invalid/photo?token=synthetic-secret",
            }
        ],
    }


async def test_actual_sdk_singular_chat_attachment_becomes_private_jpeg(hass, chat_server):
    chat_server["messages"] = [
        {
            "dtype": "chat.RChatTextMessage",
            "links": [{"rel": "self", "id": 44}],
            "text": "<p>Good morning</p><script>hidden()</script>",
            "identity": {"firstName": "Synthetic", "surname": "Teacher"},
            "createdAt": "2026-09-08T08:00:00Z",
            "lastModifiedAt": "2026-09-08T09:00:00Z",
            "attachment": photo(),
        }
    ]
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    feed = ParroChatFeed(hass, api)
    result = await feed.async_get_messages("12")
    assert result["conversation"] == {"id": "12", "title": "Synthetic teacher"}
    message = result["items"][0]
    assert message["contents"] == "Good morning"
    assert message["sender"] == "Synthetic Teacher"
    assert message["created_at"] == "2026-09-08T08:00:00Z"
    assert message["sort_date"] == message["created_at"]
    handle = message["images"][0]["id"]
    assert len(handle) == 32
    assert "synthetic-secret" not in str(result)
    assert "http" not in str(result)
    assert result["limit"] == 20
    assert [request.headers.get("Range") for request in chat_server["requests"]] == [
        None,
        "items=0-49",
        "items=0-19",
    ]
    assert all(request.method == "GET" for request in chat_server["requests"])
    assert (await feed.async_get_conversations())["returned"] == 1
    assert await feed.async_get_messages("12") == result
    assert len(chat_server["requests"]) == 3
    original = BytesIO()
    Image.new("RGB", (30, 20), "red").save(original, "PNG")
    feed._download = AsyncMock(return_value=original.getvalue())
    encoded, mime = await feed.async_get_image(handle)
    assert mime == "image/jpeg"
    with Image.open(BytesIO(encoded)) as image:
        assert image.format == "JPEG" and image.size == (30, 20)
    assert await feed.async_get_image(handle) == (encoded, mime)
    feed._download.assert_awaited_once()
    # Existing public action remains unchanged and never returns source URLs.
    public = await api.async_get_messages("12", 1)
    assert public[0]["attachments"] == []
    assert "synthetic-secret" not in str(public)
    assert public[0]["last_modified_at"] == "2026-09-08T09:00:00Z"
    await feed.async_close()
    await api.async_close()
    assert not feed._refs and not feed._images and not feed._messages


@pytest.mark.parametrize("room_id", ["13", "99999999999999999999"])
async def test_unknown_room_never_fetches_messages(hass, chat_server, room_id):
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    with pytest.raises(ParroError, match="unavailable"):
        await api._async_fetch_chat_source(room_id)
    assert not any(request.url.path.endswith("/chatmessage") for request in chat_server["requests"])
    await api.async_close()


async def test_membership_lookup_is_bounded_even_if_server_ignores_range(hass, chat_server):
    chat_server["rooms"] = [{"id": index} for index in range(100, 150)] + [{"id": 12}]
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    with pytest.raises(ParroError, match="unavailable"):
        await api._async_fetch_chat_source("12")
    assert len(chat_server["requests"]) == 2
    await api.async_close()


async def test_deleted_media_is_omitted_and_unknown_media_is_not_guessed(hass, chat_server):
    chat_server["messages"] = [
        {"id": 1, "text": "Deleted text", "deleted": True, "attachment": photo()},
        {
            "id": 2,
            "text": "",
            "attachment": {"attachmentType": "video", "entries": photo()["entries"]},
        },
        {"id": 3, "text": "", "unknownMedia": {"url": "https://private.invalid/secret"}},
        {"id": 4, "text": "", "attachment": photo()},
    ]
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    source = await api._async_fetch_chat_source("12")
    assert [item["id"] for item in source["items"]] == ["2", "3", "4"]
    assert source["items"][0]["image_sources"] == []
    assert source["items"][1]["image_sources"] == []
    assert len(source["items"][2]["image_sources"]) == 1
    await api.async_close()


@pytest.mark.parametrize(
    "attachment",
    [None, [], "bad", {"entries": None}, {"attachmentType": "image", "entries": [None]}],
)
async def test_malformed_optional_photos_keep_message(hass, chat_server, attachment):
    chat_server["messages"] = [{"text": "Still available", "attachment": attachment}] * 100
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    source = await api._async_fetch_chat_source("12", limit=2)
    assert len(source["items"]) == 2
    assert source["items"][0]["contents"] == "Still available"
    assert source["items"][0]["image_sources"] == []
    assert chat_server["requests"][-1].headers["Range"] == "items=0-1"
    await api.async_close()


@pytest.mark.parametrize("room_id", [True, 12, "0", "../12", "https://private.invalid", "1" * 21])
async def test_malformed_room_ids_fail_before_http(hass, chat_server, room_id):
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    with pytest.raises(ParroError):
        await api._async_fetch_chat_source(room_id)
    assert not chat_server["requests"]
    await api.async_close()


@pytest.mark.parametrize("limit", [True, 0, -1, 21, "20", None])
async def test_private_message_limit_is_twenty(hass, chat_server, limit):
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    with pytest.raises(ParroError):
        await api._async_fetch_chat_source("12", limit)
    assert not chat_server["requests"]
    await api.async_close()


@pytest.mark.parametrize(
    "status,error",
    [
        (401, ParroAuthError),
        (403, ParroAuthError),
        (429, ParroConnectionError),
        (500, ParroConnectionError),
    ],
)
async def test_errors_are_classified_without_server_details(hass, chat_server, status, error):
    chat_server["message_status"] = status
    api = ParroApi(hass, {"access_token": "synthetic-access"}, "81", lambda tokens: None)
    with pytest.raises(error) as caught:
        await api._async_fetch_chat_source("12")
    assert "not-for-user" not in str(caught.value)
    assert "synthetic" not in str(caught.value)
    await api.async_close()
