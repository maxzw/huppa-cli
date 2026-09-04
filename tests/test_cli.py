import json

import pytest
from click.testing import CliRunner

from huppa_cli.cli import cli
from huppa_cli.update import UpdateError


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

    def book_class(self, org_id, occ_id):
        return {"booked": True}

    def cancel_booking(self, org_id, occ_id):
        return {"cancelled": True}

    def join_waitlist(self, org_id, occ_id):
        return {"waitlisted": True}

    def leave_waitlist(self, org_id, occ_id):
        return {"left": True}


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def fake_client(monkeypatch):
    monkeypatch.setattr("huppa_cli.cli._get_client", lambda: _FakeClient())


def test_classes_single_date(runner, fake_client):
    result = runner.invoke(cli, ["classes", "2026-03-08"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == [{"date": "2026-03-08", "name": "Spin"}]


def test_classes_multiple_dates(runner, fake_client):
    result = runner.invoke(cli, ["classes", "2026-03-08", "2026-03-09"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "2026-03-08" in data
    assert "2026-03-09" in data


def test_classes_invalid_date(runner, fake_client):
    result = runner.invoke(cli, ["classes", "08-03-2026"])
    assert result.exit_code != 0
    assert "YYYY-MM-DD" in result.output


def test_bookings_default(runner, fake_client):
    result = runner.invoke(cli, ["bookings"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == [{"filter": "upcoming", "per_page": 50, "page": 1}]


def test_bookings_with_filter(runner, fake_client):
    result = runner.invoke(cli, ["bookings", "--filter", "past"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["filter"] == "past"


def test_bookings_invalid_filter(runner, fake_client):
    result = runner.invoke(cli, ["bookings", "--filter", "today"])
    assert result.exit_code != 0


def test_memberships(runner, fake_client):
    result = runner.invoke(cli, ["memberships"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == [{"name": "Unlimited"}]


def test_book(runner, fake_client):
    result = runner.invoke(cli, ["book", "org1", "occ1"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {"booked": True}


def test_cancel(runner, fake_client):
    result = runner.invoke(cli, ["cancel", "org1", "occ1"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {"cancelled": True}


def test_waitlist_join(runner, fake_client):
    result = runner.invoke(cli, ["waitlist", "join", "org1", "occ1"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {"waitlisted": True}


def test_waitlist_leave(runner, fake_client):
    result = runner.invoke(cli, ["waitlist", "leave", "org1", "occ1"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == {"left": True}


def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "classes" in result.output
    assert "bookings" in result.output
    assert "mcp" in result.output
    assert "auth" in result.output


def test_version(runner, monkeypatch):
    monkeypatch.setattr("huppa_cli.cli.get_version", lambda: "1.2.3")

    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == "huppa 1.2.3"


def test_status_json_with_environment_credentials(runner, monkeypatch):
    monkeypatch.setenv("HUPPA_EMAIL", "user@example.com")
    monkeypatch.setenv("HUPPA_PASSWORD", "secret-password")
    monkeypatch.setenv("HUPPA_SUBDOMAIN", "mygym")
    monkeypatch.setattr("huppa_cli.cli._get_client", lambda: object())
    monkeypatch.setattr("huppa_cli.cli.keyring_backend_name", lambda: "test.backend")

    result = runner.invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["credential_source"] == "environment"
    assert data["password_configured"] is True
    assert data["api"] == "reachable"
    assert "secret-password" not in result.output


def test_status_reports_missing_credentials(runner, monkeypatch):
    for name in ("HUPPA_EMAIL", "HUPPA_PASSWORD", "HUPPA_SUBDOMAIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("huppa_cli.cli.load_credentials", lambda profile: None)
    monkeypatch.setattr("huppa_cli.cli.keyring_backend_name", lambda: "test.backend")

    result = runner.invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["credential_source"] == "partial/missing"
    assert data["password_configured"] is False
    assert data["api"] == "not checked"


def test_status_reports_api_error(runner, monkeypatch):
    monkeypatch.setenv("HUPPA_EMAIL", "user@example.com")
    monkeypatch.setenv("HUPPA_PASSWORD", "secret-password")
    monkeypatch.setenv("HUPPA_SUBDOMAIN", "mygym")
    monkeypatch.setattr("huppa_cli.cli._get_client", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr("huppa_cli.cli.keyring_backend_name", lambda: "test.backend")

    result = runner.invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["api"] == "error: offline"


def test_update_check(runner, monkeypatch):
    calls = {}

    def fake_update(**kwargs):
        calls.update(kwargs)
        return False

    monkeypatch.setattr("huppa_cli.cli.update_package", fake_update)

    result = runner.invoke(cli, ["update", "--check"])

    assert result.exit_code == 0
    assert calls["check_only"] is True
    assert calls["force"] is False
    assert callable(calls["output"])


def test_update_reports_failure(runner, monkeypatch):
    def fail(**kwargs):
        raise UpdateError("offline")

    monkeypatch.setattr("huppa_cli.cli.update_package", fail)

    result = runner.invoke(cli, ["update"])

    assert result.exit_code != 0
    assert "offline" in result.output
