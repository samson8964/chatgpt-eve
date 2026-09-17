import baseWorker from "./worker.js";

const SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize";
const SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token";
const ESI_BASE = "https://esi.evetech.net/latest";
const MAIL_SCOPE = "esi-mail.send_mail.v1";
const MAIL_ACCESS_TOKEN_CACHE_KEY = "https://eve-contract-opener.internal/mail-access-token";

let memoryMailAccessToken = "";
let memoryMailAccessTokenExp = 0;
let mailRefreshInFlight = null;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    try {
      if (url.pathname === "/auth-mail") return await startMailAuth(env);
      if (url.pathname === "/logout-mail") return await logoutMail(env);
      if (url.pathname === "/mail-status") return await mailStatus(env);

      if (url.pathname === "/callback") {
        const cookies = parseCookies(request.headers.get("Cookie") || "");
        if (cookies.eve_mail_state) return await handleMailCallback(request, env, cookies);
      }

      if (url.pathname === "/api/mail-health") return await handleMailHealth(request, env);
      if (url.pathname === "/api/send-mail") return await handleSendMail(request, env);
    } catch (err) {
      console.error("mail worker route exception", String(err?.stack || err));
      return json({ ok: false, error: "mail_worker_exception", detail: String(err) }, 502);
    }

    return baseWorker.fetch(request, env);
  },
};

async function startMailAuth(env) {
  if (!env.EVE_CLIENT_ID || !env.EVE_CLIENT_SECRET || !env.EVE_REDIRECT_URI) {
    return text("Worker 未配置完成：缺少 EVE_CLIENT_ID / EVE_CLIENT_SECRET / EVE_REDIRECT_URI。", 500);
  }
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);

  const state = randomHex(24);
  const authUrl = new URL(SSO_AUTHORIZE);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("client_id", env.EVE_CLIENT_ID);
  authUrl.searchParams.set("redirect_uri", env.EVE_REDIRECT_URI);
  authUrl.searchParams.set("scope", MAIL_SCOPE);
  authUrl.searchParams.set("state", state);

  const headers = new Headers({ Location: authUrl.toString() });
  headers.append("Set-Cookie", cookie("eve_mail_state", state, 600));
  return new Response(null, { status: 302, headers });
}

async function handleMailCallback(request, env, cookies) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  if (!code || !returnedState || !cookies.eve_mail_state || returnedState !== cookies.eve_mail_state) {
    return text("EVE 邮件发送角色授权失败：state 不匹配。", 400);
  }

  const resp = await tokenRequest(env, new URLSearchParams({ grant_type: "authorization_code", code }));
  if (!resp.ok) return text(`EVE SSO token exchange failed (${resp.status}): ${resp.detail}`, 502);

  const claims = decodeJwtClaims(resp.access_token);
  const characterId = String(claims.sub || "").split(":").pop();
  const characterName = String(claims.name || "");
  if (!/^\d+$/.test(characterId || "")) return text("无法识别授权角色 ID。", 502);

  try {
    await env.AUTH_STORE.put("mail_refresh_token", resp.refresh_token);
    await env.AUTH_STORE.put("mail_character_id", characterId);
    if (characterName) await env.AUTH_STORE.put("mail_character_name", characterName);
  } catch (err) {
    console.error("mail authorization persistence failed", String(err));
    return text("邮件角色授权已取得，但保存授权失败。请稍后重新授权。", 503);
  }

  rememberMailAccessToken(resp.access_token, claims);
  await cacheMailAccessToken(resp.access_token, claims, characterId, characterName);

  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  headers.append("Set-Cookie", expiredCookie("eve_mail_state"));
  return new Response(
    `<!doctype html><meta charset='utf-8'><h2>邮件发送角色授权成功</h2>` +
    `<p>当前邮件发送者：<b>${escapeHtml(characterName || characterId)}</b></p>` +
    `<p>仅授权：${escapeHtml(MAIL_SCOPE)}</p>` +
    `<p><a href='/mail-status'>查看邮件发送角色状态</a></p>`,
    { status: 200, headers }
  );
}

async function logoutMail(env) {
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);
  memoryMailAccessToken = "";
  memoryMailAccessTokenExp = 0;
  await Promise.allSettled([
    "mail_refresh_token",
    "mail_character_id",
    "mail_character_name",
  ].map(k => env.AUTH_STORE.delete(k)));
  try { await caches.default.delete(MAIL_ACCESS_TOKEN_CACHE_KEY); } catch {}
  return html("<!doctype html><meta charset='utf-8'><h2>已清除邮件发送角色授权。</h2><p><a href='/auth-mail'>重新授权邮件发送角色</a></p>");
}

