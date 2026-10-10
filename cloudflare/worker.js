const SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize";
const SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token";
const ESI_BASE = "https://esi.evetech.net/latest";
const ESI_SKILLS_BASE = "https://esi.evetech.net/v4";
const SCOPE = "esi-ui.open_window.v1 esi-mail.send_mail.v1 esi-skills.read_skills.v1 esi-markets.structure_markets.v1";
const ACCESS_TOKEN_CACHE_KEY = "https://eve-contract-opener.internal/access-token";
const CJ_MARKET_SCOPE = "esi-markets.structure_markets.v1 esi-wallet.read_character_wallet.v1 esi-markets.read_character_orders.v1 esi-contracts.read_character_contracts.v1 esi-assets.read_assets.v1";
const CJ_ACCESS_TOKEN_CACHE_KEY = "https://eve-contract-opener.internal/cj-market-access-token";
const DC_MARKET_SCOPE = "esi-markets.structure_markets.v1 esi-search.search_structures.v1";
const DC_ACCESS_TOKEN_CACHE_KEY = "https://eve-contract-opener.internal/dc-market-access-token";

let memoryAccessToken = "";
let memoryAccessTokenExp = 0;
let refreshInFlight = null;
let memoryCjAccessToken = "";
let memoryCjAccessTokenExp = 0;
let cjRefreshInFlight = null;
let memoryDcAccessToken = "";
let memoryDcAccessTokenExp = 0;
let dcRefreshInFlight = null;

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
      const cjHasToken = Boolean(await env.AUTH_STORE.get("cj_refresh_token"));
      const cjName = await env.AUTH_STORE.get("cj_character_name");
      const cjId = await env.AUTH_STORE.get("cj_character_id");
      const dcHasToken = Boolean(await env.AUTH_STORE.get("dc_refresh_token"));
      const dcName = await env.AUTH_STORE.get("dc_character_name");
      const dcId = await env.AUTH_STORE.get("dc_character_id");
      return html(`<!doctype html><meta charset="utf-8"><title>EVE Contract Opener</title>
        <style>body{font:16px system-ui;max-width:760px;margin:48px auto;padding:0 20px;line-height:1.65}code{background:#eee;padding:2px 6px;border-radius:5px}</style>
        <h1>EVE Contract Opener</h1>
        <p>状态：<b>${hasToken ? "已授权" : "尚未授权"}</b>${name ? ` · ${escapeHtml(name)} (${escapeHtml(id || "")})` : ""}</p>
        <p>权限：<code>${escapeHtml(SCOPE)}</code></p>
        <p>技能读取接口：<code>/api/skills</code>（需要 API Key）</p>
        <p>建筑市场接口：<code>/api/structure-market?structure_id=1053970513596&page=1</code>（需要 API Key）</p>
        <p>C-J6MT市场授权：<b>${cjHasToken ? "已授权" : "尚未授权"}</b>${cjName ? ` · ${escapeHtml(cjName)} (${escapeHtml(cjId || "")})` : ""} · <a href="/auth-cj">授权/更换</a> · <a href="/logout-cj">清除</a></p>
        <p>C-J6MT接口使用 <code>auth_profile=cj</code>，与原4-H主授权彼此独立。</p>
        <p>DC影子市场授权：<b>${dcHasToken ? "已授权" : "尚未授权"}</b>${dcName ? ` · ${escapeHtml(dcName)} (${escapeHtml(dcId || "")})` : ""} · <a href="/auth-dc">授权/更换</a> · <a href="/logout-dc">清除</a></p>
        <p>DC接口使用 <code>auth_profile=dc</code>；只用于TCAG-3 / O4T-Z5影子扫描，不影响4-H、C-J6MT和邮件角色。</p>
        <p>打开合同：<code>/c/合同ID</code></p>
        <p>打开市场：<code>/m/物品Type ID</code></p>
        <p><a href="/auth">重新授权角色</a> · <a href="/logout">清除授权</a></p>`);
    }

    if (url.pathname === "/logout") {
      memoryAccessToken = "";
      memoryAccessTokenExp = 0;
      await Promise.all(["refresh_token","character_id","character_name"].map(k => env.AUTH_STORE.delete(k)));
      return html("<!doctype html><meta charset='utf-8'><h2>已清除 EVE 授权。</h2><p><a href='/'>返回</a></p>");
    }
    if (url.pathname === "/auth") return startAuth(env, null);
    if (url.pathname === "/auth-cj") return startCjAuth(env);
    if (url.pathname === "/logout-cj") return logoutCjAuth(env);
    if (url.pathname === "/auth-dc") return startDcAuth(env);
    if (url.pathname === "/logout-dc") return logoutDcAuth(env);
    if (url.pathname === "/callback") {
      const cookies = parseCookies(request.headers.get("Cookie") || "");
      if (cookies.eve_dc_state) return handleDcCallback(request, env, cookies);
      if (cookies.eve_cj_state) return handleCjCallback(request, env, cookies);
      return handleCallback(request, env);
    }
    if (url.pathname === "/api/skills") return handleSkills(request, env);
    if (url.pathname === "/api/structure-market") return handleStructureMarket(request, env);
    if (url.pathname === "/api/structure-search") return handleStructureSearch(request, env);
    if (url.pathname === "/api/send-mail") return handleSendMail(request, env);

    const contractMatch = url.pathname.match(/^\/c\/(\d+)\/?$/);
    if (contractMatch) return handleOpen(env, `contract:${contractMatch[1]}`);
    const marketMatch = url.pathname.match(/^\/m\/(\d+)\/?$/);
    if (marketMatch) return handleOpen(env, `market:${marketMatch[1]}`);
    return text("Not found", 404);
  },
};

