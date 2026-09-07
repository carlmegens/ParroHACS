"""Isolated Home Assistant fixtures. All account and school data is synthetic."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Resolve our namespace before HA's temporary test config is added to sys.path.
import custom_components.parro  # noqa: F401

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Load this repository's custom integration in a real HA test instance."""


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.async_fetch_summary.return_value = {
        "children_count": 2,
        "groups_count": 3,
        "unread_announcements": 4,
        "unread_chatrooms": 1,
    }
    for name in ("announcements", "chatrooms", "messages", "calendar_urls"):
        getattr(api, f"async_get_{name}").return_value = []
    return api


@pytest.fixture
def config_entry():
    return MockConfigEntry(
        domain="parro",
        title="Parro test",
        unique_id="acct-1",
        data={
            "account_id": "acct-1",
            "tokens": {
                "access_token": "synthetic-access",
                "refresh_token": "synthetic-refresh",
                "expires_at": 4102444800,
            },
        },
    )
