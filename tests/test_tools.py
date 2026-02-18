"""
Tests for all MCP tools in github_engineer.py
Covers: setup_credential, get_next_mission, manage_environment,
        confirm_manage_environment, finish_mission, confirm_finish_mission,
        search_mission_context, find_similar_bug_or_code
"""
import sys
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
import github_engineer as ge


# ── setup_credential ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_credential_saves_value(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    result = await ge.setup_credential("GITHUB_APP_ID", "999")
    assert "✅" in result
    assert ge._read_env().get("GITHUB_APP_ID") == "999"

@pytest.mark.asyncio
async def test_setup_credential_unknown_key(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    result = await ge.setup_credential("UNKNOWN_KEY", "val")
    assert "❌" in result

@pytest.mark.asyncio
async def test_setup_credential_pem_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    result = await ge.setup_credential("GITHUB_PRIVATE_KEY_PATH", "/nonexistent/path.pem")
    assert "❌" in result
    assert "not found" in result.lower()

@pytest.mark.asyncio
async def test_setup_credential_pem_copies_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    monkeypatch.chdir(tmp_path)
    pem = tmp_path / "my.pem"
    pem.write_text("-----BEGIN RSA PRIVATE KEY-----\nfake\n")
    result = await ge.setup_credential("GITHUB_PRIVATE_KEY_PATH", str(pem))
    assert "✅" in result

@pytest.mark.asyncio
async def test_setup_credential_local_log_patterns(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    result = await ge.setup_credential("LOCAL_LOG_PATTERNS", "./logs/**/*.log")
    assert "✅" in result

@pytest.mark.asyncio
async def test_setup_credential_strips_whitespace(tmp_path, monkeypatch):
    monkeypatch.setattr(ge, "ENV_FILE", tmp_path / ".env")
    await ge.setup_credential("GITHUB_APP_ID", "  123  ")
    assert ge._read_env().get("GITHUB_APP_ID") == "123"


# ── get_next_mission ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_next_mission_missing_creds():
    result = await ge.get_next_mission()
    assert "❌" in result
    assert "GitHub App ID" in result

@pytest.mark.asyncio
async def test_get_next_mission_no_issues(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=[]):
        result = await ge.get_next_mission()
    assert "caught up" in result.lower() or "no open issues" in result.lower()

@pytest.mark.asyncio
async def test_get_next_mission_returns_top_issue(all_creds, fake_issue):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=[fake_issue]):
        result = await ge.get_next_mission()
    assert "Fix login bug" in result
    assert "#42" in result

@pytest.mark.asyncio
async def test_get_next_mission_prioritises_critical(all_creds):
    low = {"number": 1, "title": "Minor typo", "html_url": "http://x", "labels": [], "body": "small"}
    critical = {"number": 2, "title": "Critical outage", "html_url": "http://y",
                "labels": [{"name": "critical"}], "body": "down"}
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=[low, critical]):
        result = await ge.get_next_mission()
    assert "Critical outage" in result

@pytest.mark.asyncio
async def test_get_next_mission_prioritises_p0(all_creds):
    low = {"number": 1, "title": "Low task", "html_url": "http://x", "labels": [], "body": ""}
    p0 = {"number": 2, "title": "P0 task", "html_url": "http://y",
          "labels": [{"name": "p0"}], "body": ""}
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=[low, p0]):
        result = await ge.get_next_mission()
    assert "P0 task" in result

@pytest.mark.asyncio
async def test_get_next_mission_medium_priority(all_creds):
    no_label = {"number": 1, "title": "No label task", "html_url": "http://x", "labels": [], "body": ""}
    medium = {"number": 2, "title": "Medium task", "html_url": "http://y",
              "labels": [{"name": "medium"}], "body": ""}
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=[no_label, medium]):
        result = await ge.get_next_mission()
    assert "Medium task" in result

