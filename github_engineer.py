from typing import Any, Optional
import os
import glob
import re
import shutil
import time
from pathlib import Path

import httpx
import jwt
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("github-engineer")

GITHUB_API = "https://api.github.com"
ENV_FILE = Path(".env")

# ─── ENV HELPERS ─────────────────────────────────────────────────────────────

def _read_env() -> dict:
    env: dict = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _write_env(key: str, value: str) -> None:
    env = _read_env()
    env[key] = value
    ENV_FILE.write_text("\n".join(f"{k}={v}" for k, v in env.items()) + "\n", encoding="utf-8")
    os.environ[key] = value


def _cfg(key: str) -> Optional[str]:
    return os.environ.get(key) or _read_env().get(key)


# ─── CREDENTIAL SYSTEM ───────────────────────────────────────────────────────

_CRED_META = {
    "GITHUB_APP_ID": {
        "label": "GitHub App ID",
        "what": "A unique number that identifies your GitHub App.",
        "how": (
            "1. Go to github.com → Profile picture → Settings\n"
            "2. Scroll down → Developer settings → GitHub Apps\n"
            "3. Click your app name\n"
            "4. The App ID is shown at the top of the page (e.g. 123456)"
        ),
    },
    "GITHUB_INSTALLATION_ID": {
        "label": "GitHub Installation ID",
        "what": "A number that identifies where your GitHub App is installed (your account or org).",
        "how": (
            "1. Go to github.com → Profile picture → Settings\n"
            "2. Click Applications → Installed GitHub Apps\n"
            "3. Click Configure next to your app\n"
            "4. Look at the browser URL — the number at the end is your Installation ID\n"
            "   Example: github.com/settings/installations/12345678 → ID is 12345678"
        ),
    },
    "GITHUB_PRIVATE_KEY_PATH": {
        "label": "GitHub App Private Key (.pem file path)",
        "what": "A .pem file used to sign authentication tokens for your GitHub App.",
        "how": (
            "1. Go to github.com → Profile picture → Settings → Developer settings → GitHub Apps\n"
            "2. Click your app name\n"
            "3. Scroll down → click Generate a private key\n"
            "4. A .pem file will be downloaded to your computer\n"
            "5. Provide the full path to that file\n"
            "   Example: C:\\Users\\you\\Downloads\\my-app.2024-01-01.private-key.pem"
        ),
    },
    "GITHUB_REPO": {
        "label": "GitHub Repository",
        "what": "The GitHub repo to work with, in owner/repo format.",
        "how": (
            "Use your GitHub username (or org name) and the repo name.\n"
            "Example: john/my-project  or  my-org/backend-api"
        ),
    },
}

_REQUIRED_CREDS = list(_CRED_META.keys())


def _missing_creds() -> list[str]:
    return [k for k in _REQUIRED_CREDS if not _cfg(k)]


def _cred_prompt(key: str) -> str:
    m = _CRED_META[key]
    return (
        f"❌ I need your **{m['label']}** to continue.\n\n"
        f"**What it is:** {m['what']}\n\n"
        f"**How to find it:**\n{m['how']}\n\n"
        f"**Please provide your {m['label']} here and I will save it automatically.**"
    )


# ─── GITHUB APP AUTH ─────────────────────────────────────────────────────────

def _make_jwt() -> str:
    app_id = _cfg("GITHUB_APP_ID")
    key_path = _cfg("GITHUB_PRIVATE_KEY_PATH")
    if not app_id or not key_path:
        raise ValueError("Missing GITHUB_APP_ID or GITHUB_PRIVATE_KEY_PATH")
    private_key = Path(key_path).read_text(encoding="utf-8")
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": str(app_id)}
    return jwt.encode(payload, private_key, algorithm="RS256")


async def _get_token() -> str:
    installation_id = _cfg("GITHUB_INSTALLATION_ID")
    if not installation_id:
        raise ValueError("Missing GITHUB_INSTALLATION_ID")
    app_jwt = _make_jwt()
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers)
        resp.raise_for_status()
        return resp.json()["token"]


async def _gh(method: str, path: str, token: str, **kwargs) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        resp = await getattr(client, method)(f"{GITHUB_API}{path}", headers=headers, **kwargs)
        if resp.status_code == 204:
            return {}
        resp.raise_for_status()
        return resp.json()


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 40) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text[:max_len].strip("-")


def _branch_name(issue_number: int, title: str) -> str:
    return f"issue-{issue_number}-{_slugify(title)}"


def _fmt_issue(issue: dict) -> str:
    labels = ", ".join(lb["name"] for lb in issue.get("labels", []))
    body = (issue.get("body") or "No description provided.")[:300]
    return (
        f"🎯 Issue #{issue['number']}: {issue['title']}\n"
        f"   URL     : {issue['html_url']}\n"
        f"   Labels  : {labels or 'none'}\n"
        f"   Preview : {body}"
    )


