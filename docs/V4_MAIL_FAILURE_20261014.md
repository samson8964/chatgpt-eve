## 2026-10-14 20:23 Beijing: full scan good, both research sends failed

User-provided Windows log (NOT remotely executed) reported:
- Task EVE-V4-Shadow start 20:23 China, run 20261014T122301Z-caf4e25e
- Full scan + deep scan completed; SHADOW_RECORDED; 4-H/C-J/O4T COMPLETE
- source_input_integrity ALL_PARSED, 0 invalid public/structure orders,
  1 valid zero-remaining public order explicitly excluded
- SQLite unique proofs: 37,566
- REVIEW_MAIL_FAILED RuntimeError and GAME_REVIEW_MAIL_FAILED RuntimeError
- Task LastTaskResult 3 (mail failure). Prior 19:34 run sent Gmail and
  in-game mail successfully.

Because both mail channels invoke the same `v4.unified_review.make_review`,
a shared review/validation failure is suspected. Previous logging printed
only the exception class, so the **exact failed validation is not yet known**.
Do not claim EVE or Gmail credentials broke, and do not disable Jita-4-4
valuation checks simply to make email pass.

New tools shipped in this patch:
- `v4.mail_diagnostics`: read-only local audit of newest finished run,
  report prices/market proof counts, one approved exact error code, and
  existence of mail receipts. Does NOT call network, Gmail, EVE or vault,
  or send/restart anything. Does not print private data or secrets.
- `v4.local_service` prints safe, allowlisted error reason after each
  channel; strips unknown exception contents from the log.
- Added actual `v4.deep_scan` -> `v4.unified_review.make_review`
  integration test and explicit safe-log tests; these close prior
  isolated-fixture coverage gap.

### On the user's Windows host

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
& .\.venv\Scripts\python.exe -m v4.mail_diagnostics
```

If `review=READY` and two receipts are absent for the latest run, the
user may explicitly attempt mail delivery of that recorded run without
rescanning:

```powershell
& .\.venv\Scripts\python.exe -m v4.research_mail --send-now
& .\.venv\Scripts\python.exe -m v4.game_mail_review --send-now
```

If `review=BLOCKED`, capture `error_code`, `market_pricing_basis`,
`expected_market_proofs`, `actual_proofs`, and `contract_pricing_basis`
and repair the precise schema/proof issue. Do not send unverifiable opportunities.
If mixed-version scan produced old pricing schema, a fresh full scan under
the updated code is required. The existing two-hour task remains unchanged.

Commit is on PR #54's isolated migration branch; **GitHub CI success is not
proof that the Windows scheduler has loaded this new code**.
