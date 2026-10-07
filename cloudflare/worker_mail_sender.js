import baseWorker from "./worker.js";

const SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize";
const SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token";
const ESI_BASE = "https://esi.evetech.net/latest";
const MAIL_SCOPE = "esi-mail.send_mail.v1 esi-wallet.read_character_wallet.v1 esi-markets.read_character_orders.v1 esi-contracts.read_character_contracts.v1 esi-assets.read_assets.v1";
const MAIL_ACCESS_TOKEN_CACHE_KEY = "https://eve-contract-opener.internal/mail-access-token";
const SKILL_SCOPE = "esi-skills.read_skills.v1 esi-skills.read_skillqueue.v1 esi-wallet.read_character_wallet.v1 esi-markets.read_character_orders.v1 esi-contracts.read_character_contracts.v1 esi-assets.read_assets.v1";
const SKILL_ACCESS_TOKEN_CACHE_KEY = "https://eve-contract-opener.internal/skill-access-token";
const REQUIRED_SKILL_CHARACTER = "MikeChong";
const GITHUB_REPO = "samson8964/chatgpt-eve";
const FAST_SCAN_CRON = "*/15 * * * *";
const BPC_DEEP_CRON = "0 */3 * * *";

let memoryMailAccessToken = "";
let memoryMailAccessTokenExp = 0;
let mailRefreshInFlight = null;
let memorySkillAccessToken = "";
let memorySkillAccessTokenExp = 0;
let skillRefreshInFlight = null;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/auth-mail") return startMailAuth(env);
    if (url.pathname === "/logout-mail") return logoutMail(env);
    if (url.pathname === "/mail-status") return mailStatus(env);
    if (url.pathname === "/api/mail-health") return handleMailHealth(request, env);
    if (url.pathname === "/api/scheduler-health") return handleSchedulerHealth(request, env);
    if (url.pathname === "/auth-skills") return startSkillAuth(env);
    if (url.pathname === "/logout-skills") return logoutSkills(env);
    if (url.pathname === "/skill-status") return skillStatus(env);
    if (url.pathname === "/api/mikechong-skills") return handleSkillData(request, env);
    if (url.pathname === "/api/trade-data") return handleTradeData(request, env);

    if (url.pathname === "/callback") {
      const cookies = parseCookies(request.headers.get("Cookie") || "");
      if (cookies.eve_skill_state) return handleSkillCallback(request, env, cookies);
      if (cookies.eve_mail_state) return handleMailCallback(request, env, cookies);
    }

    if (url.pathname === "/api/send-mail") return handleSendMail(request, env);

    return baseWorker.fetch(request, env);
  },

  async scheduled(controller, env, ctx) {
    ctx.waitUntil(handleScheduledDispatch(controller, env));
  },
};

async function handleSchedulerHealth(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;
  return json({
    ok: true,
    configured: Boolean(env.GITHUB_DISPATCH_TOKEN),
    repository: GITHUB_REPO,
    fast_scan: { cron: FAST_SCAN_CRON, workflow: "scan.yml" },
    bpc_deep: { cron: BPC_DEEP_CRON, workflow: "v3-bpc-deep.yml" },
  });
}

