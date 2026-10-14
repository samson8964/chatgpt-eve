# EVE V4 two-hour contract research summaries to in-game Mail

**Status:** V4 shadow scanner retains formal production alert protection:
`mail_enabled=false` in the scan manifest. V3 workers stay retired.
Two separate, optional research-only channels are available after a
**completed** local run:

- Gmail SMTP: `v4.research_mail`, previously configured by the user and
  confirmed to have delivered a real SMTP test.
- EVE Online game mail: `v4.game_mail_review`, new opt-in channel to
  `MikeChong` (2124493042), from existing Cloudflare mail sender
  `LadyGuaGua` (2124679425).

The user's manual game-mail test received ID **403312040** and the user
subsequently confirmed seeing the message in MikeChong's in-game mailbox.
That proves transport and identity for a test. It does not prove that the
scheduled scanner has sent an opportunity digest.

## Activate only after the user opts in

From an ordinary PowerShell window logged in as the SAME Windows user who
runs the `EVE-V4-Shadow` scheduled task:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
& .\.venv\Scripts\python.exe -m v4.game_mail_review --enable --recipient MikeChong
if ($LASTEXITCODE -ne 0) { throw 'Game mail configuration failed' }
& .\.venv\Scripts\python.exe -m v4.game_mail_review --status
```

This writes only the opt-in identity to
`EVE-V4-Data/config/eve_game_mail_review.json`. No API key or token is saved
there; the existing Windows Credential Manager key is used only when
sending. No message is sent during enable or status.

The current Windows task already runs `v4.local_service.main` every two
hours. After each new complete run, it calls both independent research mail
channels. A one-off immediate scan may be started from PowerShell:

```powershell
$task = Get-ScheduledTask -TaskName 'EVE-V4-Shadow'
if ($task.State -ne 'Running') { Start-ScheduledTask -TaskName 'EVE-V4-Shadow' }
```

The new game-mail code only publishes Jita 4-4 buy-depth model outputs and
rejects old same-location price snapshots. It includes contract ID,
snapshot profitability, ROI, bid-removal stress test and location as
**non-actionable research**, subject to source completeness checks.

After a run finishes, inspect:

```powershell
Get-Content (Join-Path $HOME 'EVE-V4-Data/logs/shadow-task.log') -Tail 35
```

Expected lines include `GAME_REVIEW_MAIL {"status": "V4_GAME_RESEARCH_MAIL_SENT", ...,
"mail_id": <real-id>}`. The user's in-game mailbox should show that
specific message. If a message is not sent, a sanitized
`GAME_REVIEW_MAIL_FAILED <exception type>` line is logged and Windows
Task Scheduler exits 3 instead of falsely reporting full success.
A Gmail send failure cannot block game mail, and vice versa.

To send a digest immediately from an *existing, newly priced, completed*
run without starting another full scan:

```powershell
& .\.venv\Scripts\python.exe -m v4.game_mail_review --send-now
```

Do **not** call this until a newly completed scan has been recorded under
the accepted Jita 4-4 contract valuation. The `make_review` validator
rejects old pricing and refuses to invent trade opportunities.

Each run is de-duplicated by its private receipt under
`EVE-V4-Data/mail-review/eve-receipts/<run>.json`, plus a deterministic
Cloudflare Worker idempotency key. A duplicate Worker ACK is not described
as a new send; its prior-accepted state is recorded.

## Disable without disturbing scanning or Gmail

```powershell
& .\.venv\Scripts\python.exe -m v4.game_mail_review --disable
```

This does not modify the original Windows scheduled task, scan schedule,
EVE OAuth grants, Gmail configuration, or any V3 job.

## Present limitations and next changes

1. Only public item-exchange contracts in currently monitored locations
   are studied; private-only, inaccessible and non-cash barter contracts
   are not falsely reported as scanned.
2. Blueprints without verified instance type, live contract status, live
   buy depth, actual transport/ACL safety remain review-only; no production
   trade notification is enabled by this integration.
3. Game-mail summary currently reports **contract evidence**, not market
   pair opportunities. Market execution proofs require independent live
   verification before being promoted.
4. Zero-candidate or incomplete-source periods still produce an honest
   review digest if opted in, enabling the user to audit progress rather
   than assuming the scanner is dead.
5. Gmail and in-game research channels are independently optional and
   deliberately not a single global formal mail switch.
