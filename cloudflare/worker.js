const SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize";
const SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token";
const ESI_BASE = "https://esi.evetech.net/latest";
const SCOPE = "esi-ui.open_window.v1";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!env.EVE_CLIENT_ID || !env.EVE_CLIENT_SECRET || !env.EVE_REDIRECT_URI) {
      return text("Worker 未配置完成：缺少 EVE_CLIENT_ID / EVE_CLIENT_SECRET / EVE_REDIRECT_URI。", 500);
    }
    if (!env.AUTH_STORE) {
      return text("Worker 未绑定 KV：请创建 KV namespace，并绑定为 AUTH_STORE。", 500);
    }

    if (url.pathname === "/" || url.pathname === "/health") {
      const hasToken = Boolean(await env.AUTH_STORE.get("refresh_token"));
      return html(`<!doctype html><meta charset="utf-8"><title>EVE Contract Opener</title>
        <style>body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.65}code{background:#eee;padding:2px 6px;border-radius:5px}</style>
        <h1>EVE Contract Opener</h1>
        <p>状态：<b>${hasToken ? "已授权" : "尚未授权"}</b></p>
        <p>打开合同：<code>/c/合同ID</code></p>
        <p>打开市场：<code>/m/物品Type ID</code></p>
        <p><a href="/auth">${hasToken ? "重新授权角色" : "授权 EVE 角色"}</a> · <a href="/logout">清除授权</a></p>`);
    }

    if (url.pathname === "/logout") {
      await env.AUTH_STORE.delete("refresh_token");
      return html("<!doctype html><meta charset='utf-8'><h2>已清除 EVE 授权。</h2><p><a href='/'>返回</a></p>");
    }

    if (url.pathname === "/auth") {
      return startAuth(env, null);
    }

    if (url.pathname === "/callback") {
      return handleCallback(request, env);
    }

    const contractMatch = url.pathname.match(/^\/c\/(\d+)\/?$/);
    if (contractMatch) {
      return handleOpen(request, env, `contract:${contractMatch[1]}`);
    }

    const marketMatch = url.pathname.match(/^\/m\/(\d+)\/?$/);
    if (marketMatch) {
      return handleOpen(request, env, `market:${marketMatch[1]}`);
    }

    return text("Not found", 404);
  },
};

async function handleOpen(request, env, action) {
  const refreshToken = await env.AUTH_STORE.get("refresh_token");
  if (!refreshToken) return startAuth(env, action);

  const tokenResult = await refreshAccessToken(env, refreshToken);
  if (!tokenResult.ok) {
    await env.AUTH_STORE.delete("refresh_token");
    return startAuth(env, action);
  }

  if (tokenResult.refresh_token && tokenResult.refresh_token !== refreshToken) {
    await env.AUTH_STORE.put("refresh_token", tokenResult.refresh_token);
  }

  return openInEve(tokenResult.access_token, action);
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
    return text("EVE SSO 回调校验失败：state 不匹配。请重新打开授权链接。", 400);
  }

  const basic = btoa(`${env.EVE_CLIENT_ID}:${env.EVE_CLIENT_SECRET}`);
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
  });
  const resp = await fetch(SSO_TOKEN, {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
    body,
  });

  if (!resp.ok) {
    const detail = await resp.text();
    return text(`EVE SSO token exchange failed (${resp.status}): ${detail}`, 502);
  }

  const data = await resp.json();
  if (!data.refresh_token || !data.access_token) {
    return text("EVE SSO 未返回 refresh_token/access_token。", 502);
  }

  await env.AUTH_STORE.put("refresh_token", data.refresh_token);

  const action = cookies.eve_action || null;
  if (action) return openInEve(data.access_token, action, true);

  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  headers.append("Set-Cookie", expiredCookie("eve_state"));
  headers.append("Set-Cookie", expiredCookie("eve_action"));
  return new Response("<!doctype html><meta charset='utf-8'><h2>EVE 授权成功。</h2><p>以后直接点击合同链接即可。</p><p><a href='/'>返回状态页</a></p>", { status: 200, headers });
}

async function refreshAccessToken(env, refreshToken) {
  const basic = btoa(`${env.EVE_CLIENT_ID}:${env.EVE_CLIENT_SECRET}`);
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
  });
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
  const data = await resp.json();
  return { ok: true, ...data };
}

async function openInEve(accessToken, action, clearCookies = false) {
  const [kind, rawId] = action.split(":", 2);
  if (!/^\d+$/.test(rawId || "")) return text("Invalid action", 400);

  let endpoint;
  let label;
  if (kind === "contract") {
    endpoint = `${ESI_BASE}/ui/openwindow/contract/?datasource=tranquility&contract_id=${encodeURIComponent(rawId)}`;
    label = `合同 ${rawId}`;
  } else if (kind === "market") {
    endpoint = `${ESI_BASE}/ui/openwindow/marketdetails/?datasource=tranquility&type_id=${encodeURIComponent(rawId)}`;
    label = `市场 ${rawId}`;
  } else {
    return text("Unknown action", 400);
  }

  const resp = await fetch(endpoint, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      Accept: "application/json",
    },
  });

  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  if (clearCookies) {
    headers.append("Set-Cookie", expiredCookie("eve_state"));
    headers.append("Set-Cookie", expiredCookie("eve_action"));
  }

  if (resp.status === 204) {
    return new Response(`<!doctype html><meta charset="utf-8"><title>EVE</title>
      <style>body{font:18px system-ui;max-width:620px;margin:60px auto;padding:0 20px;line-height:1.6}</style>
      <h2>已发送到 EVE 客户端</h2><p>${escapeHtml(label)} 应已在当前登录角色的客户端中打开。</p>
      <p>如果没有弹窗，请确认授权的角色正在游戏里在线。</p>`, { status: 200, headers });
  }

  const detail = await resp.text();
  return new Response(`<!doctype html><meta charset="utf-8"><h2>EVE ESI 打开窗口失败</h2><p>HTTP ${resp.status}</p><pre>${escapeHtml(detail)}</pre>`, { status: 502, headers });
}

function parseCookies(raw) {
  const out = {};
  for (const part of raw.split(";")) {
    const idx = part.indexOf("=");
    if (idx < 0) continue;
    out[part.slice(0, idx).trim()] = decodeURIComponent(part.slice(idx + 1).trim());
  }
  return out;
}

function cookie(name, value, maxAge) {
  return `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Lax`;
}

function expiredCookie(name) {
  return `${name}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;
}

function randomHex(bytes) {
  const a = new Uint8Array(bytes);
  crypto.getRandomValues(a);
  return [...a].map(x => x.toString(16).padStart(2, "0")).join("");
}

function text(body, status = 200) {
  return new Response(body, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}

function html(body, status = 200) {
  return new Response(body, { status, headers: { "Content-Type": "text/html; charset=utf-8" } });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