async function dispatchGitHubWorkflow(env, workflow, inputs = null) {
  if (!env.GITHUB_DISPATCH_TOKEN) {
    throw new Error("missing Cloudflare secret GITHUB_DISPATCH_TOKEN");
  }
  const payload = { ref: "main" };
  if (inputs && Object.keys(inputs).length) payload.inputs = inputs;

  const resp = await fetch(
    `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "eve-v3-cloudflare-scheduler/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify(payload),
    },
  );
  const detail = await resp.text();
  if (resp.status !== 204) {
    throw new Error(`GitHub workflow dispatch failed workflow=${workflow} status=${resp.status} detail=${detail.slice(0, 500)}`);
  }
}

async function handleScheduledDispatch(controller, env) {
  const cron = String(controller.cron || "");
  const scheduledTime = Number(controller.scheduledTime || Date.now());

  let workflow = "";
  let inputs = null;
  if (cron === FAST_SCAN_CRON) {
    workflow = "scan.yml";
    inputs = { source: "cloudflare-cron" };
  } else if (cron === BPC_DEEP_CRON) {
    workflow = "v3-bpc-deep.yml";
    inputs = { reason: "cloudflare-cron" };
  } else {
    console.warn("Unknown scheduled cron; skip", cron);
    return;
  }

  const idemKey = `scheduler_dispatch:${workflow}:${scheduledTime}`;
  if (env.AUTH_STORE) {
    try {
      if (await env.AUTH_STORE.get(idemKey)) {
        console.log("scheduled dispatch duplicate skipped", workflow, scheduledTime);
        return;
      }
    } catch (err) {
      console.warn("scheduler idempotency read failed", String(err));
    }
  }

  await dispatchGitHubWorkflow(env, workflow, inputs);

  if (env.AUTH_STORE) {
    try {
      await env.AUTH_STORE.put(idemKey, "1", { expirationTtl: 21600 });
    } catch (err) {
      console.warn("scheduler idempotency persistence failed", String(err));
    }
  }
  console.log("scheduled dispatch accepted", { cron, workflow, scheduledTime });
}

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
    return text(`保存邮件角色授权失败：${String(err)}`, 503);
  }

  rememberMailAccessToken(resp.access_token, claims);
  await cacheMailAccessToken(resp.access_token, claims);

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

async function handleMailHealth(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;
  if (!env.AUTH_STORE) return json({ ok: false, error: "auth_store_missing" }, 500);

  const senderId = Number(await env.AUTH_STORE.get("mail_character_id") || 0);
  const senderName = await env.AUTH_STORE.get("mail_character_name") || "";
  const hasRefreshToken = Boolean(await env.AUTH_STORE.get("mail_refresh_token"));
  if (!senderId || !hasRefreshToken) {
    return json({ ok: false, error: "mail_sender_not_authorized", sender_id: senderId || null, sender_name: senderName || null, auth_url: "/auth-mail" }, 409);
  }

  const token = await getFreshMailToken(env);
  if (!token.ok) {
    return json({ ok: false, error: "mail_sender_token_refresh_failed", detail: token.detail || token.status, sender_id: senderId, sender_name: senderName, auth_url: "/auth-mail" }, 502);
  }
  return json({ ok: true, sender_id: senderId, sender_name: senderName, token_source: token.cached || "refresh" });
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
  if (idem) {
    try {
      if (await env.AUTH_STORE.get(`mail_sent:${idem}`)) {
        return json({ ok: true, skipped: true, reason: "duplicate" });
      }
    } catch (err) {
      console.warn("mail idempotency read failed", String(err));
    }
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

  const mailPayload = JSON.stringify({
    approved_cost: 0,
    subject,
    body,
    recipients: [{ recipient_id: recipientId, recipient_type: "character" }],
  });

  let resp = null;
  let detail = "";
  let lastException = "";
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      resp = await fetch(`${ESI_BASE}/characters/${senderId}/mail/?datasource=tranquility`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token.access_token}`,
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: mailPayload,
      });
      detail = await resp.text();
      if (resp.status === 201) break;

      const retryable = resp.status === 420 || resp.status === 429 || resp.status >= 500;
      if (!retryable || attempt >= 3) {
        return text(`EVE mail failed (${resp.status}): ${detail}`, 502);
      }

      const retryAfter = Number(resp.headers.get("Retry-After") || 0);
      const esiReset = Number(resp.headers.get("X-Esi-Error-Limit-Reset") || 0);
      const backoffSeconds = Math.min(15, Math.max(attempt * 2, retryAfter, esiReset));
      console.warn(`EVE mail transient failure status=${resp.status}; retrying in ${backoffSeconds}s attempt=${attempt + 1}/3`);
      await new Promise((resolve) => setTimeout(resolve, backoffSeconds * 1000));
    } catch (err) {
      lastException = String(err);
      if (attempt >= 3) {
        return json({ ok: false, error: "eve_mail_request_exception", detail: lastException }, 502);
      }
      const backoffSeconds = attempt * 2;
      console.warn(`EVE mail request exception; retrying in ${backoffSeconds}s attempt=${attempt + 1}/3 detail=${lastException}`);
      await new Promise((resolve) => setTimeout(resolve, backoffSeconds * 1000));
    }
  }

  if (!resp || resp.status !== 201) {
    return text(`EVE mail failed (${resp ? resp.status : "exception"}): ${detail || lastException}`, 502);
  }

  // Once EVE returns 201 the mail is already accepted. Idempotency persistence is
  // best-effort only; never turn a successful send into HTTP 500 and trigger duplicates.
  if (idem) {
    try {
      await env.AUTH_STORE.put(`mail_sent:${idem}`, "1", { expirationTtl: 172800 });
    } catch (err) {
      console.warn("mail idempotency persistence failed after successful send", String(err));
    }
  }

  return json({
    ok: true,
    mail_id: Number(detail),
    sender_id: senderId,
    sender_name: senderName,
    recipient_id: recipientId,
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

async function cacheMailAccessToken(accessToken, claims = {}) {
  if (!accessToken) return;
  const nowSec = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp || 0) || (nowSec + 900);
  const ttl = Math.max(60, Math.min(1100, exp - nowSec - 60));
  try {
    const response = new Response(JSON.stringify({ access_token: accessToken, exp }), {
      headers: { "Content-Type": "application/json", "Cache-Control": `public, max-age=${ttl}` },
    });
    await caches.default.put(MAIL_ACCESS_TOKEN_CACHE_KEY, response);
  } catch (err) {
    console.warn("mail access token cache write failed", String(err));
  }
}

async function refreshMailAccessToken(env) {
  const refreshToken = await env.AUTH_STORE.get("mail_refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no mail refresh token" };

  let result;
  try {
    result = await tokenRequest(env, new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken }));
  } catch (err) {
    return { ok: false, status: 502, detail: `token request exception: ${String(err)}` };
  }
  if (!result.ok) return result;

  const claims = decodeJwtClaims(result.access_token);
  rememberMailAccessToken(result.access_token, claims);
  await cacheMailAccessToken(result.access_token, claims);

  // Rotated refresh tokens must be persisted, but a temporary KV write failure must
  // not crash the current request because the new access token is already valid.
  if (result.refresh_token && result.refresh_token !== refreshToken) {
    try {
      await env.AUTH_STORE.put("mail_refresh_token", result.refresh_token);
    } catch (err) {
      console.warn("mail refresh token persistence failed", String(err));
    }
  }
  return result;
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


