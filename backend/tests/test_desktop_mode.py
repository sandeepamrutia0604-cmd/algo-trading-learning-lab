from pathlib import Path

from backend.app import config, paths
from backend.app.config import settings


def test_health_says_whether_this_is_the_windows_download(client, monkeypatch):
    assert client.get("/api/health").json()["desktop"] is False
    monkeypatch.setattr(settings, "desktop_mode", True)
    assert client.get("/api/health").json()["desktop"] is True


def test_the_broker_routes_exist_normally_but_not_in_desktop_mode(client, monkeypatch):
    assert client.get("/api/data-sources").status_code == 200

    monkeypatch.setattr(settings, "desktop_mode", True)
    assert client.get("/api/data-sources").status_code == 404
    response = client.post("/api/data-sources/import", json={"source": "upstox", "symbols": ["SBIN"]})
    assert response.status_code == 404


def test_other_routes_still_work_in_desktop_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "desktop_mode", True)
    assert client.get("/api/portfolio").status_code == 200
    assert client.get("/api/stocks").status_code == 200


def test_data_goes_to_a_per_user_folder_in_desktop_mode(monkeypatch, tmp_path):
    monkeypatch.delenv("ALGO_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("ALGO_DESKTOP", "1")
    assert paths.data_dir() == tmp_path / "AlgoTradingLab"

    monkeypatch.delenv("ALGO_DESKTOP")
    assert paths.data_dir() == Path("data")

    monkeypatch.setenv("ALGO_DATA_DIR", str(tmp_path / "elsewhere"))
    assert paths.data_dir() == tmp_path / "elsewhere"


def test_desktop_settings_ignore_broker_choice_and_use_the_user_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("ALGO_DESKTOP", "1")
    monkeypatch.setenv("ALGO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "upstox")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    made = config.Settings()

    assert made.desktop_mode is True
    assert made.market_data_provider == "dummy"
    assert made.database_url == f"sqlite:///{(tmp_path / 'algo_trading.db').as_posix()}"


def test_a_normal_run_keeps_the_repo_defaults(monkeypatch):
    monkeypatch.delenv("ALGO_DESKTOP", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)

    made = config.Settings(_env_file=None)

    assert made.desktop_mode is False
    assert made.database_url == config.DEFAULT_DATABASE_URL


def test_resource_dir_is_the_repo_when_not_frozen():
    assert (paths.resource_dir() / "frontend" / "index.html").is_file()
