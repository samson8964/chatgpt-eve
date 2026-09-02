const SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize";
const SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token";
const ESI_BASE = "https://esi.evetech.net/latest";
const SCOPE = "esi-ui.open_window.v1 esi-mail.send_mail.v1";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!env.EVE_CLIENT_ID || !env.EVE_CLIENT_SECRET || !env.EVE_REDIRECT_URI) {
      return text("Worker 未配置完成：缺少 EVE_CLIENT_ID / EVE_CLIENT_SECRET / EVE_REDIRECT_URI。", 500);
    }
    if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);

    if (url.pathname === "/" || url.pathname === "/health") {
      const hasToken = Boolean(await env.AUTH_STORE.get("refresh_token"));
      const name = await env.AUTH_STORE.get("character_name");
      const id = await env.AUTH_STORE.get("character_id");
      return html(`<!doctype html><meta charset="utf-8"><title>EVE Contract Opener</title>
        <style>body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.65}code{background:#eee;padding:2px 6px;border-radius:5px}</style>
        <h1>EVE Contract Opener</h1>
        <p>状态：<b>${hasToken ? "已授权" : "尚未授权"}</b>${name ? ` · ${escapeHtml(name)} (${escapeHtml(id || "")})` : ""}</p>
        <p>权限：<code>${escapeHtml(SCOPE)}</code></p>
        <p>打开合同：<code>/c/合同ID</code></p>
        <p>打开市场：<code>/m/物品Type ID</code></p>
        <p><a href="/auth">重新授权角色</a> · <a href="/logout">清除授权</a></p>`);
    }

    if (url.pathname === "/logout") {
      await Promise.all(["refresh_token","character_id","character_name"].map(k => env.AUTH_STORE.delete(k)));
      return html("<!doctype html><meta charset='utf-8'><h2>已清除 EVE 授权。</h2><p><a href='/'>返回</a></p>");
    }
    if (url.pathname === "/auth") return startAuth(env, null);
    if (url.pathname === "/callback") return handleCallback(request, env);
    if (url.pathname === "/api/send-mail") return handleSendMail(request, env);

    const contractMatch = url.pathname.match(/^\/c\/(\d+)\/?$/);
    if (contractMatch) return handleOpen(env, `contract:${contractMatch[1]}`);
    const marketMatch = url.pathname.match(/^\/m\/(\d+)\/?$/);
    if (marketMatch) return handleOpen(env, `market:${marketMatch[1]}`);
    return text("Not found", 404);
  },
};

async function handleOpen(env, action) {
  const token = await getFreshToken(env);
  if (!token.ok) return startAuth(env, action);
  return openInEve(token.access_token, action);
}

async function handleSendMail(request, env) {
  if (request.method !== "POST") return text("Method not allowed", 405);
  if (!env.MAIL_API_KEY) return text("缺少 Cloudflare Secret：MAIL_API_KEY", 500);
  const auth = request.headers.get("Authorization") || "";
  if (auth !== `Bearer ${env.MAIL_API_KEY}`) return text("Unauthorized", 401);

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

  const senderId = Number(await env.AUTH_STORE.get("character_id") || 0);
  if (!senderId) return text("请重新 /auth，让 Worker 保存发送角色 ID。", 409);
  const token = await getFreshToken(env);
  if (!token.ok) return text(`EVE token refresh failed: ${token.detail || token.status}`, 502);

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
  return json({ ok: true, mail_id: Number(detail), sender_id: senderId, recipient_id: recipientId });
}

function startAuth(env, action) {
  const state = randomHex(24);
  const authUrl = new URL(SSO_AUTHORIZE);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("client_id", env.EVE_CLIENT_ID);
  authUrl.searchParams.set("redirect_uri", env.EVE_REDIRECT_URI);
  authUrl.searchParams.set("scope", SCOPE);
  authUrl.searchParams.set("state", state);
  const headers = new Headers({ Location: authUrl.toString() });
  headers.append("Set-Cookie", cookie("eve_state", state, 600));
  if (action) headers.append("Set-Cookie", cookie("eve_action", action, 600));
  return new Response(null, { status: 302, headers });
}