async function startSkillAuth(env) {
  if (!env.EVE_CLIENT_ID || !env.EVE_CLIENT_SECRET || !env.EVE_REDIRECT_URI) {
    return text("Worker 未配置完成：缺少 EVE_CLIENT_ID / EVE_CLIENT_SECRET / EVE_REDIRECT_URI。", 500);
  }
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);

  const state = randomHex(24);
  const authUrl = new URL(SSO_AUTHORIZE);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("client_id", env.EVE_CLIENT_ID);
  authUrl.searchParams.set("redirect_uri", env.EVE_REDIRECT_URI);
  authUrl.searchParams.set("scope", SKILL_SCOPE);
  authUrl.searchParams.set("state", state);

  const headers = new Headers({ Location: authUrl.toString() });
  headers.append("Set-Cookie", cookie("eve_skill_state", state, 600));
  return new Response(null, { status: 302, headers });
}

async function handleSkillCallback(request, env, cookies) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  if (!code || !returnedState || !cookies.eve_skill_state || returnedState !== cookies.eve_skill_state) {
    return text("EVE 技能授权失败：state 不匹配。", 400);
  }

  const resp = await tokenRequest(env, new URLSearchParams({ grant_type: "authorization_code", code }));
  if (!resp.ok) return text(`EVE SSO token exchange failed (${resp.status}): ${resp.detail}`, 502);

  const claims = decodeJwtClaims(resp.access_token);
  const characterId = String(claims.sub || "").split(":").pop();
  const characterName = String(claims.name || "");
  if (!/^\d+$/.test(characterId || "")) return text("无法识别技能授权角色 ID。", 502);
  if (characterName.toLowerCase() !== REQUIRED_SKILL_CHARACTER.toLowerCase()) {
    return html(`<!doctype html><meta charset='utf-8'><h2>没有保存授权</h2><p>你刚才选择的是 <b>${escapeHtml(characterName || characterId)}</b>，技能槽只允许 <b>${escapeHtml(REQUIRED_SKILL_CHARACTER)}</b>。</p><p><a href='/auth-skills'>重新选择 MikeChong</a></p>`, 400);
  }

  try {
    await env.AUTH_STORE.put("skill_refresh_token", resp.refresh_token);
    await env.AUTH_STORE.put("skill_character_id", characterId);
    await env.AUTH_STORE.put("skill_character_name", characterName);
  } catch (err) {
    return text(`保存技能角色授权失败：${String(err)}`, 503);
  }

  rememberSkillAccessToken(resp.access_token, claims);
  await cacheSkillAccessToken(resp.access_token, claims);

  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  headers.append("Set-Cookie", expiredCookie("eve_skill_state"));
  return new Response(
    `<!doctype html><meta charset='utf-8'><h2>MikeChong 技能授权成功</h2><p>角色：<b>${escapeHtml(characterName)}</b></p><p>权限：<code>${escapeHtml(SKILL_SCOPE)}</code></p><p>授权已独立保存，不会覆盖邮件或市场角色。</p><p><a href='/skill-status'>查看技能授权状态</a></p>`,
    { status: 200, headers }
  );
}