async function mailStatus(env) {
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);
  const hasToken = Boolean(await safeKvGet(env, "mail_refresh_token"));
  const name = await safeKvGet(env, "mail_character_name");
  const id = await safeKvGet(env, "mail_character_id");
  return html(`<!doctype html><meta charset='utf-8'><title>EVE Mail Sender</title>
    <style>body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.65}code{background:#eee;padding:2px 6px;border-radius:5px}</style>
    <h1>EVE Mail Sender</h1>
    <p>邮件发送角色：<b>${hasToken ? "已授权" : "尚未授权"}</b>${name ? ` · ${escapeHtml(name)} (${escapeHtml(id || "")})` : ""}</p>
    <p>权限：<code>${escapeHtml(MAIL_SCOPE)}</code></p>
    <p><a href='/auth-mail'>授权/更换邮件发送角色</a> · <a href='/logout-mail'>清除邮件发送角色</a></p>
    <p>主角色授权仍由原来的 <code>/auth</code> 管理，技能、建筑市场和客户端开窗功能不会被这里覆盖。</p>`);
}

function requireApiKey(request, env) {
  if (!env.MAIL_API_KEY) return text("缺少 Cloudflare Secret：MAIL_API_KEY", 500);
  const auth = request.headers.get("Authorization") || "";
  if (auth !== `Bearer ${env.MAIL_API_KEY}`) return text("Unauthorized", 401);
  return null;
}

async function handleMailHealth(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;
  if (!env.AUTH_STORE) return json({ ok: false, error: "auth_store_missing" }, 500);

  const senderId = Number(await safeKvGet(env, "mail_character_id") || 0);
  const senderName = await safeKvGet(env, "mail_character_name") || "";
  const hasRefreshToken = Boolean(await safeKvGet(env, "mail_refresh_token"));
  if (!Number.isSafeInteger(senderId) || senderId <= 0 || !hasRefreshToken) {
    return json({ ok: false, error: "mail_sender_not_authorized", auth_url: "/auth-mail" }, 409);
  }

  const token = await getFreshMailToken(env);
  if (!token.ok) {
    return json({
      ok: false,
      error: "mail_sender_token_refresh_failed",
      detail: token.detail || token.status,
      auth_url: "/auth-mail",
    }, 502);
  }

  return json({
    ok: true,
    sender_id: senderId,
    sender_name: senderName,
    token_source: token.cached || "refreshed",
    refresh_token_persisted: token.refresh_token_persisted !== false,
  });
}

async function handleSendMail(request, env) {
  if (request.method !== "POST") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;
  if (!env.AUTH_STORE) return json({ ok: false, error: "auth_store_missing" }, 500);

  let payload;
  try { payload = await request.json(); } catch { return text("Invalid JSON", 400); }
  const subject = String(payload.subject || "").slice(0, 1000);
  const body = String(payload.body || "").slice(0, 10000);
  const recipientId = Number(payload.recipient_id || 0);
  if (!subject || !body || !Number.isSafeInteger(recipientId) || recipientId <= 0) {
    return text("subject/body/recipient_id required", 400);
  }

  const idem = String(payload.idempotency_key || "").slice(0, 200);
  const duplicate = idem ? await safeKvGet(env, `mail_sent:${idem}`) : null;
  if (duplicate) {
    return json({ ok: true, skipped: true, reason: "duplicate" });
  }

  const senderId = Number(await safeKvGet(env, "mail_character_id") || 0);
  const senderName = await safeKvGet(env, "mail_character_name") || "";
  if (!Number.isSafeInteger(senderId) || senderId <= 0) {
    return json({ ok: false, error: "mail_sender_not_authorized", auth_url: "/auth-mail" }, 409);
  }

  const token = await getFreshMailToken(env);
  if (!token.ok) {
    return json({ ok: false, error: "mail_sender_token_refresh_failed", detail: token.detail || token.status, auth_url: "/auth-mail" }, 502);
  }

  let resp;
  try {
    resp = await fetch(`${ESI_BASE}/characters/${senderId}/mail/?datasource=tranquility`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token.access_token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        approved_cost: 0,
        subject,
        body,
        recipients: [{ recipient_id: recipientId, recipient_type: "character" }],
      }),
    });
  } catch (err) {
    return json({ ok: false, error: "eve_mail_network_error", detail: String(err) }, 502);
  }

  const detail = await resp.text();
  if (resp.status !== 201) {
    return json({ ok: false, error: "eve_mail_failed", status: resp.status, detail }, 502);
  }

  // Never turn a successfully accepted EVE mail into HTTP 500 just because KV
  // idempotency persistence is temporarily unavailable. The caller must not retry
  // an already accepted mail in that case.
  let idempotencyPersisted = true;
  if (idem) {
    idempotencyPersisted = await safeKvPut(env, `mail_sent:${idem}`, "1", { expirationTtl: 172800 });
  }

  return json({
    ok: true,
    mail_id: Number(detail),
    sender_id: senderId,
    sender_name: senderName,
    recipient_id: recipientId,
    idempotency_persisted: idempotencyPersisted,
    refresh_token_persisted: token.refresh_token_persisted !== false,
  });
}

function rememberMailAccessToken(accessToken, claims = {}) {
  const nowSec = Math.floor(Date.now() / 1000);
  memoryMailAccessToken = accessToken || "";
  memoryMailAccessTokenExp = Number(claims.exp || 0) || (nowSec + 900);
}

