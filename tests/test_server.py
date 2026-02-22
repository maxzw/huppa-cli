import pytest

from huppa_cli import server


class _Dumpable:
    def __init__(self, payload: dict):
        self.payload = payload

    def model_dump(self) -> dict:
        return self.payload


class _FakeClient:
    def get_classes(self, date: str):
        return [_Dumpable({"date": date, "name": "Spin"})]

    def get_my_bookings(self, filter: str, per_page: int, page: int):
        return [_Dumpable({"filter": filter, "per_page": per_page, "page": page})]

    def get_memberships(self):
        return [_Dumpable({"name": "Unlimited"})]


@pytest.fixture(autouse=True)
def _reset_client_cache():
    server._client = None
    yield
    server._client = None


def test_get_classes_rejects_invalid_date():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        server.get_classes("26-02-2026")


def test_get_my_bookings_rejects_invalid_filter():
    with pytest.raises(ValueError, match="past"):
        server.get_my_bookings(filter="today")


def test_get_classes_returns_structured_data(monkeypatch):
    monkeypatch.setattr(server, "get_client", lambda: _FakeClient())
    result = server.get_classes("2026-02-26")
    assert result == [{"date": "2026-02-26", "name": "Spin"}]


def test_get_client_requires_setup_or_env(monkeypatch):
    monkeypatch.setattr(
        server.HuppaClient,
        "from_profile",
        classmethod(lambda cls, profile="default": (_ for _ in ()).throw(RuntimeError("run huppa auth setup"))),
    )

    with pytest.raises(RuntimeError, match="setup"):
        server.get_client()
