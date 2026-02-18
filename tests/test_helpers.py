"""
Tests for all helper functions in github_engineer.py
Covers: _slugify, _branch_name, _fmt_issue, _cfg,
        _read_env, _write_env, _missing_creds, _cred_prompt,
        _search_local_logs, _ensure_label
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import github_engineer as ge


# ── _slugify ──────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert ge._slugify("Fix Login Bug") == "fix-login-bug"

def test_slugify_special_chars():
    assert ge._slugify("Fix: login/bug!") == "fix-login-bug"

def test_slugify_max_len():
    result = ge._slugify("a" * 100)
    assert len(result) <= 40

def test_slugify_leading_trailing_dashes():
    result = ge._slugify("---fix---")
    assert not result.startswith("-")
    assert not result.endswith("-")

def test_slugify_numbers():
    assert ge._slugify("Issue 42 fix") == "issue-42-fix"


# ── _branch_name ─────────────────────────────────────────────────────────────

def test_branch_name_format():
    assert ge._branch_name(42, "Fix login bug") == "issue-42-fix-login-bug"

def test_branch_name_includes_number():
    assert ge._branch_name(7, "Critical DB failure").startswith("issue-7-")


# ── _fmt_issue ────────────────────────────────────────────────────────────────

def test_fmt_issue_contains_title(fake_issue):
    assert "Fix login bug" in ge._fmt_issue(fake_issue)

def test_fmt_issue_contains_number(fake_issue):
    assert "#42" in ge._fmt_issue(fake_issue)

def test_fmt_issue_contains_labels(fake_issue):
    result = ge._fmt_issue(fake_issue)
    assert "bug" in result
    assert "high" in result

def test_fmt_issue_no_body_fallback():
    issue = {"number": 1, "title": "Test", "html_url": "http://x", "labels": [], "body": None}
    assert "No description provided." in ge._fmt_issue(issue)

def test_fmt_issue_no_labels():
    issue = {"number": 1, "title": "Test", "html_url": "http://x", "labels": [], "body": "desc"}
    assert "none" in ge._fmt_issue(issue)


# ── _cfg ──────────────────────────────────────────────────────────────────────

def test_cfg_reads_from_os_environ(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "from_env")
    assert ge._cfg("GITHUB_APP_ID") == "from_env"

def test_cfg_reads_from_env_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    (tmp_path / ".env").write_text("GITHUB_REPO=owner/repo\n")
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    assert ge._cfg("GITHUB_REPO") == "owner/repo"

def test_cfg_prefers_os_environ_over_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    (tmp_path / ".env").write_text("GITHUB_APP_ID=from_file\n")
    monkeypatch.setenv("GITHUB_APP_ID", "from_env")
    assert ge._cfg("GITHUB_APP_ID") == "from_env"

def test_cfg_returns_none_when_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
    assert ge._cfg("NONEXISTENT_KEY") is None


# ── _read_env / _write_env ────────────────────────────────────────────────────

def test_read_env_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    assert ge._read_env() == {}

def test_write_then_read_env(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    ge._write_env("MY_KEY", "my_value")
    assert ge._read_env()["MY_KEY"] == "my_value"

def test_write_env_updates_os_environ(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    ge._write_env("MY_KEY2", "hello")
    assert os.environ.get("MY_KEY2") == "hello"

def test_read_env_ignores_comments(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    (tmp_path / ".env").write_text("# comment\nKEY=val\n")
    data = ge._read_env()
    assert "comment" not in data
    assert data["KEY"] == "val"

def test_write_env_overwrites_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    ge._write_env("K", "old")
    ge._write_env("K", "new")
    assert ge._read_env()["K"] == "new"


# ── _missing_creds ────────────────────────────────────────────────────────────

def test_missing_creds_all_missing():
    missing = ge._missing_creds()
    assert "GITHUB_APP_ID" in missing
    assert "GITHUB_REPO" in missing

def test_missing_creds_partial(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    missing = ge._missing_creds()
    assert "GITHUB_APP_ID" not in missing
    assert "GITHUB_REPO" in missing

def test_missing_creds_all_set(monkeypatch, tmp_path):
    pem = tmp_path / "key.pem"
    pem.write_text("x")
    monkeypatch.setenv("GITHUB_APP_ID", "1")
    monkeypatch.setenv("GITHUB_INSTALLATION_ID", "2")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(pem))
    monkeypatch.setenv("GITHUB_REPO", "a/b")
    assert ge._missing_creds() == []


# ── _cred_prompt ─────────────────────────────────────────────────────────────

def test_cred_prompt_contains_label():
    assert "GitHub App ID" in ge._cred_prompt("GITHUB_APP_ID")

def test_cred_prompt_contains_how():
    assert "Developer settings" in ge._cred_prompt("GITHUB_APP_ID")

def test_cred_prompt_asks_user_to_provide():
    prompt = ge._cred_prompt("GITHUB_REPO")
    assert "provide" in prompt.lower() or "save" in prompt.lower()


# ── _search_local_logs ────────────────────────────────────────────────────────

def test_search_local_logs_finds_match(tmp_path, monkeypatch):
    (tmp_path / "app.log").write_text("2024-01-01 ERROR: login failed\n2024-01-02 INFO: ok\n")
    monkeypatch.setenv("LOCAL_LOG_PATTERNS", str(tmp_path / "*.log"))
    hits = ge._search_local_logs("login failed")
    assert any("login failed" in h for h in hits)

def test_search_local_logs_no_match(tmp_path, monkeypatch):
    (tmp_path / "app.log").write_text("nothing relevant here\n")
    monkeypatch.setenv("LOCAL_LOG_PATTERNS", str(tmp_path / "*.log"))
    assert ge._search_local_logs("xyzzy_no_match") == []

def test_search_local_logs_no_patterns(monkeypatch):
    monkeypatch.delenv("LOCAL_LOG_PATTERNS", raising=False)
    assert ge._search_local_logs("anything") == []

def test_search_local_logs_max_20(tmp_path, monkeypatch):
    (tmp_path / "big.log").write_text("\n".join(["match line"] * 50))
    monkeypatch.setenv("LOCAL_LOG_PATTERNS", str(tmp_path / "*.log"))
    assert len(ge._search_local_logs("match line")) <= 20

def test_search_local_logs_multiple_patterns(tmp_path, monkeypatch):
    (tmp_path / "a.log").write_text("error in module A\n")
    (tmp_path / "b.log").write_text("error in module B\n")
    monkeypatch.setenv("LOCAL_LOG_PATTERNS",
                       f"{tmp_path / 'a.log'},{tmp_path / 'b.log'}")
    hits = ge._search_local_logs("error")
    assert len(hits) == 2

def test_search_local_logs_unreadable_file_skipped(tmp_path, monkeypatch):
    log = tmp_path / "bad.log"
    log.write_text("some error here\n")
    monkeypatch.setenv("LOCAL_LOG_PATTERNS", str(tmp_path / "*.log"))
    # Patch open to raise for this file — should not crash
    original_read = Path.read_text
    def patched_read(self, *args, **kwargs):
        if self.name == "bad.log":
            raise PermissionError("no access")
        return original_read(self, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", patched_read)
    hits = ge._search_local_logs("error")  # should not raise
    assert isinstance(hits, list)


# ── _ensure_label ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ensure_label_does_not_raise_if_label_exists(all_creds):
    """_ensure_label swallows errors silently — existing label must not crash."""
    async def mock_gh_raise(*args, **kwargs):
        raise Exception("422 label already exists")

    with patch("github_engineer._gh", side_effect=mock_gh_raise):
        # Should complete without raising
        await ge._ensure_label("owner/repo", "fake-token", "in-progress", "0075ca")


# ── _make_jwt ─────────────────────────────────────────────────────────────────

def test_make_jwt_raises_when_app_id_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(tmp_path / "k.pem"))
    with pytest.raises(ValueError, match="GITHUB_APP_ID"):
        ge._make_jwt()

def test_make_jwt_raises_when_key_missing(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.delenv("GITHUB_PRIVATE_KEY_PATH", raising=False)
    with pytest.raises(ValueError):
        ge._make_jwt()


# ── _get_token ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_token_raises_when_installation_id_missing(monkeypatch, tmp_path):
    pem = tmp_path / "k.pem"
    pem.write_text("fake")
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(pem))
    monkeypatch.delenv("GITHUB_INSTALLATION_ID", raising=False)
    with pytest.raises(ValueError, match="GITHUB_INSTALLATION_ID"):
        await ge._get_token()
