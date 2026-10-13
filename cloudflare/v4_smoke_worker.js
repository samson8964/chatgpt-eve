export { V4OpportunityLedger } from "./v4_store.js";
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/health") {
      return new Response("Not found", {status: 404});
    }
    const instance = env.V4_LEDGER.get(env.V4_LEDGER.idFromName("canary"));
    return instance.fetch(new Request("https://ledger.internal/health"));
  }
};
