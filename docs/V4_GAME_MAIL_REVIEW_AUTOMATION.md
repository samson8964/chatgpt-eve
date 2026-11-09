## 2026-11-09: Confirmed exact character name Arb Hunter (correcting 2026-11-08 typo)

The in-game showinfo link supplied by the user confirms **Arb Hunter**, not **Abr Hunter**. Use the exact EVE ESI name when configuring game-mail recipients. The route to DC SSO is unchanged.

## 2026-11-08: Replace retired LadyBaBa with Arb Hunter (Imperium access)

The user retired the LadyBaBa character and enrolled **Arb Hunter** in the Imperium.
Keep **MikeChong** as game-mail recipient; retire LadyBaBa as the second
destination. Two independent pieces of configuration are involved:

1. **O4T-Z5 private structure market read identity** is the Worker `dc`
   auth profile, not the mail recipient. In
   `cloudflare/worker.js` the O4T lane uses `auth_profile=dc` and
   `/auth-dc` with scope `esi-markets.structure_markets.v1`. The source
   documents O4T-Z5 as the structure link supplied by LadyBaBa. Existing
   `cj`, `banestar`, and retired `four_h` scope are NOT affected.
   The **actual currently authorized role is only verifiable on the live
   Worker status page**, not from repository source.

   - User opens
     https://eve-contract-opener.99617224.workers.dev/
     to inspect "DC影子市场授权" character name.
   - If the stored character is the retired LadyBaBa, user explicitly opens
     https://eve-contract-opener.99617224.workers.dev/auth-dc
     in their own browser, selects **Arb Hunter** in EVE SSO and grants the
     structure market permission. No secrets or tokens go through chat.
     Do **NOT** click `/logout-dc` first (that would remove the working
     credential before replacement).
   - Status page must show `Arb Hunter` next to DC. This confirms saved
     identity, *not* actual O4T market permission. Check an authenticated
     O4T page-1 request using the existing Windows key and then full-page
     coverage in the following scan.

2. **V4 EVE in-game research digest recipient** is a separate Windows
   config. The user-approved replacement is `Arb Hunter` for
   `LadyBaBa`; do not change the sender `LadyGuaGua` or the
   `MikeChong` recipient, Gmail, market economics, or formal alerts.
   A new `--replace-recipient` command resolves Arb Hunter's **exact
   numeric character ID via CCP public ESI** before an atomic write.
   It migrates schema 2 (MikeChong + LadyBaBa), or adds Arb Hunter to a
   MikeChong-only configuration, but does *not* activate a disabled channel.
   Existing receipts stay on disk; future sends are keyed by the new
   exact recipient ID and will not be sent to LadyBaBa.

Once the Windows scheduled task is **not Running**, from the SAME
Windows user session as `EVE-V4-Shadow`:

```powershell
$repo = Join-Path $HOME 'EVE-V4-Code'
$task = Get-ScheduledTask -TaskName 'EVE-V4-Shadow'
if ($task.State -eq 'Running') { throw 'Scan is running; do not update now' }
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed; config unchanged' }
Push-Location $repo
try {
    & .\.venv\Scripts\python.exe -m v4.game_mail_review --replace-recipient --recipient "Arb Hunter"
    if ($LASTEXITCODE -ne 0) { throw 'Recipient migration did not succeed' }
    & .\.venv\Scripts\python.exe -m v4.game_mail_review --status
    if ($LASTEXITCODE -ne 0) { throw 'Recipient status check failed' }
    & .\.venv\Scripts\python.exe -m v4.local_bridge_probe
    if ($LASTEXITCODE -ne 0) { throw 'Structure access check failed' }
} finally { Pop-Location }
```

Expected: `recipients=["MikeChong","Arb Hunter"]`; `structures.o4t.status=PAGE1_OK`.
`PAGE1_OK` is NOT proof that later pages are complete. There is no
`--send-now` in the migration because that would re-mail the most recent
run. The next independently completed scheduled shadow run should show
`o4t=COMPLETE` with `pages_fetched=pages`, and future EVE game-mail
receipts should use Arb Hunter's numeric ESI ID. If mail is currently
disabled, the migration refuses to turn it on: report that status and
confirm with the user before doing any enablement.

The local GitHub prep branch may not be the Windows checkout branch:
run `git -C $repo branch --show-current` and compare with
`prep/v4-windows-local-migration-20261013` before assuming pull has
updated the code. Never discard uncommitted local changes or force-switch
branches just to apply this migration.

---

## 2026-10-14 addition: LadyBaBa receives all future V4 EVE game-mail digests

**User explicitly requested** EVE game-mail alerts also go to LadyBaBa.
From the same Windows user profile as the existing `EVE-V4-Shadow` task:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
& .\.venv\Scripts\python.exe -m v4.game_mail_review --add-recipient --recipient LadyBaBa
if ($LASTEXITCODE -ne 0) { throw 'Cannot enable LadyBaBa' }
& .\.venv\Scripts\python.exe -m v4.game_mail_review --status
```

This is additive: the existing MikeChong recipient remains. The tool
resolves LadyBaBa's character ID through CCP's **public ESI exact-name**
lookup (not by guessing an ID or requesting extra OAuth scopes), then
persists only the recipient name and numeric ID; no credentials are saved
in the JSON configuration. The default Gmail recipient is unchanged.
Enabling is NOT a send.

To send the latest *already-completed* run to the newly-added LadyBaBa
immediately, without re-running a market scan or duplicating MikeChong's
previous mail, explicitly run:

```powershell
& .\.venv\Scripts\python.exe -m v4.game_mail_review --send-now
```

Future scheduled completed scans automatically deliver to both.
Every recipient has its own durable receipt and identical per-recipient
Worker idempotency key. Existing legacy `<run>.json` receipts remain
MikeChong's and are respected during upgrades; LadyBaBa uses
`<run>-<character-id>.json`. A failure for one character cannot block
the other, but scheduler exit code is nonzero to flag partial delivery.
The in-game `<url=contract:0//...>` and `<url=showinfo:...>` native
clickable links and compact market + contract summaries are unchanged.

### Windows SQLite test warning

If manually running old V4 unit tests shows `WinError 32` on temporary
`ledger.db` files, this indicates temporary SQLite handles or a transient
Windows file-locking race during **test cleanup**, not proof of lost
production scanning data. `v4/tests/test_local_store.py` now retries
this specific Windows sharing violation for a short bounded period,
while all other errors remain visible. Tests still fail if locks persist.
The unrelated `v4/ingest.py` generator already uses a `with` block
to close proof-file handles on termination; do not disable production
validation or remove SQLite WAL to work around test cleanup.

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