async function readCachedMailAccessToken() {
  const nowSec = Math.floor(Date.now() / 1000);
  if (memoryMailAccessToken && memoryMailAccessTokenExp > nowSec + 60) {
    return { ok: true, access_token: memoryMailAccessToken, cached: "memory" };
  }
  try {
    const cached = await caches.default.match(MAIL_ACCESS_TOKEN_CACHE_KEY);
    if (!cached) return null;
    const data = await cached.json();
    if (!data || !data.access_token || Number(data.exp || 0) <= nowSec + 60) return null;
    memoryMailAccessToken = String(data.access_token);
    memoryMailAccessTokenExp = Number(data.exp);
    return { ok: true, access_token: memoryMailAccessToken, cached: "edge" };
  } catch (err) {
    console.warn("mail access token cache read failed", String(err));
    return null;
  }
}

async function cacheMailAccessToken(accessToken, claims = {}, characterId = "", characterName = "") {
  if (!accessToken) return;
  const nowSec = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp || 0) || (nowSec + 900);
  const ttl = Math.max(60, Math.min(1100, exp - nowSec - 60));
  try {
    const response = new Response(JSON.stringify({ access_token: accessToken, exp, character_id: characterId, character_name: characterName }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": `public, max-age=${ttl}`,
      },
    });
    await caches.default.put(MAIL_ACCESS_TOKEN_CACHE_KEY, response);
  } catch (err) {
    console.warn("mail access token cache write failed", String(err));
  }
}

async function refreshMailAccessToken(env) {
  const refreshToken = await safeKvGet(env, "mail_refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no mail refresh token" };

  const result = await tokenRequest(env, new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
  }));
  if (!result.ok) return result;

  const claims = decodeJwtClaims(result.access_token);
  rememberMailAccessToken(result.access_token, claims);
  await cacheMailAccessToken(result.access_token, claims, String(claims.sub || "").split(":").pop(), String(claims.name || ""));

  let refreshTokenPersisted = true;
  if (result.refresh_token && result.refresh_token !== refreshToken) {
    refreshTokenPersisted = await safeKvPut(env, "mail_refresh_token", result.refresh_token);
  }

  // mail_character_id/name are persisted during /auth-mail only. Rewriting the
  // same values on every send previously consumed KV writes for no benefit.
  return { ...result, refresh_token_persisted: refreshTokenPersisted };
}

async function getFreshMailToken(env) {
  const cached = await readCachedMailAccessToken();
  if (cached) return cached;

  if (!mailRefreshInFlight) mailRefreshInFlight = refreshMailAccessToken(env);
  try {
    return await mailRefreshInFlight;
  } finally {
    mailRefreshInFlight = null;
  }
}

async function tokenRequest(env, body) {
  try {
    const basic = btoa(`${env.EVE_CLIENT_ID}:${env.EVE_CLIENT_SECRET}`);
    const resp = await fetch(SSO_TOKEN, {
      method: "POST",
      headers: {
        Authorization: `Basic ${basic}`,
        "Content-Type": "application/x-www-form-urlencoded",
        Accept: "application/json",
      },
      body,
    });
    if (!resp.ok) return { ok: false, status: resp.status, detail: await resp.text() };
    return { ok: true, ...(await resp.json()) };
  } catch (err) {
    return { ok: false, status: 502, detail: `token request exception: ${String(err)}` };
  }
}

async function safeKvGet(env, key) {
  try {
    return await env.AUTH_STORE.get(key);
  } catch (err) {
    console.warn(`KV get failed for ${key}`, String(err));
    return null;
  }
}

async function safeKvPut(env, key, value, options = undefined) {
  try {
    if (options) await env.AUTH_STORE.put(key, value, options);
    else await env.AUTH_STORE.put(key, value);
    return true;
  } catch (err) {
    console.warn(`KV put failed for ${key}`, String(err));
    return false;
  }
}

function decodeJwtClaims(token) {
  try {
    const part = token.split(".")[1];
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(part.length / 4) * 4, "=");
    return JSON.parse(decodeURIComponent([...atob(b64)].map(c => "%" + c.charCodeAt(0).toString(16).padStart(2, "0")).join("")));
  } catch { return {}; }
}

function parseCookies(raw) {
  const out = {};
  for (const part of raw.split(";")) {
    const idx = part.indexOf("=");
    if (idx >= 0) out[part.slice(0, idx).trim()] = decodeURIComponent(part.slice(idx + 1).trim());
  }
  return out;
}
function cookie(name, value, maxAge) { return `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`; }
function expiredCookie(name) { return `${name}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`; }
function randomHex(bytes) { const a = new Uint8Array(bytes); crypto.getRandomValues(a); return [...a].map(x => x.toString(16).padStart(2, "0")).join(""); }
function text(body, status = 200) { return new Response(body, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } }); }
function html(body, status = 200) { return new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8" } }); }
function json(obj, status = 200) { return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json; charset=utf-8" } }); }
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
