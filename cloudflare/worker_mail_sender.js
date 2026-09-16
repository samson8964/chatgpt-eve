import baseWorker from "./worker.js";

const SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize";
const SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token";
const ESI_BASE = "https://esi.evetech.net/latest";
const MAIL_SCOPE = "esi-mail.send_mail.v1";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/auth-mail") return startMailAuth(env);
    if (url.pathname === "/logout-mail") return logoutMail(env);
    if (url.pathname === "/mail-status") return mailStatus(env);

    if (url.pathname === "/callback") {
      const cookies = parseCookies(request.headers.get("Cookie") || "");
      if (cookies.eve_mail_state) return handleMailCallback(request, env, cookies);
    }

    if (url.pathname === "/api/send-mail") return handleSendMail(request, env);

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

  await env.AUTH_STORE.put("mail_refresh_token", resp.refresh_token);
  await env.AUTH_STORE.put("mail_character_id", characterId);
  if (characterName) await env.AUTH_STORE.put("mail_character_name", characterName);

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
  await Promise.all([
    "mail_refresh_token",
    "mail_character_id",
    "mail_character_name",
  ].map(k => env.AUTH_STORE.delete(k)));
  return html("<!doctype html><meta charset='utf-8'><h2>已清除邮件发送角色授权。</h2><p><a href='/auth-mail'>重新授权邮件发送角色</a></p>");
}

async function mailStatus(env) {
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);
  const hasToken = Boolean(await env.AUTH_STORE.get("mail_refresh_token"));
  const name = await env.AUTH_STORE.get("mail_character_name");
  const id = await env.AUTH_STORE.get("mail_character_id");
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

async function handleSendMail(request, env) {
  if (request.method !== "POST") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);

  let payload;
  try { payload = await request.json(); } catch { return text("Invalid JSON", 400); }
  const subject = String(payload.subject || "").slice(0, 1000);
  const body = String(payload.body || "").slice(0, 10000);
  const recipientId = Number(payload.recipient_id || 0);
  if (!subject || !body || !Number.isSafeInteger(recipientId) || recipientId <= 0) {
    return text("subject/body/recipient_id required", 400);
  }

  const idem = String(payload.idempotency_key || "").slice(0, 200);
  if (idem && await env.AUTH_STORE.get(`mail_sent:${idem}`)) {
    return json({ ok: true, skipped: true, reason: "duplicate" });
  }

  const senderId = Number(await env.AUTH_STORE.get("mail_character_id") || 0);
  const senderName = await env.AUTH_STORE.get("mail_character_name") || "";
  if (!Number.isSafeInteger(senderId) || senderId <= 0) {
    return json({ ok: false, error: "mail_sender_not_authorized", auth_url: "/auth-mail" }, 409);
  }

  const token = await getFreshMailToken(env);
  if (!token.ok) {
    return json({ ok: false, error: "mail_sender_token_refresh_failed", detail: token.detail || token.status, auth_url: "/auth-mail" }, 502);
  }

  const resp = await fetch(`${ESI_BASE}/characters/${senderId}/mail/?datasource=tranquility`, {
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
  const detail = await resp.text();
  if (resp.status !== 201) return text(`EVE mail failed (${resp.status}): ${detail}`, 502);

  if (idem) await env.AUTH_STORE.put(`mail_sent:${idem}`, "1", { expirationTtl: 172800 });
  return json({
    ok: true,
    mail_id: Number(detail),
    sender_id: senderId,
    sender_name: senderName,
    recipient_id: recipientId,
  });
}

async function getFreshMailToken(env) {
  const refreshToken = await env.AUTH_STORE.get("mail_refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no mail refresh token" };

  const result = await tokenRequest(env, new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
  }));
  if (!result.ok) return result;

  if (result.refresh_token && result.refresh_token !== refreshToken) {
    await env.AUTH_STORE.put("mail_refresh_token", result.refresh_token);
  }
  const claims = decodeJwtClaims(result.access_token);
  const characterId = String(claims.sub || "").split(":").pop();
  if (/^\d+$/.test(characterId || "")) await env.AUTH_STORE.put("mail_character_id", characterId);
  if (claims.name) await env.AUTH_STORE.put("mail_character_name", String(claims.name));
  return result;
}

async function tokenRequest(env, body) {
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
