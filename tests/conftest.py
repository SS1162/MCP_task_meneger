import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def isolate_env(tmp_path, monkeypatch):
    """Each test gets a clean environment — no real credentials leak in."""
    for key in [
        "GITHUB_APP_ID", "GITHUB_INSTALLATION_ID",
        "GITHUB_PRIVATE_KEY_PATH", "GITHUB_REPO", "LOCAL_LOG_PATTERNS",
    ]:
        monkeypatch.delenv(key, raising=False)

    import github_engineer as ge
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")


@pytest.fixture()
def all_creds(monkeypatch, tmp_path):
    """Set all required credentials via env vars (no real GitHub calls)."""
    pem = tmp_path / "test.pem"
    pem.write_text("fake-key")
    monkeypatch.setenv("GITHUB_APP_ID", "123456")
    monkeypatch.setenv("GITHUB_INSTALLATION_ID", "99999")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(pem))
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")


@pytest.fixture()
def fake_issue():
    return {
        "number": 42,
        "title": "Fix login bug",
        "html_url": "https://github.com/owner/repo/issues/42",
        "labels": [{"name": "bug"}, {"name": "high"}],
        "body": "Users cannot log in after the latest deploy.",
    }