def _search_local_logs(query: str) -> list[str]:
    patterns_raw = _cfg("LOCAL_LOG_PATTERNS") or ""
    patterns = [p.strip() for p in patterns_raw.split(",") if p.strip()]
    hits: list[str] = []
    for pattern in patterns:
        for filepath in glob.glob(pattern, recursive=True):
            try:
                for i, line in enumerate(Path(filepath).read_text(errors="ignore").splitlines(), 1):
                    if query.lower() in line.lower():
                        hits.append(f"📄 {filepath}:{i} → {line.strip()}")
                        if len(hits) >= 20:
                            return hits
            except Exception:
                continue
    return hits


async def _ensure_label(repo: str, token: str, name: str, color: str) -> None:
    try:
        await _gh("post", f"/repos/{repo}/labels", token, json={"name": name, "color": color})
    except Exception:
        pass  # label probably already exists


# ─── TOOLS ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def setup_credential(key: str, value: str) -> str:
    """
    Save a GitHub credential provided by the user.
    Call this tool when the user provides a credential value in the chat.

    Args:
        key:   Credential key — one of: GITHUB_APP_ID, GITHUB_INSTALLATION_ID,
               GITHUB_PRIVATE_KEY_PATH, GITHUB_REPO, LOCAL_LOG_PATTERNS
        value: The value provided by the user
    """
    if key not in _CRED_META and key != "LOCAL_LOG_PATTERNS":
        return (
            f"❌ Unknown key: {key}\n"
            f"Valid keys: {', '.join(list(_CRED_META.keys()) + ['LOCAL_LOG_PATTERNS'])}"
        )

    value = value.strip()

    if key == "GITHUB_PRIVATE_KEY_PATH":
        src = Path(value)
        if not src.exists():
            return (
                f"❌ File not found: {value}\n"
                f"Please check the path and try again. Use the full path, "
                f"e.g. C:\\Users\\you\\Downloads\\my-app.private-key.pem"
            )
        dest = Path(".") / src.name
        if src.resolve() != dest.resolve():
            shutil.copy(src, dest)
        _write_env(key, str(dest))
        return f"✅ Private key copied to `{dest}` and saved."

    _write_env(key, value)
    label = _CRED_META[key]["label"] if key in _CRED_META else key
    return f"✅ **{label}** saved successfully."


@mcp.tool()
async def get_next_mission() -> str:
    """
    Get your next mission from GitHub Issues.

    Fetches all open issues in the target repo, prioritises by labels
    (critical / high / urgent first, then medium, then others), and
    returns the single best next issue with its full context.
    """
    missing = _missing_creds()
    if missing:
        return _cred_prompt(missing[0])

    repo = _cfg("GITHUB_REPO")
    try:
        token = await _get_token()
        raw = await _gh("get", f"/repos/{repo}/issues", token, params={
            "state": "open",
            "sort": "created",
            "direction": "asc",
            "per_page": 100,
        })

        issues = [i for i in raw if "pull_request" not in i]

        if not issues:
            return "✅ No open issues found in the repo — you're all caught up!"

        def _priority(issue: dict) -> int:
            lnames = [lb["name"].lower() for lb in issue.get("labels", [])]
            if any(kw in ln for ln in lnames for kw in ("critical", "high", "urgent", "p0", "p1")):
                return 0
            if any(kw in ln for ln in lnames for kw in ("medium", "normal", "p2")):
                return 1
            return 2

        issues.sort(key=_priority)
        top = issues[0]
        return f"🚀 Your next mission:\n\n{_fmt_issue(top)}"

    except Exception as exc:
        return f"❌ Error fetching issues: {exc}"


@mcp.tool()
async def manage_environment(issue_number: int) -> str:
    """
    Prepare your work environment for a mission.
    Shows a permission prompt — then call confirm_manage_environment to execute.

    What this will do (after confirmation):
      • Create a branch  → issue-{number}-{title-slug}
      • Add label        → in-progress on the issue

    Args:
        issue_number: The GitHub issue number you want to start working on
    """
    missing = _missing_creds()
    if missing:
        return _cred_prompt(missing[0])

    repo = _cfg("GITHUB_REPO")
    try:
        token = await _get_token()
        issue = await _gh("get", f"/repos/{repo}/issues/{issue_number}", token)
        new_branch = _branch_name(issue_number, issue["title"])

        return (
            f"⚠️  **Permission required** — I am about to:\n"
            f"   🌿 Create branch : `{new_branch}`\n"
            f"   🏷️  Add label      : `in-progress` on issue #{issue_number}\n"
            f"   📌 Issue          : {issue['title']}\n\n"
            f"Reply **yes** to confirm, or **no** to cancel.\n"
            f"_(After confirming, call `confirm_manage_environment` with issue_number={issue_number})_"
        )
    except Exception as exc:
        return f"❌ Error: {exc}"