async function logoutSkills(env) {
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);
  memorySkillAccessToken = "";
  memorySkillAccessTokenExp = 0;
  await Promise.all([
    "skill_refresh_token",
    "skill_character_id",
    "skill_character_name",
  ].map(k => env.AUTH_STORE.delete(k)));
  return html("<!doctype html><meta charset='utf-8'><h2>已清除 MikeChong 技能授权。</h2><p><a href='/auth-skills'>重新授权</a></p>");
}

async function skillStatus(env) {
  if (!env.AUTH_STORE) return text("Worker 未绑定 KV：AUTH_STORE。", 500);
  const hasToken = Boolean(await env.AUTH_STORE.get("skill_refresh_token"));
  const name = await env.AUTH_STORE.get("skill_character_name");
  const id = await env.AUTH_STORE.get("skill_character_id");
  return html(`<!doctype html><meta charset='utf-8'><title>MikeChong Skill API</title>
    <style>body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.65}code{background:#eee;padding:2px 6px;border-radius:5px}</style>
    <h1>MikeChong Skill API</h1>
    <p>技能角色：<b>${hasToken ? "已授权" : "尚未授权"}</b>${name ? ` · ${escapeHtml(name)} (${escapeHtml(id || "")})` : ""}</p>
    <p>权限：<code>${escapeHtml(SKILL_SCOPE)}</code></p>
    <p><a href='/auth-skills'>授权/重新授权 MikeChong</a> · <a href='/logout-skills'>清除技能授权</a></p>
    <p>该授权槽与邮件发送、主角色和 C-J 市场授权彼此独立。</p>`);
}

async function handleSkillData(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;
  if (!env.AUTH_STORE) return json({ ok: false, error: "auth_store_missing" }, 500);

  const characterId = Number(await env.AUTH_STORE.get("skill_character_id") || 0);
  const characterName = await env.AUTH_STORE.get("skill_character_name") || "";
  if (!Number.isSafeInteger(characterId) || characterId <= 0) {
    return json({ ok: false, error: "skill_character_not_authorized", auth_url: "/auth-skills" }, 409);
  }

  const token = await getFreshSkillToken(env);
  if (!token.ok) {
    return json({ ok: false, error: "skill_token_refresh_failed", detail: token.detail || token.status, auth_url: "/auth-skills" }, 502);
  }

  const headers = { Authorization: `Bearer ${token.access_token}`, Accept: "application/json" };
  const [skillsResp, queueResp] = await Promise.all([
    fetch(`${ESI_BASE}/characters/${characterId}/skills/?datasource=tranquility`, { headers }),
    fetch(`${ESI_BASE}/characters/${characterId}/skillqueue/?datasource=tranquility`, { headers }),
  ]);
  const skillsText = await skillsResp.text();
  const queueText = await queueResp.text();
  if (skillsResp.status !== 200 || queueResp.status !== 200) {
    return json({
      ok: false,
      error: "esi_skill_read_failed",
      skills_status: skillsResp.status,
      queue_status: queueResp.status,
      skills_detail: skillsText,
      queue_detail: queueText,
      auth_url: "/auth-skills",
    }, 502);
  }

  let skillsData, queueData;
  try {
    skillsData = JSON.parse(skillsText);
    queueData = JSON.parse(queueText);
  } catch {
    return json({ ok: false, error: "invalid_esi_json" }, 502);
  }

  return json({
    ok: true,
    character_id: characterId,
    character_name: characterName,
    total_sp: Number(skillsData.total_sp || 0),
    unallocated_sp: Number(skillsData.unallocated_sp || 0),
    skills: Array.isArray(skillsData.skills) ? skillsData.skills : [],
    skillqueue: Array.isArray(queueData) ? queueData : [],
  });
}

