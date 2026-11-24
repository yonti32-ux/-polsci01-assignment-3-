# Gmail and Calendar with Antigravity CLI

A student can use natural-language requests in Antigravity CLI to read class email, prepare a draft, check availability, and add a personal calendar event. The CLI launches a local Python FastMCP server over standard input and output. Google authorizes the student account separately in a browser.

| Gmail | Google Calendar |
| --- | --- |
| `search_emails` finds message IDs, subjects, senders, and snippets. | `list_events` reads events from the primary calendar. |
| `read_email` opens a message by ID. | `find_free_slots` returns gaps that fit a requested duration. |
| `create_draft` saves a message for review in Gmail. | `create_event` adds an event to the primary calendar without guests. |

## Run on Windows

You need PowerShell, Git, uv, Antigravity CLI (`agy`), and a Google account authorized to test your OAuth app. Enable the Gmail and Google Calendar APIs in the Google Cloud project. Download its **Desktop app** OAuth client JSON and place it in a private directory outside the checkout. Exactly one filename in that directory should match `client_secret*.json`.

### 1. Install and authorize

```powershell
git clone https://github.com/yonti32-ux/-polsci01-assignment-3-.git assignment-3
cd assignment-3
uv sync --locked
$env:GOOGLE_PRIVATE_DIR = Read-Host 'Full path of your private OAuth directory'
$env:CLASS_EMAIL = Read-Host 'Google email address for this project'
uv run auth --expected-email $env:CLASS_EMAIL
```

Choose that account in the browser. A successful profile check saves `token.json` in the private directory. If you deliberately want to replace an existing token, rerun the authorization command with `--overwrite`.

### 2. Connect Antigravity CLI

From the same PowerShell session in the project root, run the following once for a fresh checkout. It creates a machine-local configuration containing the Python executable path, the private directory path, and the expected email address. If you already have a project MCP configuration, merge the `gmail-calendar` entry into it.

```powershell
$python = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$config = @{ mcpServers = @{ 'gmail-calendar' = @{
    command = $python
    args = @('-m', 'gmail_calendar.server')
    env = @{
        GOOGLE_PRIVATE_DIR = $env:GOOGLE_PRIVATE_DIR
        CLASS_EMAIL = $env:CLASS_EMAIL
    }
} } }
New-Item -ItemType Directory -Force .agents | Out-Null
$path = Join-Path $PWD '.agents\mcp_config.json'
if (Test-Path $path) { throw 'MCP config exists. Merge the server entry manually.' }
[IO.File]::WriteAllText($path, ($config | ConvertTo-Json -Depth 6))
agy
```

Inside Antigravity, enter `/mcp` and check that `gmail-calendar` is connected. For subsequent sessions, open the project directory and run `agy`.

### 3. Verify one read and one write

1. Ask **“Use gmail-calendar/list_events to list my primary calendar events for tomorrow in Israel time.”** Expand the tool call in the CLI. A successful empty list is a valid result.
2. Ask **“Use gmail-calendar/create_draft to write one draft addressed to my class account with subject ‘CLI draft test’ and body ‘Draft created from Antigravity.’”** Check the returned draft ID and open Gmail → Drafts to verify it. The account owner controls sending.

## Run the tests

```powershell
uv run python -m pytest -v
```

The suite uses mocked Google responses and temporary credentials. It also exercises the MCP handshake and tool discovery in a subprocess. Browser consent and a live CLI tool call are separate integration checks. For supported inputs, acceptance criteria, and the recorded live verification, see [the retrospective PRD](PRD.md).