function requireApiKey(request, env) {
  if (!env.MAIL_API_KEY) return text("缺少 Cloudflare Secret：MAIL_API_KEY", 500);
  const auth = request.headers.get("Authorization") || "";
  if (auth !== `Bearer ${env.MAIL_API_KEY}`) return text("Unauthorized", 401);
  return null;
}

async function handleSkills(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;

  const characterId = Number(await env.AUTH_STORE.get("character_id") || 0);
  const characterName = await env.AUTH_STORE.get("character_name") || "unknown";
  if (!Number.isSafeInteger(characterId) || characterId <= 0) {
    return json({ ok: false, error: "not_authorized", auth_url: "/auth" }, 401);
  }

  const token = await getFreshToken(env);
  if (!token.ok) {
    return json({ ok: false, error: "token_refresh_failed", detail: token.detail || token.status, auth_url: "/auth" }, 401);
  }

  const resp = await fetch(`${ESI_SKILLS_BASE}/characters/${characterId}/skills/?datasource=tranquility`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token.access_token}`,
      Accept: "application/json",
    },
  });
  const detail = await resp.text();
  if (resp.status !== 200) {
    const missingScope = resp.status === 403;
    return json({
      ok: false,
      error: missingScope ? "missing_scope" : "esi_error",
      status: resp.status,
      detail,
      auth_url: "/auth",
    }, missingScope ? 403 : 502);
  }

  let data;
  try { data = JSON.parse(detail); } catch { return text("EVE skills returned invalid JSON", 502); }
  const totalSp = Number(data.total_sp || 0);
  const unallocatedSp = Number(data.unallocated_sp || 0);
  const skills = Array.isArray(data.skills) ? data.skills : [];
  const trainedSkills = skills.filter(s => Number(s.trained_skill_level || 0) > 0).length;
  const level5Skills = skills.filter(s => Number(s.trained_skill_level || 0) >= 5).length;

  return json({
    ok: true,
    character_id: characterId,
    character_name: characterName,
    total_sp: totalSp,
    unallocated_sp: unallocatedSp,
    allocated_sp: Math.max(0, totalSp - unallocatedSp),
    skills_count: skills.length,
    trained_skills_count: trainedSkills,
    level_5_skills_count: level5Skills,
    skills,
  });
}

async function handleStructureMarket(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;

  const url = new URL(request.url);
  const structureId = Number(url.searchParams.get("structure_id") || "1053970513596");
  const page = Number(url.searchParams.get("page") || "1");
  const authProfile = String(url.searchParams.get("auth_profile") || "main").trim().toLowerCase();
  if (!Number.isSafeInteger(structureId) || structureId <= 0 || !Number.isSafeInteger(page) || page < 1) {
    return json({ ok: false, error: "invalid_structure_id_or_page" }, 400);
  }
  if (!["main", "cj", "dc"].includes(authProfile)) {
    return json({ ok: false, error: "invalid_auth_profile", auth_profile: authProfile }, 400);
  }

  const token = authProfile === "dc" ? await getFreshDcToken(env) : authProfile === "cj" ? await getFreshCjToken(env) : await getFreshToken(env);
  const authUrl = authProfile === "dc" ? "/auth-dc" : authProfile === "cj" ? "/auth-cj" : "/auth";
  if (!token.ok) {
    return json({ ok: false, error: "token_refresh_failed", detail: token.detail || token.status, auth_profile: authProfile, auth_url: authUrl }, 401);
  }

  const resp = await fetch(`${ESI_BASE}/markets/structures/${structureId}/?datasource=tranquility&page=${page}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${token.access_token}`, Accept: "application/json" },
  });
  const detail = await resp.text();
  if (resp.status !== 200) {
    return json({
      ok: false,
      error: resp.status === 403 ? "missing_scope_or_structure_access" : "esi_error",
      status: resp.status,
      detail,
      structure_id: structureId,
      page,
      auth_profile: authProfile,
      auth_url: authUrl,
    }, resp.status === 403 ? 403 : 502);
  }

  let orders;
  try { orders = JSON.parse(detail); } catch { return text("EVE structure market returned invalid JSON", 502); }
  return json({
    ok: true,
    structure_id: structureId,
    auth_profile: authProfile,
    page,
    pages: Math.max(1, Number(resp.headers.get("X-Pages") || 1)),
    expires: resp.headers.get("Expires") || null,
    orders: Array.isArray(orders) ? orders : [],
  });
}

async function handleStructureSearch(request, env) {
  if (request.method !== "GET") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;

  const url = new URL(request.url);
  const query = String(url.searchParams.get("q") || "").trim();
  const authProfile = String(url.searchParams.get("auth_profile") || "dc").trim().toLowerCase();
  if (!query) return json({ ok: false, error: "missing_query" }, 400);
  if (authProfile !== "dc") {
    return json({ ok: false, error: "structure_search_requires_dc_profile", auth_profile: authProfile }, 400);
  }

  const characterId = Number(await env.AUTH_STORE.get("dc_character_id") || 0);
  if (!Number.isSafeInteger(characterId) || characterId <= 0) {
    return json({ ok: false, error: "not_authorized", auth_profile: "dc", auth_url: "/auth-dc" }, 401);
  }

  const token = await getFreshDcToken(env);
  if (!token.ok) {
    return json({ ok: false, error: "token_refresh_failed", detail: token.detail || token.status, auth_profile: "dc", auth_url: "/auth-dc" }, 401);
  }

  const upper = query.toUpperCase();
  const regionId = upper.includes("TCAG-3") ? 10000063 : upper.includes("O4T-Z5") ? 10000059 : 0;
  if (!regionId) {
    return json({ ok: false, error: "unsupported_dc_structure_query", query }, 400);
  }

  // First try the authenticated structure-search endpoint with the market token.
  // Some current ESI deployments allow the endpoint even though requesting the
  // legacy search scope through SSO is rejected for this application.
  let searchStatus = 0;
  let directIds = [];
  try {
    const su = new URL(`${ESI_BASE}/characters/${characterId}/search/`);
    su.searchParams.set("categories", "structure");
    su.searchParams.set("datasource", "tranquility");
    su.searchParams.set("language", "en");
    su.searchParams.set("search", query);
    su.searchParams.set("strict", "false");
    const sr = await fetch(su, { headers: { Authorization: `Bearer ${token.access_token}`, Accept: "application/json" } });
    searchStatus = sr.status;
    if (sr.status === 200) {
      const payload = await sr.json();
      directIds = Array.isArray(payload.structure) ? payload.structure.map(Number).filter(Number.isSafeInteger) : [];
    }
  } catch {}

  const counts = new Map();
  if (!directIds.length) {
    // Fallback: mine public regional contracts for candidate Upwell location IDs.
    let pages = 1;
    for (let page = 1; page <= pages; page++) {
      const cr = await fetch(`${ESI_BASE}/contracts/public/${regionId}/?datasource=tranquility&page=${page}`, {
        headers: { Accept: "application/json" },
      });
      if (cr.status !== 200) {
        const detail = await cr.text();
        return json({ ok: false, error: "public_contracts_error", status: cr.status, detail, region_id: regionId }, 502);
      }
      pages = Math.max(1, Number(cr.headers.get("X-Pages") || 1));
      let rows = [];
      try { rows = await cr.json(); } catch { return text("EVE public contracts returned invalid JSON", 502); }
      for (const row of Array.isArray(rows) ? rows : []) {
        for (const raw of [row.start_location_id, row.end_location_id]) {
          const sid = Number(raw || 0);
          if (!Number.isSafeInteger(sid) || sid < 1000000000000) continue;
          counts.set(sid, (counts.get(sid) || 0) + 1);
        }
      }
    }
  }

  const candidateIds = directIds.length
    ? [...new Set(directIds)]
    : [...counts.entries()].sort((a,b) => b[1] - a[1]).slice(0, 160).map(([sid]) => sid);

  const structures = [];
  for (const structureId of candidateIds.slice(0, 100)) {
    let name = "";
    let solarSystemId = 0;
    let typeId = 0;
    let metadataStatus = 0;

    const rr = await fetch(`${ESI_BASE}/universe/structures/${structureId}/?datasource=tranquility`, {
      headers: { Authorization: `Bearer ${token.access_token}`, Accept: "application/json" },
    });
    metadataStatus = rr.status;
    if (rr.status === 200) {
      try {
        const info = await rr.json();
        name = String(info.name || "");
        solarSystemId = Number(info.solar_system_id || 0);
        typeId = Number(info.type_id || 0);
      } catch {}
    }

    const mr = await fetch(`${ESI_BASE}/markets/structures/${structureId}/?datasource=tranquility&page=1`, {
      headers: { Authorization: `Bearer ${token.access_token}`, Accept: "application/json" },
    });
    if (mr.status !== 200) continue;

    let orders = [];
    try { orders = await mr.json(); } catch {}
    structures.push({
      structure_id: structureId,
      name,
      solar_system_id: solarSystemId,
      type_id: typeId,
      metadata_status: metadataStatus,
      market_pages: Math.max(1, Number(mr.headers.get("X-Pages") || 1)),
      page1_orders: Array.isArray(orders) ? orders.length : 0,
      contract_mentions: Number(counts.get(structureId) || 0),
    });
  }

  structures.sort((a,b) =>
    (b.market_pages - a.market_pages) ||
    (b.page1_orders - a.page1_orders) ||
    (b.contract_mentions - a.contract_mentions)
  );

  return json({
    ok: true,
    auth_profile: "dc",
    query,
    region_id: regionId,
    search_status: searchStatus,
    direct_search_ids: directIds.length,
    candidate_count: candidateIds.length,
    structures
  });
}

async function handleOpen(env, action) {
  const token = await getFreshToken(env);
  if (!token.ok) return startAuth(env, action);
  return openInEve(token.access_token, action);
}

async function handleSendMail(request, env) {
  if (request.method !== "POST") return text("Method not allowed", 405);
  const denied = requireApiKey(request, env);
  if (denied) return denied;

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

function startCjAuth(env) {
  const state = randomHex(24);
  const authUrl = new URL(SSO_AUTHORIZE);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("client_id", env.EVE_CLIENT_ID);
  authUrl.searchParams.set("redirect_uri", env.EVE_REDIRECT_URI);
  authUrl.searchParams.set("scope", CJ_MARKET_SCOPE);
  authUrl.searchParams.set("state", state);
  const headers = new Headers({ Location: authUrl.toString() });
  headers.append("Set-Cookie", cookie("eve_cj_state", state, 600));
  return new Response(null, { status: 302, headers });
}

async function logoutCjAuth(env) {
  memoryCjAccessToken = "";
  memoryCjAccessTokenExp = 0;
  await Promise.all(["cj_refresh_token", "cj_character_id", "cj_character_name"].map(k => env.AUTH_STORE.delete(k)));
  return html("<!doctype html><meta charset='utf-8'><h2>已清除 C-J6MT 市场授权。</h2><p><a href='/auth-cj'>重新授权 C-J6MT 角色</a> · <a href='/'>返回</a></p>");
}

async function handleCjCallback(request, env, cookies) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  if (!code || !returnedState || !cookies.eve_cj_state || returnedState !== cookies.eve_cj_state) {
    return text("C-J6MT EVE SSO 回调校验失败：state 不匹配。", 400);
  }

  const resp = await tokenRequest(env, new URLSearchParams({ grant_type: "authorization_code", code }));
  if (!resp.ok) return text(`C-J6MT EVE SSO token exchange failed (${resp.status}): ${resp.detail}`, 502);

  const claims = decodeJwtClaims(resp.access_token);
  const characterId = String(claims.sub || "").split(":").pop();
  if (!/^\d+$/.test(characterId || "")) return text("无法识别 C-J6MT 授权角色 ID。", 502);

  await env.AUTH_STORE.put("cj_refresh_token", resp.refresh_token);
  await env.AUTH_STORE.put("cj_character_id", characterId);
  if (claims.name) await env.AUTH_STORE.put("cj_character_name", String(claims.name));
  rememberCjAccessToken(resp.access_token, claims);
  await cacheCjAccessToken(resp.access_token, claims);

  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  headers.append("Set-Cookie", expiredCookie("eve_cj_state"));
  return new Response(
    `<!doctype html><meta charset='utf-8'><h2>C-J6MT 市场授权成功</h2><p>角色：${escapeHtml(claims.name || characterId)}</p><p>权限：<code>${escapeHtml(CJ_MARKET_SCOPE)}</code></p><p><a href='/'>返回状态页</a></p>`,
    { status: 200, headers }
  );
}

function startDcAuth(env) {
  const state = randomHex(24);
  const authUrl = new URL(SSO_AUTHORIZE);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("client_id", env.EVE_CLIENT_ID);
  authUrl.searchParams.set("redirect_uri", env.EVE_REDIRECT_URI);
  authUrl.searchParams.set("scope", DC_MARKET_SCOPE);
  authUrl.searchParams.set("state", state);
  const headers = new Headers({ Location: authUrl.toString() });
  headers.append("Set-Cookie", cookie("eve_dc_state", state, 600));
  return new Response(null, { status: 302, headers });
}

async function logoutDcAuth(env) {
  memoryDcAccessToken = "";
  memoryDcAccessTokenExp = 0;
  await Promise.all(["dc_refresh_token", "dc_character_id", "dc_character_name"].map(k => env.AUTH_STORE.delete(k)));
  return html("<!doctype html><meta charset='utf-8'><h2>已清除 DC 影子市场授权。</h2><p><a href='/auth-dc'>重新授权 LadyBaBa / DC访问角色</a> · <a href='/'>返回</a></p>");
}

async function handleDcCallback(request, env, cookies) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const returnedState = url.searchParams.get("state");
  if (!code || !returnedState || !cookies.eve_dc_state || returnedState !== cookies.eve_dc_state) {
    return text("DC EVE SSO 回调校验失败：state 不匹配。", 400);
  }

  const resp = await tokenRequest(env, new URLSearchParams({ grant_type: "authorization_code", code }));
  if (!resp.ok) return text(`DC EVE SSO token exchange failed (${resp.status}): ${resp.detail}`, 502);

  const claims = decodeJwtClaims(resp.access_token);
  const characterId = String(claims.sub || "").split(":").pop();
  if (!/^\d+$/.test(characterId || "")) return text("无法识别 DC 授权角色 ID。", 502);

  await env.AUTH_STORE.put("dc_refresh_token", resp.refresh_token);
  await env.AUTH_STORE.put("dc_character_id", characterId);
  if (claims.name) await env.AUTH_STORE.put("dc_character_name", String(claims.name));
  rememberDcAccessToken(resp.access_token, claims);
  await cacheDcAccessToken(resp.access_token, claims);

  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  headers.append("Set-Cookie", expiredCookie("eve_dc_state"));
  return new Response(
    `<!doctype html><meta charset='utf-8'><h2>DC 影子市场授权成功</h2><p>角色：${escapeHtml(claims.name || characterId)}</p><p>权限：<code>${escapeHtml(DC_MARKET_SCOPE)}</code></p><p><a href='/'>返回状态页</a></p>`,
    { status: 200, headers }
  );
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
  rememberAccessToken(resp.access_token, claims);
  await cacheAccessToken(resp.access_token, claims);

  const action = cookies.eve_action || null;
  if (action) return openInEve(resp.access_token, action, true);
  const headers = new Headers({ "Content-Type": "text/html; charset=utf-8" });
  headers.append("Set-Cookie", expiredCookie("eve_state"));
  headers.append("Set-Cookie", expiredCookie("eve_action"));
  return new Response(`<!doctype html><meta charset='utf-8'><h2>EVE 授权成功。</h2><p>角色：${escapeHtml(claims.name || characterId || "unknown")}</p><p>已申请合同窗口 + 发送邮件 + 读取技能 + 玩家建筑市场权限。</p><p><a href='/'>返回状态页</a></p>`, { status: 200, headers });
}

function rememberAccessToken(accessToken, claims = {}) {
  const nowSec = Math.floor(Date.now() / 1000);
  memoryAccessToken = accessToken || "";
  memoryAccessTokenExp = Number(claims.exp || 0) || (nowSec + 900);
}

async function readCachedAccessToken() {
  const nowSec = Math.floor(Date.now() / 1000);
  if (memoryAccessToken && memoryAccessTokenExp > nowSec + 60) {
    return { ok: true, access_token: memoryAccessToken, cached: "memory" };
  }
  try {
    const cached = await caches.default.match(ACCESS_TOKEN_CACHE_KEY);
    if (!cached) return null;
    const data = await cached.json();
    if (!data || !data.access_token || Number(data.exp || 0) <= nowSec + 60) return null;
    memoryAccessToken = String(data.access_token);
    memoryAccessTokenExp = Number(data.exp);
    return { ok: true, access_token: memoryAccessToken, cached: "edge" };
  } catch (err) {
    console.warn("access token cache read failed", String(err));
    return null;
  }
}

async function cacheAccessToken(accessToken, claims = {}) {
  if (!accessToken) return;
  const nowSec = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp || 0) || (nowSec + 900);
  const ttl = Math.max(60, Math.min(1100, exp - nowSec - 60));
  try {
    const response = new Response(JSON.stringify({ access_token: accessToken, exp }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": `public, max-age=${ttl}`,
      },
    });
    await caches.default.put(ACCESS_TOKEN_CACHE_KEY, response);
  } catch (err) {
    console.warn("access token cache write failed", String(err));
  }
}

async function refreshAccessToken(env) {
  const refreshToken = await env.AUTH_STORE.get("refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no refresh token" };

  let result;
  try {
    result = await tokenRequest(env, new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken }));
  } catch (err) {
    return { ok: false, status: 502, detail: `token request exception: ${String(err)}` };
  }
  if (!result.ok) return result;

  const claims = decodeJwtClaims(result.access_token);
  rememberAccessToken(result.access_token, claims);
  await cacheAccessToken(result.access_token, claims);

  if (result.refresh_token && result.refresh_token !== refreshToken) {
    try {
      await env.AUTH_STORE.put("refresh_token", result.refresh_token);
    } catch (err) {
      // KV free-tier write exhaustion must not crash all market scans. The current
      // access token remains usable; a later /auth can restore persistence if needed.
      console.warn("refresh token persistence failed", String(err));
    }
  }

  // character_id/name are written during /auth callback only. Rewriting them on
  // every market page previously burned KV writes without changing the values.
  return result;
}

async function getFreshToken(env) {
  const cached = await readCachedAccessToken();
  if (cached) return cached;

  if (!refreshInFlight) refreshInFlight = refreshAccessToken(env);
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

function rememberCjAccessToken(accessToken, claims = {}) {
  const nowSec = Math.floor(Date.now() / 1000);
  memoryCjAccessToken = accessToken || "";
  memoryCjAccessTokenExp = Number(claims.exp || 0) || (nowSec + 900);
}

async function readCachedCjAccessToken() {
  const nowSec = Math.floor(Date.now() / 1000);
  if (memoryCjAccessToken && memoryCjAccessTokenExp > nowSec + 60) {
    return { ok: true, access_token: memoryCjAccessToken, cached: "memory" };
  }
  try {
    const cached = await caches.default.match(CJ_ACCESS_TOKEN_CACHE_KEY);
    if (!cached) return null;
    const data = await cached.json();
    if (!data || !data.access_token || Number(data.exp || 0) <= nowSec + 60) return null;
    memoryCjAccessToken = String(data.access_token);
    memoryCjAccessTokenExp = Number(data.exp);
    return { ok: true, access_token: memoryCjAccessToken, cached: "edge" };
  } catch (err) {
    console.warn("C-J access token cache read failed", String(err));
    return null;
  }
}

async function cacheCjAccessToken(accessToken, claims = {}) {
  if (!accessToken) return;
  const nowSec = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp || 0) || (nowSec + 900);
  const ttl = Math.max(60, Math.min(1100, exp - nowSec - 60));
  try {
    const response = new Response(JSON.stringify({ access_token: accessToken, exp }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": `public, max-age=${ttl}`,
      },
    });
    await caches.default.put(CJ_ACCESS_TOKEN_CACHE_KEY, response);
  } catch (err) {
    console.warn("C-J access token cache write failed", String(err));
  }
}

async function refreshCjAccessToken(env) {
  const refreshToken = await env.AUTH_STORE.get("cj_refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no C-J refresh token" };

  let result;
  try {
    result = await tokenRequest(env, new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken }));
  } catch (err) {
    return { ok: false, status: 502, detail: `C-J token request exception: ${String(err)}` };
  }
  if (!result.ok) return result;

  const claims = decodeJwtClaims(result.access_token);
  rememberCjAccessToken(result.access_token, claims);
  await cacheCjAccessToken(result.access_token, claims);

  if (result.refresh_token && result.refresh_token !== refreshToken) {
    try {
      await env.AUTH_STORE.put("cj_refresh_token", result.refresh_token);
    } catch (err) {
      console.warn("C-J refresh token persistence failed", String(err));
    }
  }
  return result;
}

async function getFreshCjToken(env) {
  const cached = await readCachedCjAccessToken();
  if (cached) return cached;

  if (!cjRefreshInFlight) cjRefreshInFlight = refreshCjAccessToken(env);
  try {
    return await cjRefreshInFlight;
  } finally {
    cjRefreshInFlight = null;
  }
}

function rememberDcAccessToken(accessToken, claims = {}) {
  const nowSec = Math.floor(Date.now() / 1000);
  memoryDcAccessToken = accessToken || "";
  memoryDcAccessTokenExp = Number(claims.exp || 0) || (nowSec + 900);
}

async function readCachedDcAccessToken() {
  const nowSec = Math.floor(Date.now() / 1000);
  if (memoryDcAccessToken && memoryDcAccessTokenExp > nowSec + 60) {
    return { ok: true, access_token: memoryDcAccessToken, cached: "memory" };
  }
  try {
    const cached = await caches.default.match(DC_ACCESS_TOKEN_CACHE_KEY);
    if (!cached) return null;
    const data = await cached.json();
    if (!data || !data.access_token || Number(data.exp || 0) <= nowSec + 60) return null;
    memoryDcAccessToken = String(data.access_token);
    memoryDcAccessTokenExp = Number(data.exp);
    return { ok: true, access_token: memoryDcAccessToken, cached: "edge" };
  } catch (err) {
    console.warn("DC access token cache read failed", String(err));
    return null;
  }
}

async function cacheDcAccessToken(accessToken, claims = {}) {
  if (!accessToken) return;
  const nowSec = Math.floor(Date.now() / 1000);
  const exp = Number(claims.exp || 0) || (nowSec + 900);
  const ttl = Math.max(60, Math.min(1100, exp - nowSec - 60));
  try {
    const response = new Response(JSON.stringify({ access_token: accessToken, exp }), {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": `public, max-age=${ttl}`,
      },
    });
    await caches.default.put(DC_ACCESS_TOKEN_CACHE_KEY, response);
  } catch (err) {
    console.warn("DC access token cache write failed", String(err));
  }
}

async function refreshDcAccessToken(env) {
  const refreshToken = await env.AUTH_STORE.get("dc_refresh_token");
  if (!refreshToken) return { ok: false, status: 401, detail: "no DC refresh token" };

  let result;
  try {
    result = await tokenRequest(env, new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken }));
  } catch (err) {
    return { ok: false, status: 502, detail: `DC token request exception: ${String(err)}` };
  }
  if (!result.ok) return result;

  const claims = decodeJwtClaims(result.access_token);
  rememberDcAccessToken(result.access_token, claims);
  await cacheDcAccessToken(result.access_token, claims);

  if (result.refresh_token && result.refresh_token !== refreshToken) {
    try {
      await env.AUTH_STORE.put("dc_refresh_token", result.refresh_token);
    } catch (err) {
      console.warn("DC refresh token persistence failed", String(err));
    }
  }
  return result;
}

async function getFreshDcToken(env) {
  const cached = await readCachedDcAccessToken();
  if (cached) return cached;
  if (!dcRefreshInFlight) dcRefreshInFlight = refreshDcAccessToken(env);
  try {
    return await dcRefreshInFlight;
  } finally {
    dcRefreshInFlight = null;
  }
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