function rememberSkillAccessToken(accessToken, claims = {}) {
  const nowSec = Math.floor(Date.now() / 1000);
  memorySkillAccessToken = accessToken || "";
  memorySkillAccessTokenExp = Number(claims.exp || 0) || (nowSec + 900);
}

async function readCachedSkillAccessToken() {
  const nowSec = Math.floor(Date.now() / 1000);
  if (memorySkillAccessToken && memorySkillAccessTokenExp > nowSec + 60) {
    return { ok: true, access_token: memorySkillAccessToken, cached: "memory" };
  }
  try {
    const cached = await caches.default.match(SKILL_ACCESS_TOKEN_CACHE_KEY);
    if (!cached) return null;
    const data = await cached.json();
    if (!data || !data.access_token || Number(data.exp || 0) <= nowSec + 60) return null;
    memorySkillAccessToken = String(data.access_token);
    memorySkillAccessTokenExp = Number(data.exp);
    return { ok: true, access_token: memorySkillAccessToken, cached: "edge" };
  } catch (err) {
    console.warn("skill access token cache read failed", String(err));
    return null;
  }
}

async function cacheSkillAccessToken(accessToken, claims = {}) {
  if (!accessToken) return;
  const nowSec = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp || 0) || (nowSec + 900);
  const ttl = Math.max(60, Math.min(1100, exp - nowSec - 60));
  try {
    const response = new Response(JSON.stringify({ access_token: accessToken, exp }), {
      headers: { "Content-Type": "application/json", "Cache-Control": `public, max-age=${ttl}` },
    });
    await caches.default.put(SKILL_ACCESS_TOKEN_CACHE_KEY, response);
  } catch (err) {
    console.warn("skill access token cache write failed", String(err));
  }
}

async function refreshSkillAccessToken(env) {
  const refreshToken = await env.AUTH_STORE.get("skill_refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no skill refresh token" };

  let result;
  try {
    result = await tokenRequest(env, new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken }));
  } catch (err) {
    return { ok: false, status: 502, detail: `token request exception: ${String(err)}` };
  }
  if (!result.ok) return result;

  const claims = decodeJwtClaims(result.access_token);
  rememberSkillAccessToken(result.access_token, claims);
  await cacheSkillAccessToken(result.access_token, claims);
  if (result.refresh_token && result.refresh_token !== refreshToken) {
    try {
      await env.AUTH_STORE.put("skill_refresh_token", result.refresh_token);
    } catch (err) {
      console.warn("skill refresh token persistence failed", String(err));
    }
  }
  return result;
}

async function getFreshSkillToken(env) {
  const cached = await readCachedSkillAccessToken();
  if (cached) return cached;
  if (!skillRefreshInFlight) skillRefreshInFlight = refreshSkillAccessToken(env);
  try {
    return await skillRefreshInFlight;
  } finally {
    skillRefreshInFlight = null;
  }
}


const TRADE_PROFILES = {
  mikechong: { prefix: "skill", expected: "MikeChong" },
  ladyguagua: { prefix: "mail", expected: "LadyGuaGua" },
  ladybaba: { prefix: "cj", expected: "LadyBaBa" },
};

