// Independent V4 event-ledger API. Does NOT handle EVE SSO or mail sending.
export { V4OpportunityLedger } from "./v4_store.js";
export default {
  async fetch(request, env) {
    const u = new URL(request.url);
    if (u.pathname === "/health") {
      const actor = env.V4_LEDGER.get(env.V4_LEDGER.idFromName("production"));
      return actor.fetch(new Request("https://ledger.internal/health"));
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