@pytest.mark.asyncio
async def test_get_next_mission_skips_prs(all_creds, fake_issue):
    pr = {"number": 5, "title": "PR title", "html_url": "http://z",
          "labels": [], "body": "", "pull_request": {}}
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=[pr, fake_issue]):
        result = await ge.get_next_mission()
    assert "PR title" not in result
    assert "Fix login bug" in result

@pytest.mark.asyncio
async def test_get_next_mission_github_error(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, side_effect=Exception("API error")):
        result = await ge.get_next_mission()
    assert "❌" in result


# ── manage_environment ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_manage_environment_missing_creds():
    result = await ge.manage_environment(42)
    assert "❌" in result

@pytest.mark.asyncio
async def test_manage_environment_shows_permission_prompt(all_creds, fake_issue):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=fake_issue):
        result = await ge.manage_environment(42)
    assert "Permission required" in result
    assert "issue-42" in result
    assert "in-progress" in result

@pytest.mark.asyncio
async def test_manage_environment_branch_name_in_prompt(all_creds, fake_issue):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value=fake_issue):
        result = await ge.manage_environment(42)
    assert "issue-42-fix-login-bug" in result

@pytest.mark.asyncio
async def test_manage_environment_github_error(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, side_effect=Exception("API error")):
        result = await ge.manage_environment(42)
    assert "❌" in result


# ── confirm_manage_environment ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_manage_environment_missing_creds():
    result = await ge.confirm_manage_environment(42)
    assert "❌" in result

@pytest.mark.asyncio
async def test_confirm_manage_environment_creates_branch(all_creds, fake_issue):
    repo_data = {"default_branch": "main"}
    ref_data = {"object": {"sha": "abc123"}}
    call_log = []

    async def mock_gh(method, path, token, **kwargs):
        call_log.append((method, path))
        if "issues/42" in path and method == "get": return fake_issue
        if path == "/repos/owner/repo":             return repo_data
        if "ref/heads/main" in path:                return ref_data
        return {}

    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", side_effect=mock_gh):
        result = await ge.confirm_manage_environment(42)

    assert "✅" in result
    assert "issue-42-fix-login-bug" in result
    assert any("refs" in p and m == "post" for m, p in call_log)