async function handleCallback(request, env) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  const cookies = parseCookies(request.headers.get("Cookie") || "");
  if (!code || !returnedState || !cookies.eve_state || returnedState !== cookies.eve_state) {
    return text("EVE SSO 回调校验失败：state 不匹配。", 400);
  }

  const resp = await tokenRequest(env, new URLSearchParams({ grant_type: "authorization_code", code }));
  if (!resp.ok) return text(`EVE SSO token exchange failed (${resp.status}): ${resp.detail}`, 502);
  await env.AUTH_STORE.put("refresh_token", resp.refresh_token);
  const claims = decodeJwtClaims(resp.access_token);
  const characterId = String(claims.sub || "").split(":").pop();
  if (/^\d+$/.test(characterId || "")) await env.AUTH_STORE.put("character_id", characterId);
  if (claims.name) await env.AUTH_STORE.put("character_name", String(claims.name));

  const action = cookies.eve_action || null;
  if (action) return openInEve(resp.access_token, action, true);
  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  headers.append("Set-Cookie", expiredCookie("eve_state"));
  headers.append("Set-Cookie", expiredCookie("eve_action"));
  return new Response(`<!doctype html><meta charset='utf-8'><h2>EVE 授权成功。</h2><p>角色：${escapeHtml(claims.name || characterId || "unknown")}</p><p>已申请合同窗口 + 发送邮件权限。</p><p><a href='/'>返回状态页</a></p>`, { status: 200, headers });
}

async function getFreshToken(env) {
  const refreshToken = await env.AUTH_STORE.get("refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no refresh token" };
  const result = await tokenRequest(env, new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken }));
  if (!result.ok) return result;
  if (result.refresh_token && result.refresh_token !== refreshToken) await env.AUTH_STORE.put("refresh_token", result.refresh_token);
  const claims = decodeJwtClaims(result.access_token);
  const characterId = String(claims.sub || "").split(":").pop();
  if (/^\d+$/.test(characterId || "")) await env.AUTH_STORE.put("character_id", characterId);
  if (claims.name) await env.AUTH_STORE.put("character_name", String(claims.name));
  return result;
}

async function tokenRequest(env, body) {
  const basic = btoa(`${env.EVE_CLIENT_ID}:${env.EVE_CLIENT_SECRET}`);
  const resp = await fetch(SSO_TOKEN, {
    method: "POST",
    headers: { Authorization: `Basic ${basic}`, "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
    body,
  });
  if (!resp.ok) return { ok: false, status: resp.status, detail: await resp.text() };
  return { ok: true, ...(await resp.json()) };
}

async function openInEve(accessToken, action, clearCookies = false) {
  const [kind, rawId] = action.split(":", 2);
  if (!/^\d+$/.test(rawId || "")) return text("Invalid action", 400);
  const endpoint = kind === "contract"
    ? `${ESI_BASE}/ui/openwindow/contract/?datasource=tranquility&contract_id=${rawId}`
    : `${ESI_BASE}/ui/openwindow/marketdetails/?datasource=tranquility&type_id=${rawId}`;
  const label = kind === "contract" ? `合同 ${rawId}` : `市场 ${rawId}`;
  const resp = await fetch(endpoint, { method: "POST", headers: { Authorization: `Bearer ${accessToken}`, Accept: "application/json" } });
  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  if (clearCookies) {
    headers.append("Set-Cookie", expiredCookie("eve_state"));
    headers.append("Set-Cookie", expiredCookie("eve_action"));
  }
  if (resp.status === 204) return new Response(`<!doctype html><meta charset="utf-8"><h2>已发送到 EVE 客户端</h2><p>${escapeHtml(label)} 应已打开。</p>`, { status: 200, headers });
  return new Response(`<!doctype html><meta charset="utf-8"><h2>EVE ESI 打开窗口失败</h2><p>HTTP ${resp.status}</p><pre>${escapeHtml(await resp.text())}</pre>`, { status: 502, headers });
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
