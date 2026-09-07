"""The complete flow, SDK, HA entities and response actions over a fake server."""

from unittest.mock import patch
from urllib.parse import parse_qs

import httpx
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType


async def test_login_setup_action_refresh_and_unload_against_http_server(hass):
    requests = []
    state = None

    def server(request):
        nonlocal state
        requests.append(request)
        path = request.url.path
        if path == "/idp/oauth2/authorize":
            state = request.url.params["state"]
            return httpx.Response(
                200,
                text='<form action="/login"><input type="email" name="emailadres"><input type="password" name="wachtwoord"></form>',
            )
        if path == "/login":
            data = parse_qs(request.content.decode())
            assert data["emailadres"] == ["synthetic@example.invalid"]
            assert data["wachtwoord"] == ["synthetic-password"]
            return httpx.Response(
                302, headers={"location": f"parro://oauth2?code=synthetic&state={state}"}
            )
        if path == "/idp/oauth2/token":
            data = parse_qs(request.content.decode())
            if data["grant_type"] == ["authorization_code"]:
                assert data["code_verifier"]
                return httpx.Response(
                    200,
                    json={
                        "access_token": "old-access",
                        "refresh_token": "old-refresh",
                        "expires_in": 3600,
                    },
                )
            assert data["grant_type"] == ["refresh_token"]
            assert data["refresh_token"] == ["old-refresh"]
            return httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 3600,
                },
            )
        assert request.url.host == "rest-v2.parro.com"
        assert request.method == "GET"
        if path == "/rest/v2/account/me":
            return httpx.Response(200, json={"links": [{"rel": "self", "id": 123}]})
        if path == "/rest/v2/child":
            return httpx.Response(200, json={"items": [{"links": [{"rel": "self", "id": 456}]}]})
        if path == "/rest/v2/group":
            return httpx.Response(200, json={"items": [{"id": 10}, {"id": 11}]})
        if path == "/rest/v2/identity/unreadcounts":
            return httpx.Response(
                200,
                json={"items": [{"numberOfUnreadAnnouncements": 2, "numberOfUnreadChatRooms": 1}]},
            )
        if path == "/rest/v2/event":
            assert request.headers["range"] == "items=0-1"
            if request.headers["authorization"] == "Bearer old-access":
                return httpx.Response(401)
            assert request.headers["authorization"] == "Bearer new-access"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 100,
                            "title": "SYNTHETIC-SCHOOL-TITLE",
                            "contents": "SYNTHETIC-PRIVATE-CONTENT",
                            "attachments": [
                                {
                                    "id": 12,
                                    "name": "notice.pdf",
                                    "url": "https://example.invalid/private-attachment",
                                }
                            ],
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected endpoint: {path}")

    transport = httpx.MockTransport(server)
    with patch.object(httpx.Client, "_transport_for_url", return_value=transport):
        result = await hass.config_entries.flow.async_init("parro", context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "synthetic@example.invalid", "password": "synthetic-password"},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        entry = result["result"]
        assert entry.unique_id == "123"
        assert entry.state is ConfigEntryState.LOADED
        assert len(hass.states.async_all()) == 6
        assert not any(
            request.url.path.endswith(("event", "chatroom", "chatmessage", "sync"))
            for request in requests
        )
        with patch.object(hass.config_entries, "async_reload") as reload:
            response = await hass.services.async_call(
                "parro",
                "get_announcements",
                {"config_entry_id": entry.entry_id, "limit": 2},
                blocking=True,
                return_response=True,
            )
            await hass.async_block_till_done()
            reload.assert_not_called()
        assert response["returned"] == 1
        assert response["items"][0]["contents"] == "SYNTHETIC-PRIVATE-CONTENT"
        assert "private-attachment" not in str(response)
        assert entry.data["tokens"]["refresh_token"] == "new-refresh"
        assert set(entry.data) == {"account_id", "tokens"}
        for value in (
            "SYNTHETIC-PRIVATE-CONTENT",
            "SYNTHETIC-SCHOOL-TITLE",
            "old-access",
            "new-refresh",
            "private-attachment",
        ):
            assert value not in str([state.as_dict() for state in hass.states.async_all()])
        token_requests = [
            request for request in requests if request.url.path == "/idp/oauth2/token"
        ]
        assert len(token_requests) == 2  # One login exchange and exactly one refresh.
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