@pytest.mark.asyncio
async def test_confirm_manage_environment_github_error(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await ge.confirm_manage_environment(42)
    assert "❌" in result


# ── finish_mission ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_finish_mission_missing_creds():
    result = await ge.finish_mission(42, "issue-42-fix")
    assert "❌" in result

@pytest.mark.asyncio
async def test_finish_mission_shows_permission_prompt(all_creds, fake_issue):
    async def mock_gh(method, path, token, **kwargs):
        if "issues/42" in path: return fake_issue
        return {"default_branch": "main"}

    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", side_effect=mock_gh):
        result = await ge.finish_mission(42, "issue-42-fix-login-bug")

    assert "Permission required" in result
    assert "in-review" in result
    assert "PR" in result or "pull" in result.lower()

@pytest.mark.asyncio
async def test_finish_mission_github_error(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await ge.finish_mission(42, "issue-42-fix")
    assert "❌" in result


# ── confirm_finish_mission ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirm_finish_mission_missing_creds():
    result = await ge.confirm_finish_mission(42, "issue-42-fix")
    assert "❌" in result

@pytest.mark.asyncio
async def test_confirm_finish_mission_opens_pr(all_creds, fake_issue):
    repo_data = {"default_branch": "main"}
    pr_data = {"html_url": "https://github.com/owner/repo/pull/10",
               "title": "Fix #42: Fix login bug"}

    async def mock_gh(method, path, token, **kwargs):
        if "issues/42" in path and method == "get": return fake_issue
        if path == "/repos/owner/repo":             return repo_data
        if "/pulls" in path and method == "post":   return pr_data
        return {}

    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", side_effect=mock_gh):
        result = await ge.confirm_finish_mission(42, "issue-42-fix-login-bug")

    assert "✅" in result
    assert "https://github.com/owner/repo/pull/10" in result

@pytest.mark.asyncio
async def test_confirm_finish_mission_label_delete_fails_but_pr_still_opens(all_creds, fake_issue):
    """Removing in-progress label may fail — PR must still open."""
    repo_data = {"default_branch": "main"}
    pr_data = {"html_url": "https://github.com/owner/repo/pull/11",
               "title": "Fix #42: Fix login bug"}

    async def mock_gh(method, path, token, **kwargs):
        if method == "delete" and "in-progress" in path:
            raise Exception("label not found")
        if "issues/42" in path and method == "get": return fake_issue
        if path == "/repos/owner/repo":             return repo_data
        if "/pulls" in path and method == "post":   return pr_data
        return {}

    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", side_effect=mock_gh):
        result = await ge.confirm_finish_mission(42, "issue-42-fix-login-bug")

    assert "✅" in result
    assert "pull/11" in result

@pytest.mark.asyncio
async def test_confirm_finish_mission_github_error(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, side_effect=Exception("fail")):
        result = await ge.confirm_finish_mission(42, "issue-42-fix")
    assert "❌" in result


# ── search_mission_context ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_mission_context_missing_creds():
    result = await ge.search_mission_context("login bug")
    assert "❌" in result

@pytest.mark.asyncio
async def test_search_mission_context_returns_github_results(all_creds, fake_issue):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value={"items": [fake_issue]}):
        result = await ge.search_mission_context("login bug")
    assert "Fix login bug" in result

@pytest.mark.asyncio
async def test_search_mission_context_includes_local_logs(all_creds, tmp_path, monkeypatch):
    (tmp_path / "app.log").write_text("ERROR: login failed\n")
    monkeypatch.setenv("LOCAL_LOG_PATTERNS", str(tmp_path / "*.log"))
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value={"items": []}):
        result = await ge.search_mission_context("login failed")
    assert "login failed" in result

@pytest.mark.asyncio
async def test_search_mission_context_no_log_patterns_message(all_creds, monkeypatch):
    monkeypatch.delenv("LOCAL_LOG_PATTERNS", raising=False)
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value={"items": []}):
        result = await ge.search_mission_context("anything")
    assert "Not configured" in result or "LOCAL_LOG_PATTERNS" in result

@pytest.mark.asyncio
async def test_search_mission_context_github_error_continues_to_local(all_creds, tmp_path, monkeypatch):
    """GitHub error shows warning but local log search still runs."""
    (tmp_path / "app.log").write_text("ERROR: timeout\n")
    monkeypatch.setenv("LOCAL_LOG_PATTERNS", str(tmp_path / "*.log"))
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, side_effect=Exception("rate limit")):
        result = await ge.search_mission_context("timeout")
    assert "timeout" in result
    assert "⚠️" in result


# ── find_similar_bug_or_code ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_similar_bug_missing_creds():
    result = await ge.find_similar_bug_or_code("login bug")
    assert "❌" in result

@pytest.mark.asyncio
async def test_find_similar_bug_returns_results(all_creds, fake_issue):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value={"items": [fake_issue]}):
        result = await ge.find_similar_bug_or_code("login bug")
    assert "Fix login bug" in result

@pytest.mark.asyncio
async def test_find_similar_bug_no_results(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, return_value={"items": []}):
        result = await ge.find_similar_bug_or_code("xyzzy_unique_query")
    assert "No similar results" in result

@pytest.mark.asyncio
async def test_find_similar_bug_github_error(all_creds):
    with patch("github_engineer._get_token", new_callable=AsyncMock, return_value="tok"), \
         patch("github_engineer._gh", new_callable=AsyncMock, side_effect=Exception("API fail")):
        result = await ge.find_similar_bug_or_code("login bug")
    assert "⚠️" in result
