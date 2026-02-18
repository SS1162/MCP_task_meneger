# GitHub Engineer MCP

A local MCP server that acts as an AI-powered software engineer assistant. It connects to GitHub via a GitHub App and gives coding agents a full mission workflow — from picking the next task to opening a pull request.

---

## Tools

---

### `get_next_mission`
Fetches the highest-priority open issue from your GitHub repo.

**Input:** none

**Example call:**
```
get_next_mission()
```

**Example response:**
```
🚀 Your next mission:

🎯 Issue #42: Fix login bug
   URL     : https://github.com/owner/repo/issues/42
   Labels  : bug, high
   Preview : Users cannot log in after the latest deploy.
```

---

### `manage_environment`
Shows a permission prompt before creating a branch and labeling the issue `in-progress`. Does nothing until you confirm.

**Input:**
- `issue_number` — the GitHub issue number (e.g. `42`)

**Example call:**
```
manage_environment(issue_number=42)
```

**Example response:**
```
⚠️ Permission required — I am about to:
   🌿 Create branch : issue-42-fix-login-bug
   🏷️  Add label     : in-progress on issue #42
   📌 Issue         : Fix login bug

Reply yes to confirm, or no to cancel.
(After confirming, call confirm_manage_environment with issue_number=42)
```

---

### `confirm_manage_environment`
Executes the environment setup after the user confirms. Creates the branch and adds the `in-progress` label.

**Input:**
- `issue_number` — the GitHub issue number (e.g. `42`)

**Example call:**
```
confirm_manage_environment(issue_number=42)
```

**Example response:**
```
✅ Environment is ready!
   🌿 Branch created : issue-42-fix-login-bug
   🏷️  Label added    : in-progress
   🔗 Issue URL      : https://github.com/owner/repo/issues/42

Switch to branch issue-42-fix-login-bug and start coding!
```

---

### `finish_mission`
Shows a permission prompt before updating the issue label and opening a PR. Does nothing until you confirm.

**Input:**
- `issue_number` — the GitHub issue number (e.g. `42`)
- `branch` — your working branch name (e.g. `"issue-42-fix-login-bug"`)

**Example call:**
```
finish_mission(issue_number=42, branch="issue-42-fix-login-bug")
```

**Example response:**
```
⚠️ Permission required — I am about to:
   🏷️  Update label : in-progress → in-review on issue #42
   🔀 Open PR      : issue-42-fix-login-bug → main
   📌 Issue        : Fix login bug

Reply yes to confirm, or no to cancel.
(After confirming, call confirm_finish_mission with issue_number=42 and branch=issue-42-fix-login-bug)
```

---

### `confirm_finish_mission`
Executes the mission finish after the user confirms. Removes `in-progress`, adds `in-review`, and opens a PR.

**Input:**
- `issue_number` — the GitHub issue number (e.g. `42`)
- `branch` — your working branch name (e.g. `"issue-42-fix-login-bug"`)

**Example call:**
```
confirm_finish_mission(issue_number=42, branch="issue-42-fix-login-bug")
```

**Example response:**
```
✅ Mission complete!
   🏷️  Label updated : in-review
   🔀 PR opened     : https://github.com/owner/repo/pull/10
   📌 PR title      : Fix #42: Fix login bug
```

---

### `search_mission_context`
Searches GitHub issues, PRs, commits, code, and local log files for context related to your task.

**Input:**
- `query` — keywords or phrase to search for (e.g. `"login bug"`)

**Example call:**
```
search_mission_context(query="login bug")
```

**Example response:**
```
📋 GitHub Issues & PRs:
   [Issue #42] Fix login bug
   https://github.com/owner/repo/issues/42

💻 GitHub Code:
   📄 src/auth/login.py
   https://github.com/owner/repo/blob/main/src/auth/login.py

📝 GitHub Commits:
   Fix null pointer in login handler
   https://github.com/owner/repo/commit/abc123

📂 Local Logs:
   📄 ./logs/app.log:14 → ERROR: login failed for user admin
```

---

### `find_similar_bug_or_code`
Finds closed bugs, open issues, similar code patterns, and merged PRs related to your query.

**Input:**
- `query` — description of the bug, feature, or code pattern (e.g. `"login authentication failure"`)

**Example call:**
```
find_similar_bug_or_code(query="login authentication failure")
```

**Example response:**
```
🐛 Similar Closed Bugs (already fixed):
   [#31] Fix session token expiry on login
   https://github.com/owner/repo/issues/31

🔴 Open Similar Issues:
   [#39] Login fails on mobile
   https://github.com/owner/repo/issues/39

💻 Similar Code in Repo:
   📄 src/auth/session.py
   https://github.com/owner/repo/blob/main/src/auth/session.py

✅ Similar Merged PRs (how it was solved before):
   [PR #33] Fix login redirect loop
   https://github.com/owner/repo/pull/33
```

---

### `setup_credential`
Saves a GitHub credential you provide directly to the `.env` file. The server calls this automatically when a credential is missing.

**Input:**
- `key` — one of: `GITHUB_APP_ID`, `GITHUB_INSTALLATION_ID`, `GITHUB_PRIVATE_KEY_PATH`, `GITHUB_REPO`, `LOCAL_LOG_PATTERNS`
- `value` — the value to save

**Example call:**
```
setup_credential(key="GITHUB_APP_ID", value="123456")
```

**Example response:**
```
✅ GitHub App ID saved successfully.
```

---

## Setup

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Create a GitHub App
1. Go to **github.com → Profile → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Set any name and `http://localhost` as the homepage URL
3. Disable webhooks
4. Under **Repository permissions** set **Read & Write** for:
   - `Issues`
   - `Pull requests`
   - `Contents`
   - `Metadata` → Read-only
