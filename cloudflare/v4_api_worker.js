// Independent V4 event-ledger API. Does NOT handle EVE SSO or mail sending.
export { V4OpportunityLedger } from "./v4_store.js";
export default {
  async fetch(request, env) {
    const u = new URL(request.url);
    if (u.pathname === "/health") {
      try {
        const actor = env.V4_LEDGER.get(env.V4_LEDGER.idFromName("production"));
        // await intentionally: a rejected Durable Object fetch must be caught,
        // not surface as an opaque Cloudflare 1101.
        return await actor.fetch(new Request("https://ledger.internal/health"));
      } catch (err) {
        console.error("V4_LEDGER_HEALTH_EXCEPTION", err);
        const privileged=Boolean(env.V4_API_KEY &&
          request.headers.get("Authorization")==="Bearer "+env.V4_API_KEY);
        const detail=privileged ? {
          exception_type:String(err?.name || typeof err).slice(0,80),
          exception_message:String(err?.message || err).slice(0,280)
        } : undefined;
        return new Response(JSON.stringify({ok:false,error:"ledger_backend_exception",...(detail?{detail}:{})}),{
          status:503,headers:{"content-type":"application/json"}
        });
      }
    }
    if (!u.pathname.startsWith("/api/v4/")) return new Response("Not Found", {status:404});
    if (!env.V4_API_KEY || request.headers.get("Authorization") !== "Bearer " + env.V4_API_KEY) {
      return new Response("Unauthorized", {status:401});
    }
    const endpoint = u.pathname.slice("/api/v4/".length);
    if (!["record","run","pending","claim","settle","audit"].includes(endpoint)) {
      return new Response("Not Found", {status:404});
    }
    const actor = env.V4_LEDGER.get(env.V4_LEDGER.idFromName("production"));
    const url = new URL("https://ledger.internal/" + endpoint);
    if (request.method === "GET") url.search = u.search;
    return actor.fetch(new Request(url, request));
  }
};
