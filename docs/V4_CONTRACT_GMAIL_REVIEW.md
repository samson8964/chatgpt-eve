# EVE V4: immediate contract review Gmail and recurring local delivery

Status: V4 Windows local scans stay SHADOW only. This is a **research evidence
digest**, deliberately not a formal "SAFE buy now" opportunity mail. No V3 jobs
or formal V4 outbox are re-enabled.

## 2026-10-14 first delivered review email

The first authenticated Gmail review email was sent through the connected
ChatGPT Gmail account, with subject:
`【EVE V4捡漏】16:23自动扫描验收与合同研究首封邮件`.
It used the user's actual 16:23 Windows scan output: 32880 local audited proofs,
3/3 private structure markets complete, SQLite OK, malformed orders 0 and 10
zero-remaining excluded orders. The user has not supplied that run's individual
contract proof file to ChatGPT, so no candidate ID, live status, or profit was
fabricated. This **does not establish Windows automatic mail delivery**.

## One-time Windows Gmail setup (required before unattended sends)

Gmail SMTP requires a valid Gmail address plus a Gmail App Password for an
account where Google allows App Passwords. Do **not** paste the password into
ChatGPT or GitHub. Run in PowerShell as the Windows user that runs
`EVE-V4-Shadow`:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python -m v4.research_mail --configure
if ($LASTEXITCODE -ne 0) { throw 'Gmail setup failed' }
& $python -m v4.research_mail --send-now
if ($LASTEXITCODE -ne 0) { throw 'Initial contract review email failed' }
```

The console prompts for Gmail sender address, destination (Enter for self),
then an invisible Gmail App Password input. It stores the password in Windows
Credential Manager using the `keyring.backends.Windows` backend; local JSON
config contains only sender/recipient address, mode, enabled status. No secret
enters GitHub secrets, command-line arguments, stdout, or scan logs.

`--send-now` reads latest finished run and sends one real Gmail digest at
once. A receipt in `EVE-V4-Data/mail-review/receipts/<run>.json` prevents
normal duplicate sends for that run. Receipt saved only after SMTP acceptance.
As with any SMTP client, a process dying between acceptance and local receipt
can cause a duplicate on retry; this does not guarantee exactly once.

Starting at the **next scheduled run**, the existing every-two-hours
`v4.local_service` will send the next scan's contract-review digest
automatically *if configured*. It does not scan, query email, or send on mere
import; setup is explicit. Successful scan + email => normal task exit 0 (if
all coverage checks pass). Scan success + SMTP delivery failure => exit 3,
with `REVIEW_MAIL_FAILED <ExceptionClass>` in the local log. Scan incomplete
=> no apparent contract profits are mailed, but a degraded-source warning can
still be sent. Zero eligible contracts => a truthful zero-results digest.

For rollback or temporary disable:
```powershell
& $python -m v4.research_mail --disable
```
No need to alter existing Windows scheduled task, V3 jobs or emails. It does
not activate the former V3 sender or the formal V4 executable alert engine.

## What the contract digest actually proves

`v4.contract_review.make_review` streams the latest durable
`all_proofs.jsonl`, which was created in the same run as
`deep_shadow.json` and checked into local SQLite. It only presents
contract-side model signals that passed full snapshot buy depth, positive ROI
and positive best-bid-removal stress; all are labelled **not live verified**
and **not actionable**. It lists actual contract IDs, contract purchase price,
investment, included type IDs and quantities, snapshot profit, ROI, stressed
profit and expiry fields where available. It also counts why other contract
proofs were rejected. If coverage or source integrity is degraded, the email
suppresses apparent leads rather than suggesting purchases.

A safety fix in `v4.deep_scan` excludes public contracts that request
additional non-cash goods (any `is_included=false/unknown` item) from the
cash-only valuation engine. Previously taking only the included side would
artificially inflate their profit. The excluded contract count is recorded as
`contract_requested_items_excluded`. Real barter valuation requires
pricing the requested side separately.

**Not yet implemented:** full in-game contract access confirmation, realtime
order prices, BPO/BPC instance checks on every contract, contract-source valuation for unmonitored locations, production-safe notification/outbox. Gmail messages
must not claim those features.

## Testing

CI tests include `v4/tests/test_contract_review_mail.py` and
`v4/tests/test_contract_barter_exclusion.py`. SMTP is mocked. No test sends a
real email, accesses passwords, or opens the user's desktop. The first email
was separately sent via the connected Gmail tool. Actual local SMTP delivery
requires the one-time configuration and `--send-now` command above.

## 2026-10-14 corrected Jita 4-4 contract valuation

The previously introduced same-location contract buy-book model has been
withdrawn at the user's direction. **ALL cash contract item valuations use
the Jita 4-4 station (60003760) buy-order depth**, no matter where the
contract originates. This is one station's executable bid depth, not regional
averages, seller asks, or the pickup station's bid book.

Contracts found in the known market locations remain eligible for review,
but the source location is used only for estimated transport deductions,
availability, logistics and access risks. The current transport calculation
is an estimate, not a verified shipping quote. If route or cargo volume
cannot be evaluated, HAUL_UNVERIFIED blocks a cash profit claim. Tests
verify that a higher Amarr bid never changes the value of an Amarr contract
when the chosen valuation destination is Jita 4-4.

New reports record contract_pricing_basis=JITA_4_4_BUY_DEPTH_SNAPSHOT.
New proofs record valuation_basis=JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE,
valuation_location_id=60003760, actual source_location,
destination_location=60003760, and haul_cost_estimate_isk.
Email displays both pickup site and Jita liquidation reference.
Historical scans under the wrong valuation method remain in the audit
ledger but are not eligible for re-sending in the contract review email.
A new scan using the corrected code is required.

Still SHADOW research, not live trade approval. The public contract archive
does not prove every private contract is included.
