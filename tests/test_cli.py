import json

import pytest
from click.testing import CliRunner

from huppa_cli.cli import cli


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
