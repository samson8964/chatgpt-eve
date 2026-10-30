import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const src = await readFile(
  new URL("../../cloudflare/worker.js", import.meta.url), "utf8"
);
const { default: worker } = await import(
  "data:text/javascript;base64," + Buffer.from(src).toString("base64")
);
const jwt = (payload) => [
  "eyJhbGciOiJub25lIn0",
  Buffer.from(JSON.stringify(payload)).toString("base64url"),
  "unit-test-signature",
].join(".");
const charClaims = {
  sub: "CHARACTER:EVE:111222333",
  name: "Test BANESTAR Role",
  exp: Math.floor(Date.now() / 1000) + 3600,
};
const token = jwt(charClaims);
const fakeRefresh = "unit-test-only-banestar-refresh";
const seed = {
  refresh_token: "original-main",
  cj_refresh_token: "original-cj",
  dc_refresh_token: "original-dc",
  mail_refresh_token: "original-mail",
};
const makeEnv = () => {
  const kv = new Map(Object.entries(seed));
  return {
    env: {
      EVE_CLIENT_ID: "unit-client-id",
      EVE_CLIENT_SECRET: "unit-secret",
      EVE_REDIRECT_URI: "https://eve-contract-opener.unit/callback",
      MAIL_API_KEY: "unit-bridge-key",
      AUTH_STORE: {
        get: async k => kv.get(k) ?? null,
        put: async (k, v) => { kv.set(k, v); },
        delete: async k => { kv.delete(k); },
      },
    },
    kv,
  };
};

test("Dedicated SSO is separate, market scope only, and never overwrites three roles or mail", async () => {
  const {env, kv} = makeEnv();
  const pre = await worker.fetch(new Request(
    "https://eve-contract-opener.unit/api/structure-market?auth_profile=banestar&structure_id=1050474463169",
    {headers:{Authorization: "Bearer unit-bridge-key"}},
  ), env);
  assert.equal(pre.status, 401);
  assert.equal((await pre.json()).auth_url, "/auth-banestar");

  const start = await worker.fetch(
    new Request("https://eve-contract-opener.unit/auth-banestar"), env
  );
  assert.equal(start.status, 302);
  const location = new URL(start.headers.get("Location"));
  assert.equal(location.hostname, "login.eveonline.com");
  assert.equal(location.searchParams.get("scope"), "esi-markets.structure_markets.v1");
  assert.equal(location.searchParams.get("redirect_uri"), env.EVE_REDIRECT_URI);
  const state = location.searchParams.get("state");
  assert.ok(state && state.length > 30);
  const cookie = start.headers.get("Set-Cookie").split(";")[0];
  assert.ok(cookie.startsWith("eve_banestar_state="));

  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    if (url !== "https://login.eveonline.com/v2/oauth/token") {
      throw Error("Unexpected ESI request during OAuth code exchange");
    }
    assert.equal(init.method, "POST");
    assert.equal(new URLSearchParams(init.body).get("grant_type"), "authorization_code");
    return Response.json({access_token: token, refresh_token: fakeRefresh});
  };
  let callback;
  try {
    callback = await worker.fetch(new Request(
      "https://eve-contract-opener.unit/callback?code=unit-test-code&state=" + encodeURIComponent(state),
      {headers:{Cookie: cookie}},
    ), env);
  } finally {
    globalThis.fetch = original;
  }
  assert.equal(callback.status, 200);
  assert.ok((await callback.text()).includes("74L2-U 市场授权成功"));
  assert.equal(kv.get("banestar_refresh_token"), fakeRefresh);
  assert.equal(kv.get("banestar_character_id"), "111222333");
  assert.equal(kv.get("banestar_character_name"), charClaims.name);
  for (const [key,value] of Object.entries(seed)) {
    assert.equal(kv.get(key), value, "Existing protected key changed: " + key);
  }

  const previousFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    assert.ok(String(url).includes("/markets/structures/1050474463169/"));
    assert.equal(init.headers.Authorization, "Bearer " + token);
    return Response.json(
      [{
        order_id: 12345,
        location_id: 1050474463169,
        type_id: 34,
        is_buy_order: false,
        price: 42,
        volume_remain: 9,
      }],
      {headers:{"X-Pages":"1"}},
    );
  };
  try {
    const result = await worker.fetch(new Request(
      "https://eve-contract-opener.unit/api/structure-market?auth_profile=banestar&structure_id=1050474463169&page=1",
      {headers:{Authorization: "Bearer unit-bridge-key"}},
    ), env);
    assert.equal(result.status, 200);
    const data = await result.json();
    assert.equal(data.auth_profile, "banestar");
    assert.equal(data.structure_id, 1050474463169);
    assert.equal(data.orders.length, 1);
  } finally {
    globalThis.fetch = previousFetch;
  }
});

test("BANESTAR callback rejects mismatched state and does not save tokens", async () => {
  const {env,kv} = makeEnv();
  const res = await worker.fetch(new Request(
    "https://eve-contract-opener.unit/callback?code=example&state=incorrect",
    {headers:{Cookie:"eve_banestar_state=expected"}},
  ),env);
  assert.equal(res.status,400);
  assert.equal(kv.has("banestar_refresh_token"),false);
});