@mcp.tool()
async def confirm_manage_environment(issue_number: int) -> str:
    """
    Execute environment setup after the user confirms.
    Creates the branch and updates the issue label to in-progress.

    Args:
        issue_number: The GitHub issue number
    """
    missing = _missing_creds()
    if missing:
        return _cred_prompt(missing[0])

    repo = _cfg("GITHUB_REPO")
    try:
        token = await _get_token()

        issue     = await _gh("get", f"/repos/{repo}/issues/{issue_number}", token)
        repo_data = await _gh("get", f"/repos/{repo}", token)
        default   = repo_data["default_branch"]
        ref_data  = await _gh("get", f"/repos/{repo}/git/ref/heads/{default}", token)
        sha       = ref_data["object"]["sha"]

        new_branch = _branch_name(issue_number, issue["title"])

        # Create branch
        await _gh("post", f"/repos/{repo}/git/refs", token, json={
            "ref": f"refs/heads/{new_branch}",
            "sha": sha,
        })

        # Ensure label exists and apply it
        await _ensure_label(repo, token, "in-progress", "0075ca")
        await _gh("post", f"/repos/{repo}/issues/{issue_number}/labels", token,
                  json={"labels": ["in-progress"]})

        return (
            f"✅ Environment is ready!\n"
            f"   🌿 Branch created : `{new_branch}`\n"
            f"   🏷️  Label added    : `in-progress`\n"
            f"   🔗 Issue URL      : {issue['html_url']}\n\n"
            f"Switch to branch `{new_branch}` and start coding!"
        )
    except Exception as exc:
        return f"❌ Error setting up environment: {exc}"


@mcp.tool()
async def finish_mission(issue_number: int, branch: str) -> str:
    """
    Prepare to mark a mission as finished.
    Shows a permission prompt — then call confirm_finish_mission to execute.

    What this will do (after confirmation):
      • Remove label in-progress from the issue
      • Add label in-review on the issue
      • Open a Pull Request from your branch to the default branch

    Args:
        issue_number: The GitHub issue number
        branch:       Your working branch name (e.g. issue-42-fix-login)
    """
    missing = _missing_creds()
    if missing:
        return _cred_prompt(missing[0])

    repo = _cfg("GITHUB_REPO")
    try:
        token     = await _get_token()
        issue     = await _gh("get", f"/repos/{repo}/issues/{issue_number}", token)
        repo_data = await _gh("get", f"/repos/{repo}", token)
        default   = repo_data["default_branch"]

        return (
            f"⚠️  **Permission required** — I am about to:\n"
            f"   🏷️  Update label : `in-progress` → `in-review` on issue #{issue_number}\n"
            f"   🔀 Open PR      : `{branch}` → `{default}`\n"
            f"   📌 Issue        : {issue['title']}\n\n"
            f"Reply **yes** to confirm, or **no** to cancel.\n"
            f"_(After confirming, call `confirm_finish_mission` with issue_number={issue_number} and branch={branch})_"
        )
    except Exception as exc:
        return f"❌ Error: {exc}"


@mcp.tool()
async def confirm_finish_mission(issue_number: int, branch: str) -> str:
    """
    Execute the mission finish after the user confirms.
    Updates issue label to in-review and opens a pull request.

    Args:
        issue_number: The GitHub issue number
        branch:       Your working branch name
    """
    missing = _missing_creds()
    if missing:
        return _cred_prompt(missing[0])

    repo = _cfg("GITHUB_REPO")
    try:
        token     = await _get_token()
        issue     = await _gh("get", f"/repos/{repo}/issues/{issue_number}", token)
        repo_data = await _gh("get", f"/repos/{repo}", token)
        default   = repo_data["default_branch"]

        # Remove in-progress label (best effort)
        try:
            await _gh("delete", f"/repos/{repo}/issues/{issue_number}/labels/in-progress", token)
        except Exception:
            pass

        # Add in-review label
        await _ensure_label(repo, token, "in-review", "e4e669")
        await _gh("post", f"/repos/{repo}/issues/{issue_number}/labels", token,
                  json={"labels": ["in-review"]})

        # Open PR
        pr = await _gh("post", f"/repos/{repo}/pulls", token, json={
            "title": f"Fix #{issue_number}: {issue['title']}",
            "head":  branch,
            "base":  default,
            "body":  f"Closes #{issue_number}\n\n{issue.get('body') or ''}",
        })

        return (
            f"✅ Mission complete!\n"
            f"   🏷️  Label updated : `in-review`\n"
            f"   🔀 PR opened     : {pr['html_url']}\n"
            f"   📌 PR title      : {pr['title']}"
        )
    except Exception as exc:
        return f"❌ Error finishing mission: {exc}"


