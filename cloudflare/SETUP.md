# Cloudflare Worker setup for EVE contract opener

Worker URL:

`https://eve-contract-opener.99617224.workers.dev`

EVE callback URL:

`https://eve-contract-opener.99617224.workers.dev/callback`

Required EVE scope:

`esi-ui.open_window.v1`

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

Secret:

- `EVE_CLIENT_SECRET` = the EVE application Client Secret

Never commit `EVE_CLIENT_SECRET` to GitHub.

## 3. Replace Worker code

Copy the complete contents of `cloudflare/worker.js` into the Cloudflare Worker editor and deploy.

## 4. First authorization

Open:

`https://eve-contract-opener.99617224.workers.dev/auth`

Select the EVE character that should receive contract-window opens and authorize `esi-ui.open_window.v1`.

The Worker stores only the refresh token in the bound KV namespace so it can refresh short-lived access tokens. EVE SSO refresh tokens can rotate; the Worker updates the stored refresh token whenever SSO returns a replacement.

## 5. Test

With the authorized character logged into EVE, open a public contract URL:

`https://eve-contract-opener.99617224.workers.dev/c/CONTRACT_ID`

For a market details window:

`https://eve-contract-opener.99617224.workers.dev/m/TYPE_ID`

A successful ESI request returns HTTP 204 from ESI and the Worker shows a confirmation page.

## 6. Revoke / switch character

Open:

`https://eve-contract-opener.99617224.workers.dev/logout`

Then authorize again with `/auth`.
