"""Private conversation/message caches with a separate guarded photo store."""

from __future__ import annotations

import re
from collections import OrderedDict
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant

from . import feed as feed_module
from .api import ParroApi, ParroAuthError, ParroConnectionError, ParroError
from .const import DEFAULT_LIMIT, MAX_FEED_LIMIT, MAX_LIMIT
from .feed import FEED_TTL, MAX_FEED_CACHES, STALE_TTL, ParroFeed, _FeedCache, _plain_text


class ParroChatFeed(ParroFeed):
    """Share photo implementation, never the announcement instance's references.

    Each instance owns its resolver, HTTP session, locks, image cache and opaque
    handles. Chat permission checks can therefore use a separate image route.
    """

    def __init__(self, hass: HomeAssistant, api: ParroApi) -> None:
        super().__init__(hass, api)
        self._conversations: _FeedCache | None = None
        self._messages: OrderedDict[str, _FeedCache] = OrderedDict()

    def _clear_data(self) -> None:
        super()._clear_data()
        self._conversations = None
        self._messages.clear()

    def _discard_conversation(self, chatroom_id: str) -> None:
        if cached := self._messages.pop(chatroom_id, None):
            retained = {
                image["id"]
                for remaining in self._messages.values()
                for item in remaining.value["items"]
                for image in item["images"]
            }
            for item in cached.value["items"]:
                for image in item["images"]:
                    if image["id"] not in retained:
                        self._remove_ref(image["id"])

    def _prune(self) -> None:
        super()._prune()
        now = feed_module._now()
        if self._conversations is not None and now - self._conversations.created > STALE_TTL:
            self._conversations = None
        for room_id, cached in list(self._messages.items()):
            if now - cached.created > STALE_TTL:
                self._discard_conversation(room_id)

    def _cache_conversations(self, source: list[dict[str, Any]]) -> _FeedCache:
        items = []
        for item in source[:MAX_LIMIT]:
            room_id = item.get("id")
            if (
                not isinstance(room_id, str)
                or not re.fullmatch(r"[0-9]{1,20}", room_id)
                or int(room_id) <= 0
            ):
                continue
            items.append(
                {
                    "id": room_id,
                    "title": _plain_text(item.get("title"), 1000),
                    "type": _plain_text(item.get("type"), 100),
                    "sort_date": item.get("sort_date"),
                    "unread_count": item.get("unread_count"),
                }
            )
        valid_ids = {item["id"] for item in items}
        for room_id in list(self._messages):
            if room_id not in valid_ids:
                self._discard_conversation(room_id)
        self._conversations = _FeedCache(
            {"items": items, "updated_at": datetime.now(UTC).isoformat()}, feed_module._now()
        )
        return self._conversations

    @staticmethod
    def _conversation_response(cached: _FeedCache, limit: int, *, stale: bool) -> dict[str, Any]:
        result = deepcopy(cached.value)
        result["items"] = result["items"][:limit]
        return {**result, "returned": len(result["items"]), "limit": limit, "stale": stale}

    async def async_get_conversations(self, limit: int = MAX_LIMIT) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise ParroError("The Parro conversation limit must be between 1 and 50")
        async with self._feed_lock:
            self._require_open()
            self._prune()
            cached = self._conversations
            if cached is not None and feed_module._now() - cached.created < FEED_TTL:
                return self._conversation_response(cached, limit, stale=False)
            try:
                source = await self.api.async_get_chatrooms(limit=MAX_LIMIT)
            except ParroAuthError:
                self._clear_data()
                raise
            except ParroConnectionError:
                self._require_open()
                if cached is None:
                    raise
                return self._conversation_response(cached, limit, stale=True)
            self._require_open()
            return self._conversation_response(
                self._cache_conversations(source), limit, stale=False
            )

    async def async_get_messages(
        self, chatroom_id: str, limit: int = DEFAULT_LIMIT
    ) -> dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= MAX_FEED_LIMIT:
            raise ParroError("The Parro message limit must be between 1 and 20")
        if (
            not isinstance(chatroom_id, str)
            or not re.fullmatch(r"[0-9]{1,20}", chatroom_id)
            or int(chatroom_id) <= 0
        ):
            raise ParroError("The selected Parro conversation is unavailable")
        async with self._feed_lock:
            self._require_open()
            self._prune()
            cached = self._messages.get(chatroom_id)
            if cached is not None and feed_module._now() - cached.created < FEED_TTL:
                self._messages.move_to_end(chatroom_id)
                return self._response(cached, limit, stale=False)
            try:
                # The adapter checks the account's current first 50 rooms before
                # fetching this room. Always cache up to 20 across all callers.
                source = await self.api._async_fetch_chat_source(chatroom_id, limit=MAX_FEED_LIMIT)
            except ParroAuthError:
                self._clear_data()
                raise
            except ParroConnectionError:
                self._require_open()
                if cached is None:
                    raise
                return self._response(cached, limit, stale=True)
            except ParroError:
                self._discard_conversation(chatroom_id)
                raise
            self._require_open()
            self._cache_conversations(source["conversations"])
            # The shared renderer strips markup, redacts private source URLs,
            # validates destinations and converts URLs into this instance's IDs.
            rendered = self._build_feed({"items": source["items"], "groups": []})
            value = {
                "items": [
                    {
                        key: item[key]
                        for key in ("id", "contents", "sender", "created_at", "sort_date", "images")
                    }
                    for item in rendered["items"]
                ],
                "conversation": {
                    "id": chatroom_id,
                    "title": _plain_text(source["conversation"].get("title"), 1000),
                },
                "updated_at": rendered["updated_at"],
            }
            cached = _FeedCache(value, feed_module._now())
            previous = self._messages.get(chatroom_id)
            self._messages[chatroom_id] = cached
            self._messages.move_to_end(chatroom_id)
            if previous is not None:
                # A successful refresh can remove a deleted photo. Revoke its
                # old handle unless another cached conversation still uses it.
                retained = {
                    image["id"]
                    for remaining in self._messages.values()
                    for item in remaining.value["items"]
                    for image in item["images"]
                }
                for item in previous.value["items"]:
                    for image in item["images"]:
                        if image["id"] not in retained:
                            self._remove_ref(image["id"])
            while len(self._messages) > MAX_FEED_CACHES:
                self._discard_conversation(next(iter(self._messages)))
            return self._response(cached, limit, stale=False)
