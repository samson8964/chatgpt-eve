# Cloudflare Worker setup for EVE contract opener

Worker URL:

`https://eve-contract-opener.99617224.workers.dev`

EVE callback URL:

`https://eve-contract-opener.99617224.workers.dev/callback`

Required EVE scopes:

- `esi-ui.open_window.v1`
- `esi-mail.send_mail.v1`
- `esi-skills.read_skills.v1`

## 1. Create KV

Cloudflare Dashboard → Storage & Databases → KV → Create namespace.

Suggested namespace name: `eve-contract-auth`

Then open Worker `eve-contract-opener` → Settings → Bindings → Add binding → KV namespace.

Variable name must be exactly:

`AUTH_STORE`

Select the namespace you just created.

## 2. Add Worker variables / secrets

Worker → Settings → Variables and Secrets → Add.

Plaintext variables:

- `EVE_CLIENT_ID` = your public EVE application Client ID
- `EVE_REDIRECT_URI` = `https://eve-contract-opener.99617224.workers.dev/callback`

Secrets:

- `EVE_CLIENT_SECRET` = the EVE application Client Secret
- `MAIL_API_KEY` = private API key used by the mail and skills API routes

Never commit secrets to GitHub.

## 3. Deploy Worker code

The complete Worker source is `cloudflare/worker.js`.

For automatic deployment, add these GitHub Actions secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

Then run the `Deploy Cloudflare EVE Worker` workflow. The workflow uses Wrangler `--strict` and `--keep-vars` so it refuses unsafe remote-setting conflicts and preserves dashboard variables.

## 4. Authorize / re-authorize the EVE character

Open:

`https://eve-contract-opener.99617224.workers.dev/auth`

Select the EVE character and grant all requested scopes. After adding `esi-skills.read_skills.v1`, an existing refresh token must be replaced by completing this authorization flow again.

The Worker stores the refresh token in the bound KV namespace and rotates it when EVE SSO returns a replacement.

## 5. Test

With the authorized character logged into EVE, open a public contract URL:

`https://eve-contract-opener.99617224.workers.dev/c/CONTRACT_ID`

For a market details window:

`https://eve-contract-opener.99617224.workers.dev/m/TYPE_ID`

For skills, make an authenticated GET request to:

`https://eve-contract-opener.99617224.workers.dev/api/skills`

with header:

`Authorization: Bearer <MAIL_API_KEY>`

The skills response includes total SP, unallocated SP, allocated SP, skill counts, and the raw per-skill ESI data.

## 6. Revoke / switch character

Open:

`https://eve-contract-opener.99617224.workers.dev/logout`

Then authorize again with `/auth`.
