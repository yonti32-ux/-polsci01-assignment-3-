# Product requirements - Gmail and Google Calendar via MCP

**Document status:** Retrospective specification of the existing implementation. This document describes the product's purpose, supported operations, and acceptance criteria using the repository source and tests. Live operation on the configured laptop is reported by the project owner.

## User and outcome

A student using Antigravity CLI needs to operate Gmail and Google Calendar on a dedicated coursework account through natural-language requests. The core exercise is to create an unsent Gmail draft and a personal calendar event four hours from the request, then verify both in Google.

L05 establishes the direct Google API connection and the draft-plus-event exercise. L06 exposes those operations as MCP tools so the model can select and combine them without writing a new script for each request. This project implements that local MCP server and its Google authorization flow. It does not train or host a language model.

Success means the CLI discovers the six tools, invokes the required operations on the intended account, and produces results that the user can verify in Gmail and Calendar.

## Product scope and interaction

1. The account owner configures Google API access and authorizes the dedicated account separately in a browser.
2. Antigravity launches the Python FastMCP server locally over stdio and discovers its tools.
3. The user requests an operation in natural language. The model in the host chooses tools and supplies their structured arguments.
4. The server calls the Google APIs with the saved credentials and returns results to the host.
5. The user checks drafts and calendar entries in Google. Email sending is a manual action.

Additional supported requests include finding an email, reading it, preparing a draft reply, listing events, and finding a free interval before creating an event. A background email monitor, scheduled execution, and automatic handling of all meeting invitations are outside the implemented scope.

## Functional requirements and acceptance criteria

| Tool | Inputs and behavior | Observable acceptance criterion |
| --- | --- | --- |
| `search_emails` | `query=""`, `max_results=10`. Search Gmail; clamp the result limit to 1-50. | Each match includes its ID, sender, subject, and snippet. An empty search yields an empty list. |
| `read_email` | `message_id`. Decode a message body, preferring plain text where supported; return headers and thread ID as well. | A known multipart test message returns its headers and readable plain text. |
| `create_draft` | `to`, `subject`, `body`, optional `cc` and `bcc`. Save a draft for human review. | Gmail returns a draft ID and the user can find the unsent draft in the account. |
| `list_events` | `start_time`, `end_time`, `max_results=50`. Query the primary calendar in start-time order; clamp the limit to 1-250. | Timed results include local start and end times. All-day results retain their dates. A reversed or empty time window raises an error. |
| `find_free_slots` | `start_time`, `end_time`, `duration_minutes=30`. Query primary-calendar free/busy data and merge overlapping or adjacent busy intervals. | Return free intervals long enough for the requested positive duration, with discrete slot options. A gap equal to that duration qualifies; a shorter gap is excluded. |
| `create_event` | `title`, `start_time`, `end_time`, optional `description`. Create on the primary calendar with no attendees. | A successful insert returns the event ID and times. An empty title or an end at or before the start raises an error. |

The calendar interfaces use explicit time windows. The lecture's `list_events(days_ahead)` and `find_free_slots(date, duration_minutes)` examples describe the same user needs with different arguments; the host must use the schemas advertised by this server.

`create_event` does not check availability or reject overlapping events. Requests that require a free slot must call `find_free_slots` first. All six tools run on demand when invoked by the host.

## Account access and operating constraints

- Browser authorization runs separately from the server, using `uv run auth --expected-email <address>`. The selected Gmail profile must match the expected address before a new token is saved. Replacing an existing token requires `--overwrite`.
- Keep the Desktop OAuth client JSON and saved token in the directory named by `GOOGLE_PRIVATE_DIR`, outside the checkout. Client discovery requires exactly one file matching `client_secret*.json`; the token filename is `token.json`.
- The documented CLI setup supplies `CLASS_EMAIL` for account verification during credential loading. In the code, that runtime check is conditional on an expected address being supplied; following the setup keeps it enabled.
- The configured scopes are `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.compose`, `https://www.googleapis.com/auth/calendar.events`, and `https://www.googleapis.com/auth/calendar.freebusy`. Credential loading checks that the saved token contains them. Reusing L05 credentials may require authorization again.
- The exposed operations are narrower than those OAuth grants. There is no send, forward, delete, guest-invitation, or generic Google API tool. The omitted sending tool preserves the course's human review step: the server prepares a draft and the owner decides whether to send it. This restriction applies to this server's tools; it does not disable shell access or other tools available to the host.
- Use ISO date/time inputs. Interpret timezone-free values in `Asia/Jerusalem` and convert offset-aware values to that zone using the timezone database. The host resolves relative phrases such as "tomorrow" or "four hours from now" before calling a tool.
- Use stdio for MCP messages and stderr for server diagnostics. Missing credentials must produce actionable authorization instructions. A successful connection alone verifies discovery, while an actual tool call verifies access to Google.
- Use Python 3.12 or later and dependencies managed by uv. The documented Windows configuration starts the installed package with `.venv\Scripts\python.exe -m gmail_calendar.server` and stores machine-specific client settings in the ignored `.agents/mcp_config.json` file.

## Verification and current status

The project owner confirms that the integration was tested successfully during the L06 class on **24 November 2026**, on the laptop configured with the dedicated coursework Google account. Screenshots of that live run are not included in this checkout.

| Live verification | Recorded result |
| --- | --- |
| Antigravity CLI demonstration, 24 November 2026 | The CLI reported a call to `gmail-calendar/list_events` and returned a confirmed test event for 25 November, 18:00-18:15 in Israel time. This verifies a live Calendar read; the returned event alone does not establish which client created it. |

| Existing test files | What they cover |
| --- | --- |
| `tests/test_config.py` and `tests/test_auth.py` | Private directory discovery, account and scope checks, and token overwrite protection. |
| `tests/test_gmail.py`, `tests/test_calendar.py`, and `tests/test_timezone.py` | Mocked API behavior for the six operations, date conversion, and free-interval calculations. |
| `tests/test_server_stdio.py` | Test cases for six-tool discovery, missing-token diagnostics, and subprocess initialization over stdio. |

Run the suite with `uv run python -m pytest -v`. These tests use temporary credentials and mocked responses; they do not perform browser consent or verify live writes to Google. The table describes the checks implemented in the test files. A test-run result should be recorded separately when the suite is executed.

## Manual acceptance scenario

### Core exercise: a draft and an event through MCP

1. On the configured laptop, open Antigravity in the project root and check `/mcp`: `gmail-calendar` is connected and advertises six tools.
2. Ask the agent to use only those MCP tools to create an unsent draft to the coursework account with subject `L06 test`, plus a 30-minute personal event titled `MCP works` starting four hours from the request in Israel time. The duration is an explicit choice for this acceptance scenario.
3. Inspect the `create_draft` and `create_event` calls. The host must invoke the tools rather than generate a separate script for the task.
4. Verify the unsent draft in Gmail > Drafts and the event's title, start, and end in Google Calendar. A successful CLI summary alone is not the final check.

### Additional tool checks

Search for a known coursework message, read it by ID, and prepare a draft reply for review. Find a free 15-minute window, create a personal test event there, and list the same window to check the result. To check the tool boundary, ask the host to use only this server's tools to send a draft or delete an event; it should explain that no such tool exists, without executing a substitute script.

For a reviewable live demonstration, retain redacted screenshots of the server connection, the request and tool calls, and the visible result in Google. Draft and event IDs may be inspected locally. The repository does not need mailbox contents or account credentials as fixtures.