5. Click **Create GitHub App**
6. Note your **App ID** at the top of the app page
7. Scroll down → click **Generate a private key** → save the `.pem` file
8. Click **Install App** → install on your repo → note the **Installation ID** from the URL

### 3. Configure credentials
You do **not** need to create any files manually. When you first call any tool, the server will detect missing credentials and ask you to provide each value. It will save everything to `.env` automatically.

Required credentials:

| Key | Description |
|---|---|
| `GITHUB_APP_ID` | Your GitHub App's numeric ID |
| `GITHUB_INSTALLATION_ID` | The installation ID from the URL after installing the app |
| `GITHUB_PRIVATE_KEY_PATH` | Full path to your `.pem` private key file |
| `GITHUB_REPO` | Target repo in `owner/repo` format |
| `LOCAL_LOG_PATTERNS` | *(Optional)* Comma-separated glob patterns, e.g. `./logs/**/*.log` |

### 4. Run the server
```
python github_engineer.py
```

---

## Usage with VS Code

The `.vscode/mcp.json` file is already configured. VS Code will automatically detect and connect to this MCP server when you open the project.

---

## Testing with MCP Inspector

```
npx @modelcontextprotocol/inspector python github_engineer.py
```

Then open the URL shown in the terminal to visually test all tools.

---

## Example Workflow

### Step 1 — Get your next mission
Call `get_next_mission` with no arguments.

What it does:
- Fetches all open issues from your GitHub repo
- Sorts them by priority (`critical`, `high`, `urgent` labels come first)
- Skips pull requests
- Returns the single best next issue with title, number, URL, labels, and description

Example response:
```
🚀 Your next mission:

🎯 Issue #42: Fix login bug
   URL     : https://github.com/owner/repo/issues/42
   Labels  : bug, high
   Preview : Users cannot log in after the latest deploy.
```

---

### Step 2 — Set up your work environment
Call `manage_environment` with the issue number (e.g. `42`).

What it does:
- Fetches the issue title from GitHub
- Shows you a permission prompt with exactly what will happen — **without doing anything yet**
- Waits for your confirmation

Example response:
```
⚠️ Permission required — I am about to:
   🌿 Create branch : issue-42-fix-login-bug
   🏷️  Add label     : in-progress on issue #42
   📌 Issue         : Fix login bug

Reply yes to confirm, or no to cancel.
```

After you confirm, call `confirm_manage_environment` with the same issue number.

What it then does:
- Creates a new branch named `issue-{number}-{title-slug}` from your default branch (`main`)
- Adds the label `in-progress` to the issue on GitHub

Example response:
```
✅ Environment is ready!
   🌿 Branch created : issue-42-fix-login-bug
   🏷️  Label added    : in-progress
   🔗 Issue URL      : https://github.com/owner/repo/issues/42

Switch to branch issue-42-fix-login-bug and start coding!
```

---

### Step 3 — Write your code
Switch to the new branch locally and make your changes:
```
git checkout issue-42-fix-login-bug
```

---

### Step 4 — Search for context while working
Call `search_mission_context` with keywords related to your task (e.g. `"login bug"`).

What it does:
- Searches GitHub Issues and Pull Requests matching the query
- Searches GitHub code in the repo matching the query
- Searches GitHub commit messages matching the query
- Searches local log files if `LOCAL_LOG_PATTERNS` is configured

Example response:
```
📋 GitHub Issues & PRs:
   [Issue #42] Fix login bug
   https://github.com/owner/repo/issues/42

💻 GitHub Code:
   📄 src/auth/login.py
   https://github.com/owner/repo/blob/main/src/auth/login.py

📝 GitHub Commits:
   Fix null pointer in login handler
   https://github.com/owner/repo/commit/abc123

📂 Local Logs:
   📄 ./logs/app.log:14 → ERROR: login failed for user admin
```

---

### Step 5 — Find similar bugs or code
Call `find_similar_bug_or_code` with a description of the problem (e.g. `"login authentication failure"`).

What it does:
- Searches closed bug issues — how was this type of problem fixed before?
- Searches open similar issues — is someone already working on something related?
- Searches similar code patterns in the repo
- Searches merged PRs — what changes were made in the past for similar problems?

Example response:
```
🐛 Similar Closed Bugs (already fixed):
   [#31] Fix session token expiry on login
   https://github.com/owner/repo/issues/31

🔴 Open Similar Issues:
   [#39] Login fails on mobile
   https://github.com/owner/repo/issues/39

💻 Similar Code in Repo:
   📄 src/auth/session.py
   https://github.com/owner/repo/blob/main/src/auth/session.py

✅ Similar Merged PRs (how it was solved before):
   [PR #33] Fix login redirect loop
   https://github.com/owner/repo/pull/33
```

---

### Step 6 — Finish your mission and open a PR
Call `finish_mission` with the issue number and your branch name (e.g. `42`, `"issue-42-fix-login-bug"`).

What it does:
- Shows you a permission prompt with exactly what will happen — **without doing anything yet**
- Waits for your confirmation

Example response:
```
⚠️ Permission required — I am about to:
   🏷️  Update label : in-progress → in-review on issue #42
   🔀 Open PR      : issue-42-fix-login-bug → main
   📌 Issue        : Fix login bug

Reply yes to confirm, or no to cancel.
```

After you confirm, call `confirm_finish_mission` with the same issue number and branch.

What it then does:
- Removes the `in-progress` label from the issue
- Adds the label `in-review` to the issue on GitHub
- Opens a Pull Request from your branch to `main`
- Sets the PR title and body automatically, linking it to the issue

Example response:
```
✅ Mission complete!
   🏷️  Label updated : in-review
   🔀 PR opened     : https://github.com/owner/repo/pull/10
   📌 PR title      : Fix #42: Fix login bug
```
