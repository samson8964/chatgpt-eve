# EVE V4: one-off in-game mail test

This is an explicitly invoked **test only**, not a restoration of V3 alerts
or automatic game-mail delivery.

## User command on the existing Windows installation

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Git update failed" }
& .\.venv\Scripts\python.exe -m v4.eve_mail_test --recipient MikeChong
```

The test uses the **existing EVE bridge API key from Windows Credential
Manager**, not the Gmail App Password, and does not ask for another password.

The program first queries the protected Cloudflare endpoint
`/api/mail-health`; it requires the sender identity to be the previously
approved `LadyGuaGua`. It resolves the exact target character ID via the
public ESI universe/ids endpoint, without forwarding any bridge credential
to the public ESI. Finally, it POSTs **one** uniquely identified mail to
the protected Worker `/api/send-mail` endpoint. That Worker invokes
the CCP EVE mail API using its existing independent ESI OAuth authorization.
The user should inspect the in-game Mail inbox for `MikeChong`.

Other explicitly allowed owned test destinations:

```powershell
& .\.venv\Scripts\python.exe -m v4.eve_mail_test --recipient LadyBaBa
```

No other recipient names are accepted by this diagnostic. Each invocation
sends only to the one named character; do not automatically loop through
all characters without user intent. Repeating the command generates a
new unique test; the Worker protects against duplicate posting of the
same test request. The output contains sender, recipient, ESI character
IDs and mail ID but never the API key or refresh token.

Expected response: `status=EVE_GAME_MAIL_TEST_SENT`, `sent=true`,
`mail_id=<positive game-mail ID>`. This proves the API accepted the
message; the user should still inspect the in-game inbox to verify UI
delivery. `--health-only` checks mail sender authorization without sending.

## Failures (no credentials shown)

- `EVE_BRIDGE_KEY_MISSING_OR_INVALID`: current Windows Credential Manager
  does not contain the existing EVE Worker key under the local bridge service
- `WORKER_API_KEY_MISMATCH`: saved bridge key and Worker secret disagree
- `MAIL_SENDER_REAUTHORIZE_REQUIRED`: open the already deployed
  https://eve-contract-opener.99617224.workers.dev/auth-mail to reauthorize
  the intended `LadyGuaGua` mail sender via EVE SSO; do not paste tokens
- `UNEXPECTED_EVE_MAIL_SENDER`: an unrelated character is authorized
- `ESI_CHARACTER_NOT_FOUND_OR_AMBIGUOUS`: target must exactly match the
  selected game character
- `EVE_GAME_MAIL_SEND_FAILED_HTTP_...`: Worker or ESI rejected the post
- `NETWORK_REQUEST_FAILED_...`: possible network/HTTPS access problem

**Important:** successful Gmail SMTP mail does not prove EVE game mail.
This diagnostic does not activate V4 production opportunities, subscribe to
a schedule, change credentials, or edit data stores. Email values are
strictly test text; no investment recommendations.
