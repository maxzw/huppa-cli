import json
from unittest.mock import Mock

import pytest
import requests
from huppa_cli.client import HuppaAPIError, HuppaClient


def _response(status_code: int, payload: dict) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = json.dumps(payload).encode("utf-8")
    resp.url = "https://api.huppa.app/test"
    return resp


def test_request_retries_once_after_401(monkeypatch):
    monkeypatch.setattr(HuppaClient, "_login", lambda self: None)
    client = HuppaClient("user@example.com", "secret", "mygym")

    calls = []
    responses = [_response(401, {"error": "expired"}), _response(200, {"ok": True})]

    def fake_request(method, url, **kwargs):
        calls.append(kwargs)
        return responses.pop(0)

    client.session.request = Mock(side_effect=fake_request)
    relogin = Mock()
    client._login = relogin

    response = client._request("GET", "https://api.huppa.app/users/me/occurrences")

    assert response.status_code == 200
    assert relogin.call_count == 1
    assert len(calls) == 2
    assert all("timeout" in call for call in calls)


def test_request_timeout_raises_normalized_error(monkeypatch):
    monkeypatch.setattr(HuppaClient, "_login", lambda self: None)
    client = HuppaClient("user@example.com", "secret", "mygym")
    client.session.request = Mock(side_effect=requests.Timeout("timeout"))

    with pytest.raises(HuppaAPIError, match="timed out"):
        client._request("GET", "https://api.huppa.app/users/me/occurrences")


def test_cancel_booking_returns_none_for_empty_or_non_json(monkeypatch):
    monkeypatch.setattr(HuppaClient, "_login", lambda self: None)
    client = HuppaClient("user@example.com", "secret", "mygym")

    empty_response = requests.Response()
    empty_response.status_code = 204
    empty_response._content = b""

    text_response = requests.Response()
    text_response.status_code = 200
    text_response._content = b"ok"

    client._request = Mock(side_effect=[empty_response, text_response])

    assert client.cancel_booking("org", "occ") is None
    assert client.cancel_booking("org", "occ") is None