@mcp.tool()
async def search_mission_context(query: str) -> str:
    """
    Search for context related to a mission query across multiple sources:
      • GitHub Issues and Pull Requests
      • GitHub Code
      • GitHub Commits
      • Local log files (if LOCAL_LOG_PATTERNS is set in .env)

    Args:
        query: Keywords or phrase to search for
    """
    missing = _missing_creds()
    if missing:
        return _cred_prompt(missing[0])

    repo = _cfg("GITHUB_REPO")
    parts: list[str] = []

    try:
        token = await _get_token()

        # Issues & PRs
        res = await _gh("get", "/search/issues", token,
                        params={"q": f"{query} repo:{repo}", "per_page": 5})
        if res.get("items"):
            parts.append("📋 **GitHub Issues & PRs:**")
            for item in res["items"]:
                kind = "PR" if "pull_request" in item else "Issue"
                parts.append(f"   [{kind} #{item['number']}] {item['title']}\n   {item['html_url']}")

        # Code
        res = await _gh("get", "/search/code", token,
                        params={"q": f"{query} repo:{repo}", "per_page": 5})
        if res.get("items"):
            parts.append("\n💻 **GitHub Code:**")
            for item in res["items"]:
                parts.append(f"   📄 {item['path']}\n   {item['html_url']}")

        # Commits
        res = await _gh("get", "/search/commits", token,
                        params={"q": f"{query} repo:{repo}", "per_page": 5})
        if res.get("items"):
            parts.append("\n📝 **GitHub Commits:**")
            for item in res["items"]:
                msg = item["commit"]["message"].splitlines()[0][:80]
                parts.append(f"   {msg}\n   {item['html_url']}")

    except Exception as exc:
        parts.append(f"⚠️ GitHub search error: {exc}")

    # Local logs
    hits = _search_local_logs(query)
    if hits:
        parts.append("\n📂 **Local Logs:**")
        parts.extend(f"   {h}" for h in hits)
    elif _cfg("LOCAL_LOG_PATTERNS"):
        parts.append("\n📂 **Local Logs:** No matches found.")
    else:
        parts.append(
            "\n📂 **Local Logs:** Not configured.\n"
            "   To enable: provide LOCAL_LOG_PATTERNS via setup_credential\n"
            "   Example value: ./logs/**/*.log,./debug/*.txt"
        )

    return "\n".join(parts) if parts else f"No results found for: `{query}`"


@mcp.tool()
async def find_similar_bug_or_code(query: str) -> str:
    """
    Find similar bugs, issues, or code patterns to help you understand context
    and avoid duplicating work.

    Searches:
      • Closed bug issues (how was it fixed before?)
      • Open similar issues (is someone already working on it?)
      • Similar code patterns in the repo
      • Merged PRs with similar changes

    Args:
        query: Description of the bug, feature, or code pattern to search for
    """
    missing = _missing_creds()
    if missing:
        return _cred_prompt(missing[0])

    repo = _cfg("GITHUB_REPO")
    parts: list[str] = []

    try:
        token = await _get_token()

        # Closed bugs
        res = await _gh("get", "/search/issues", token, params={
            "q": f"{query} repo:{repo} is:issue is:closed label:bug",
            "per_page": 5,
            "sort": "updated",
        })
        if res.get("items"):
            parts.append("🐛 **Similar Closed Bugs (already fixed):**")
            for item in res["items"]:
                parts.append(f"   [#{item['number']}] {item['title']}\n   {item['html_url']}")

        # Open issues
        res = await _gh("get", "/search/issues", token, params={
            "q": f"{query} repo:{repo} is:issue is:open",
            "per_page": 5,
        })
        if res.get("items"):
            parts.append("\n🔴 **Open Similar Issues:**")
            for item in res["items"]:
                parts.append(f"   [#{item['number']}] {item['title']}\n   {item['html_url']}")

        # Similar code
        res = await _gh("get", "/search/code", token,
                        params={"q": f"{query} repo:{repo}", "per_page": 5})
        if res.get("items"):
            parts.append("\n💻 **Similar Code in Repo:**")
            for item in res["items"]:
                parts.append(f"   📄 {item['path']}\n   {item['html_url']}")

        # Merged PRs (prior fixes)
        res = await _gh("get", "/search/issues", token, params={
            "q": f"{query} repo:{repo} is:pr is:merged",
            "per_page": 3,
            "sort": "updated",
        })
        if res.get("items"):
            parts.append("\n✅ **Similar Merged PRs (how it was solved before):**")
            for item in res["items"]:
                parts.append(f"   [PR #{item['number']}] {item['title']}\n   {item['html_url']}")

    except Exception as exc:
        parts.append(f"⚠️ Search error: {exc}")

    return "\n".join(parts) if parts else f"No similar results found for: `{query}`"


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
