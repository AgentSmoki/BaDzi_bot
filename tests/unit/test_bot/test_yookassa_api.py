"""Tests for bot.services.yookassa_api — ЮKassa REST API (Вариант B / СБП).

httpx is stubbed via MockTransport so no real network / credentials needed.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from unittest.mock import MagicMock

import httpx
import pytest
from pydantic import SecretStr

from bot.services import yookassa_api


def _settings(
    *,
    shop: str = "1378794",
    secret: str = "live_secret",
    api_enabled: bool = True,
    bypass: bool = False,
    receipt_email: str = "",
) -> MagicMock:
    s = MagicMock()
    s.yukassa_shop_id = SecretStr(shop)
    s.yukassa_secret_key = SecretStr(secret)
    s.yookassa_api_enabled = api_enabled
    s.forecast_free_bypass = bypass
    s.yookassa_return_url = "https://t.me/EdoHa_Badzi_bot"
    s.yookassa_receipt_email = receipt_email
    s.yookassa_vat_code = 1
    return s


# Capture the real class BEFORE any monkeypatch so the factory doesn't recurse
# into its own patched replacement.
_REAL_ASYNC_CLIENT = httpx.AsyncClient


def _client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[..., httpx.AsyncClient]:
    def factory(*_a: object, **kw: object) -> httpx.AsyncClient:
        return _REAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler),
            timeout=kw.get("timeout"),  # type: ignore[arg-type]
        )

    return factory


# ── gate ──────────────────────────────────────────────────────────────────


def test_api_live_requires_flag_creds_and_no_bypass() -> None:
    assert yookassa_api.yookassa_api_live(_settings()) is True
    assert yookassa_api.yookassa_api_live(_settings(api_enabled=False)) is False
    assert yookassa_api.yookassa_api_live(_settings(bypass=True)) is False
    assert yookassa_api.yookassa_api_live(_settings(shop="")) is False
    assert yookassa_api.yookassa_api_live(_settings(secret="")) is False


def test_auth_header_is_basic_base64() -> None:
    header = yookassa_api._auth_header(_settings(shop="shop", secret="key"))
    assert header == "Basic " + base64.b64encode(b"shop:key").decode()


# ── create_payment ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_payment_posts_correct_body_and_parses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["idem"] = request.headers.get("Idempotence-Key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "pay-1",
                "status": "pending",
                "confirmation": {"confirmation_url": "https://yoomoney.ru/checkout/pay-1"},
            },
        )

    monkeypatch.setattr(yookassa_api.httpx, "AsyncClient", _client_factory(handler))
    res = await yookassa_api.create_payment(
        _settings(),
        amount_rub=290,
        description="Безлимит вопросов — Месяц",
        metadata={"kind": "q", "plan": "monthly"},
        idempotence_key="idem-1",
    )
    assert res == {
        "id": "pay-1",
        "status": "pending",
        "confirmation_url": "https://yoomoney.ru/checkout/pay-1",
    }
    assert str(captured["url"]).endswith("/v3/payments")
    assert captured["idem"] == "idem-1"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["amount"] == {"value": "290.00", "currency": "RUB"}
    assert body["capture"] is True
    assert body["metadata"] == {"kind": "q", "plan": "monthly"}
    assert body["confirmation"]["return_url"] == "https://t.me/EdoHa_Badzi_bot"
    assert "receipt" not in body  # без email чек не прикладывается


@pytest.mark.asyncio
async def test_create_payment_includes_receipt_when_email_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "p", "status": "pending", "confirmation": {}})

    monkeypatch.setattr(yookassa_api.httpx, "AsyncClient", _client_factory(handler))
    await yookassa_api.create_payment(
        _settings(receipt_email="buyer@example.com"),
        amount_rub=290,
        description="Безлимит",
        metadata={"kind": "q", "plan": "monthly"},
    )
    body = captured["body"]
    assert isinstance(body, dict)
    receipt = body["receipt"]
    assert receipt["customer"]["email"] == "buyer@example.com"
    assert receipt["items"][0]["amount"] == {"value": "290.00", "currency": "RUB"}
    assert receipt["items"][0]["vat_code"] == 1


@pytest.mark.asyncio
async def test_create_payment_generates_idempotence_key_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["idem"] = request.headers.get("Idempotence-Key")
        return httpx.Response(200, json={"id": "p", "status": "pending", "confirmation": {}})

    monkeypatch.setattr(yookassa_api.httpx, "AsyncClient", _client_factory(handler))
    await yookassa_api.create_payment(_settings(), amount_rub=500, description="d", metadata={})
    assert isinstance(seen["idem"], str) and len(str(seen["idem"])) >= 16


# ── get_payment ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_payment_returns_status_and_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url).endswith("/v3/payments/pay-9")
        return httpx.Response(
            200,
            json={
                "id": "pay-9",
                "status": "succeeded",
                "paid": True,
                "metadata": {"kind": "q", "plan": "annual"},
            },
        )

    monkeypatch.setattr(yookassa_api.httpx, "AsyncClient", _client_factory(handler))
    res = await yookassa_api.get_payment(_settings(), "pay-9")
    assert res["status"] == "succeeded"
    assert res["paid"] is True
    assert res["metadata"] == {"kind": "q", "plan": "annual"}
