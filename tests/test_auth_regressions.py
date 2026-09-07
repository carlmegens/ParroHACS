"""Synthetic login regressions; never use real credentials or live endpoints."""

from urllib.parse import parse_qs

import httpx
import pytest

from custom_components.parro.api import ParroLoginFlowError, _check_state, _error, async_login


@pytest.fixture
def authorize_resume_server(monkeypatch):
    """Emulate an IDP resuming its saved authorize request after login."""
    original_init = httpx.Client.__init__
    scenario = {"resume_state": None, "callback_state": "original", "requests": []}

    def handler(request):
        scenario["requests"].append((request.method, request.url.path))
        if request.url.path == "/idp/oauth2/authorize":
            if "client_id" in request.url.params:
                scenario["original_state"] = request.url.params["state"]
                return httpx.Response(302, headers={"location": "/login"})
            callback_state = (
                scenario["original_state"]
                if scenario["callback_state"] == "original"
                else scenario["callback_state"]
            )
            return httpx.Response(
                302,
                headers={"location": f"parro://oauth2?code=synthetic-code&state={callback_state}"},
            )
        if request.url.path == "/login" and request.method == "GET":
            return httpx.Response(
                200,
                text='<form action="/login"><input type="email" name="emailadres">'
                '<input type="password" name="wachtwoord"></form>',
            )
        if request.url.path == "/login" and request.method == "POST":
            submitted = parse_qs(request.content.decode())
            assert submitted["emailadres"] == ["synthetic@example.invalid"]
            assert submitted["wachtwoord"] == ["synthetic-password"]
            resume = "/idp/oauth2/authorize"
            if scenario["resume_state"] is not None:
                value = (
                    scenario["original_state"]
                    if scenario["resume_state"] == "original"
                    else scenario["resume_state"]
                )
                resume += f"?state={value}"
            return httpx.Response(302, headers={"location": resume})
        if request.url.path == "/idp/oauth2/token":
            return httpx.Response(
                200,
                json={"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"},
            )
        if request.url.path == "/rest/v2/account/me":
            return httpx.Response(200, json={"links": [{"rel": "self", "id": 81}]})
        return httpx.Response(404)

    def client_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", client_init)
    return scenario


@pytest.mark.parametrize("resume_state", [None, "original"])
async def test_authorize_resume_preserves_original_oauth_state(
    hass, authorize_resume_server, resume_state
):
    """A resumed authorize URL need not repeat session-bound OAuth parameters."""
    authorize_resume_server["resume_state"] = resume_state
    result = await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    assert result.account_id == "81"
    assert authorize_resume_server["requests"] == [
        ("GET", "/idp/oauth2/authorize"),
        ("GET", "/login"),
        ("POST", "/login"),
        ("GET", "/idp/oauth2/authorize"),
        ("POST", "/idp/oauth2/token"),
        ("GET", "/rest/v2/account/me"),
    ]


async def test_authorize_redirect_cannot_replace_original_oauth_state(
    hass, authorize_resume_server
):
    """A later redirect must not redefine what state is considered authentic."""
    authorize_resume_server["resume_state"] = "replacement-state"
    authorize_resume_server["callback_state"] = "replacement-state"
    with pytest.raises(ParroLoginFlowError, match="state_mismatch"):
        await async_login(hass, "synthetic@example.invalid", "synthetic-password")
    assert ("POST", "/idp/oauth2/token") not in authorize_resume_server["requests"]


@pytest.mark.parametrize(
    "query",
    ["state=original&state=", "state=&state=original", "state=original&state", "state=", ""],
)
def test_callback_rejects_duplicate_blank_or_missing_state(query):
    with pytest.raises(ParroLoginFlowError, match="state_mismatch"):
        _check_state(f"parro://oauth2?code=synthetic-code&{query}", "original")


@pytest.mark.parametrize(
    "message,reason",
    [
        (
            "Login mislukt: kon geen authorization code verkrijgen. synthetic-password",
            "login_not_completed",
        ),
        (
            "Login mislukt: onjuist wachtwoord of gebruikersnaam. synthetic-password",
            "login_not_completed",
        ),
        (
            "Token exchange mislukt: {'access_token': 'synthetic-secret-token'}",
            "token_exchange_failed",
        ),
        (
            "Kon het login formulier niet vinden. https://private.invalid/synthetic-secret",
            "unsupported_login_form",
        ),
        ("Unexpected failure containing synthetic-secret-token", "login_not_completed"),
    ],
)
def test_sdk_runtime_failures_have_only_allowlisted_reasons(message, reason):
    """SDK failure text can contain private token responses; never reuse it."""
    error = _error(RuntimeError(message), login=True)
    assert isinstance(error, ParroLoginFlowError)
    assert error.reason == reason
    assert str(error) == reason
    assert "synthetic" not in repr(error)
    assert error.__cause__ is None


@pytest.mark.parametrize(
    "reason", ["synthetic-secret-token", "state_mismatch secret", "", None, []]
)
def test_login_reason_constructor_rejects_unapproved_diagnostics(reason):
    with pytest.raises(ValueError) as error:
        ParroLoginFlowError(reason)
    assert str(error.value) == "Unsupported Parro login failure reason"


def test_login_reason_constructor_accepts_the_complete_safe_contract():
    for reason in ParroLoginFlowError.REASONS:
        error = ParroLoginFlowError(reason)
        assert str(error) == error.reason == reason
