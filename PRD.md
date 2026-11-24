# Product requirements · Gmail and Calendar CLI assistant

**Document status:** Retrospective. Written after implementation, using the Python source, test cases, and observed Antigravity CLI session. Requirements below describe the delivered assignment.

## User and outcome

A student working in a terminal needs to find a class email, prepare a response for review, and reserve time on their calendar. The user chooses a dedicated Google account during setup. Antigravity discovers six named tools and invokes them on that account. A reviewer can verify each operation by inspecting the tool call and comparing its result with Gmail or Calendar.

## Functional requirements and acceptance criteria

| Tool | Inputs and behavior | Observable acceptance criterion |
| --- | --- | --- |
| `search_emails` | Accept a Gmail query and a result limit. Default to 10 and clamp the limit to 1–50. | Each match includes its ID, sender, subject, and snippet. An empty search yields an empty list. |
| `read_email` | Accept a message ID obtained from search. Decode the message body, including supported multipart messages. | A known multipart test message returns its headers and readable plain text. |
| `create_draft` | Accept recipient, subject, and body, plus optional CC and BCC. Save a draft for human review. | Gmail returns a draft ID and the user can find the draft in the account. Sending remains a manual action. |
| `list_events` | Accept start and end times. Query the primary calendar in start-time order, with a default limit of 50 and a bound of 1–250. | Timed results include local start and end times. All-day results retain their dates. A reversed or empty time window raises an error. |
| `find_free_slots` | Query primary-calendar free/busy data. Merge overlapping busy intervals and return gaps within the window that fit a positive duration (default 30 minutes). | A gap equal to the requested duration qualifies. A shorter gap is excluded. |
| `create_event` | Accept a nonblank title, start, end, and optional description. Create on the primary calendar with no attendees. | A successful insert returns the ID and event times. An empty title or an end at or before the start raises an error. |

## Account access and operating constraints

- Browser authorization runs separately from the server. The selected Gmail profile must match the expected address before the authorization command saves a new token. Replacing an existing token requires an explicit overwrite.
- Keep the Desktop OAuth JSON and saved token in the directory named by `GOOGLE_PRIVATE_DIR`. The CLI setup supplies `CLASS_EMAIL` for account verification during credential loading.
- The server requests four Google OAuth scopes ending in `gmail.readonly`, `gmail.compose`, `calendar.events`, and `calendar.freebusy`. The exposed operations are narrower than those grants. Mail sending, deletion, guest invitations, and arbitrary Google API calls are outside the product scope.
- Use ISO date/time inputs. Interpret timezone-free values in `Asia/Jerusalem` and convert offset-aware values to that zone. Use timezone database rules for seasonal offsets.
- Use stdio for MCP messages and stderr for server diagnostics. Missing credentials must produce actionable authorization instructions. A successful connection alone verifies discovery, while an actual tool call verifies access to Google.

## Verification record

| Evidence | What it establishes |
| --- | --- |
| `tests/test_config.py` and `tests/test_auth.py` | Private directory discovery, account and scope checks, and token overwrite protection. |
| `tests/test_gmail.py`, `tests/test_calendar.py`, and `tests/test_timezone.py` | Mocked API behavior for the six operations, date conversion, and free-interval calculations. |
| `tests/test_server_stdio.py` | Test cases for six-tool discovery, missing-token diagnostics, and subprocess initialization over stdio. |
| Live Antigravity CLI demonstration, 24 November 2026 | The CLI reported a call to `gmail-calendar/list_events` and returned a confirmed test event for 25 November, 18:00–18:15 in Israel time. This verifies a live Calendar read. The result alone does not establish which client created the event. |

## Manual acceptance scenario

Search for a known class message, read it by ID, and create a draft reply for review. Then find a free 15-minute window, create one personal test event there, and list the same window to verify its title and time. Draft IDs and event IDs are evidence for the tester to inspect locally. The repository does not need mailbox contents or account credentials as fixtures.