async function handleTradeData(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;
  if (!env.AUTH_STORE) return json({ ok: false, error: "auth_store_missing" }, 500);

  const url = new URL(request.url);
  const profileName = String(url.searchParams.get("profile") || "").toLowerCase();
  const resource = String(url.searchParams.get("resource") || "").toLowerCase();
  const profile = TRADE_PROFILES[profileName];
  if (!profile) return json({ ok: false, error: "unknown_profile" }, 400);

  const prefix = profile.prefix;
  const characterId = Number(await env.AUTH_STORE.get(prefix + "_character_id") || 0);
  const characterName = await env.AUTH_STORE.get(prefix + "_character_name") || "";
  const refreshToken = await env.AUTH_STORE.get(prefix + "_refresh_token");
  if (!characterId || !refreshToken) {
    return json({ ok: false, error: "trade_profile_not_authorized", profile: profileName }, 409);
  }
  if (String(characterName).toLowerCase() !== profile.expected.toLowerCase()) {
    return json({ ok: false, error: "trade_profile_character_mismatch", profile: profileName, character_name: characterName }, 409);
  }

  const refreshed = await tokenRequest(env, new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
  }));
  if (!refreshed.ok) {
    return json({ ok: false, error: "trade_token_refresh_failed", profile: profileName, detail: refreshed.detail || refreshed.status }, 502);
  }

  if (refreshed.refresh_token && refreshed.refresh_token !== refreshToken) {
    try {
      await env.AUTH_STORE.put(prefix + "_refresh_token", refreshed.refresh_token);
    } catch (err) {
      console.warn("trade refresh token persistence failed", profileName, String(err));
    }
  }

  const pageRaw = Number(url.searchParams.get("page") || 1);
  const page = Number.isFinite(pageRaw) ? Math.max(1, Math.min(5000, Math.trunc(pageRaw))) : 1;
  const fromIdRaw = Number(url.searchParams.get("from_id") || 0);
  const fromId = Number.isFinite(fromIdRaw) ? Math.max(0, Math.trunc(fromIdRaw)) : 0;
  const contractIdRaw = Number(url.searchParams.get("contract_id") || 0);
  const contractId = Number.isFinite(contractIdRaw) ? Math.max(0, Math.trunc(contractIdRaw)) : 0;

  let endpoint = "";
  if (resource === "transactions") {
    endpoint = `${ESI_BASE}/characters/${characterId}/wallet/transactions/?datasource=tranquility`;
    if (fromId > 0) endpoint += `&from_id=${fromId}`;
  } else if (resource === "journal") {
    endpoint = `${ESI_BASE}/characters/${characterId}/wallet/journal/?datasource=tranquility&page=${page}`;
  } else if (resource === "orders") {
    endpoint = `${ESI_BASE}/characters/${characterId}/orders/?datasource=tranquility`;
  } else if (resource === "orders-history") {
    endpoint = `${ESI_BASE}/characters/${characterId}/orders/history/?datasource=tranquility&page=${page}`;
  } else if (resource === "contracts") {
    endpoint = `${ESI_BASE}/characters/${characterId}/contracts/?datasource=tranquility&page=${page}`;
  } else if (resource === "contract-items") {
    if (!contractId) return json({ ok: false, error: "contract_id_required" }, 400);
    endpoint = `${ESI_BASE}/characters/${characterId}/contracts/${contractId}/items/?datasource=tranquility&page=${page}`;
  } else if (resource === "assets") {
    endpoint = `${ESI_BASE}/characters/${characterId}/assets/?datasource=tranquility&page=${page}`;
  } else {
    return json({ ok: false, error: "unknown_resource" }, 400);
  }

  const resp = await fetch(endpoint, {
    headers: {
      Authorization: `Bearer ${refreshed.access_token}`,
      Accept: "application/json",
      "User-Agent": "samson8964-chatgpt-eve-trade-audit/1.0",
    },
  });
  const body = await resp.text();
  if (resp.status !== 200) {
    return json({ ok: false, error: "esi_trade_read_failed", profile: profileName, resource, status: resp.status, detail: body }, 502);
  }

  let data;
  try { data = JSON.parse(body); }
  catch { return json({ ok: false, error: "invalid_esi_json", profile: profileName, resource }, 502); }

  return json({
    ok: true,
    profile: profileName,
    character_id: characterId,
    character_name: characterName,
    resource,
    page,
    pages: Number(resp.headers.get("X-Pages") || 1),
    data,
  });
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
