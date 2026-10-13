/**
 * V4 dedicated SQL-backed Durable Object. No dependency on V2/V3 CSV state.
 * The runtime provides a single-writer actor and durable SQLite transaction
 * storage. External notification side effects are always outside the DB txn.
 */
export class V4OpportunityLedger {
  constructor(ctx, env) {
    this.ctx = ctx;
    this.env = env;
    this.db = ctx.storage.sql;
    this.db.exec("CREATE TABLE IF NOT EXISTS versions (run_id TEXT NOT NULL, instance TEXT NOT NULL, proof TEXT NOT NULL, PRIMARY KEY(run_id,instance))");
    this.db.exec("CREATE TABLE IF NOT EXISTS outbox (instance TEXT NOT NULL, recipient TEXT NOT NULL, channel TEXT NOT NULL, proof TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', mail_id TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(instance,recipient,channel))");
    this.db.exec("CREATE TABLE IF NOT EXISTS scan_runs (run_id TEXT PRIMARY KEY, outcome TEXT NOT NULL, coverage TEXT NOT NULL, started TEXT NOT NULL)");
    this.db.exec("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, val TEXT NOT NULL)");
    this.db.exec("CREATE TABLE IF NOT EXISTS eligible_history (instance TEXT PRIMARY KEY, first_seen TEXT NOT NULL, shadow_baseline INTEGER NOT NULL)");
  }

  result(obj, status=200) {
    return new Response(JSON.stringify(obj), { status, headers: {"content-type":"application/json; charset=utf-8"} });
  }

  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return this.result({ok:true, backend:"v4-durable-sqlite", dispatch_enabled:this.env.V4_RELEASE_ENABLED==="1", ledger_version:2});
    }
    if (request.method === "GET" && url.pathname === "/pending") {
      const recipient = url.searchParams.get("recipient") || "";
      if (!recipient) return this.result({ok:false,error:"missing_recipient"},400);
      const rows = [...this.db.exec("SELECT instance,proof FROM outbox WHERE recipient=? AND status='pending' ORDER BY updated_at ASC LIMIT 500",recipient)];
      return this.result({ok:true, rows:rows.map(x=>({instance:x.instance,proof:JSON.parse(x.proof)}))});
    }
    if (request.method !== "POST") return this.result({ok:false,error:"unsupported_operation"},405);
    let body;
    try { body=await request.json(); } catch { return this.result({ok:false,error:"invalid_json"},400); }
    if (url.pathname === "/record") {
      const runId = String(body.run_id || "");
      if (!/^[A-Za-z0-9_-]{5,128}$/.test(runId)) return this.result({ok:false,error:"invalid_run"},400);
      const proofs = Array.isArray(body.proofs) ? body.proofs : [];
      if (proofs.length>500) return this.result({ok:false,error:"batch_too_large"},413);
      const recipients = Array.isArray(body.recipients) ? body.recipients : [];
      const now = new Date().toISOString();
      const enabled = this.env.V4_RELEASE_ENABLED==="1";
      let created=0;
      this.ctx.storage.transactionSync(()=>{
        for (const p of proofs) {
          const instance = String(p.instance || "");
          if (!/^[A-Za-z0-9:_-]{8,160}$/.test(instance)) continue;
          const payload=JSON.stringify(p);
          this.db.exec("INSERT OR REPLACE INTO versions(run_id,instance,proof) VALUES(?,?,?)",runId,instance,payload);
          if (String(p.status)!=="MAIL") continue;
          const prior=[...this.db.exec("SELECT 1 AS x FROM eligible_history WHERE instance=?",instance)];
          if (prior.length) continue;
          this.db.exec("INSERT INTO eligible_history(instance,first_seen,shadow_baseline) VALUES(?,?,?)",instance,now,enabled?0:1);
          if (!enabled) continue;
          for (const recipient of recipients) {
            if (!/^[A-Za-z0-9_-]{2,60}$/.test(String(recipient))) continue;
            const exists=[...this.db.exec("SELECT 1 AS x FROM outbox WHERE instance=? AND recipient=? AND channel='eve'",instance,recipient)];
            if(exists.length) continue;
            this.db.exec("INSERT INTO outbox(instance,recipient,channel,proof,status,updated_at) VALUES(?,?, 'eve',?,'pending',?)",instance,recipient,payload,now);
            created++;
          }
        }
      });
      return this.result({ok:true,committed:proofs.length,pending_added:created,dispatch_enabled:Boolean(enabled)});
    }
    if (url.pathname === "/run") {
      if (!/^[A-Za-z0-9_-]{5,128}$/.test(String(body.run_id))) return this.result({ok:false,error:"invalid_run"},400);
      this.db.exec("INSERT OR REPLACE INTO scan_runs VALUES(?,?,?,?)",
        String(body.run_id),String(body.outcome),JSON.stringify(body.coverage||{}),new Date().toISOString());
      return this.result({ok:true});
    }
    if (url.pathname === "/claim") {
      const instance=String(body.instance||""), recipient=String(body.recipient||"");
      let claimed=false;
      this.ctx.storage.transactionSync(()=>{
        const r=[...this.db.exec("SELECT status FROM outbox WHERE instance=? AND recipient=? AND channel='eve'",instance,recipient)];
        if (r.length && r[0].status==="pending") {
          this.db.exec("UPDATE outbox SET status='sending',updated_at=? WHERE instance=? AND recipient=? AND channel='eve'",new Date().toISOString(),instance,recipient);
          claimed=true;
        }
      });
      return this.result({ok:true,claimed});
    }
    if (url.pathname === "/settle") {
      const instance=String(body.instance||""),recipient=String(body.recipient||"");
      const outcome=String(body.outcome||"");
      if(!["sent","uncertain"].includes(outcome))return this.result({ok:false,error:"invalid_outcome"},400);
      this.db.exec("UPDATE outbox SET status=?,mail_id=?,updated_at=? WHERE instance=? AND recipient=? AND status='sending'",
        outcome,String(body.mail_id||""),new Date().toISOString(),instance,recipient);
      return this.result({ok:true,status:outcome});
    }
    if (url.pathname === "/cancel") {
      const instance=String(body.instance||""),recipient=String(body.recipient||"");
      this.db.exec("UPDATE outbox SET status='obsolete',updated_at=? WHERE instance=? AND recipient=? AND status='pending'",new Date().toISOString(),instance,recipient);
      return this.result({ok:true});
    }
    if (url.pathname === "/settings") {
      // Settings is intentionally NOT exposed via public HTTP API; deployed
      // operators activate only via reviewed code/migration, never arbitrary
      // requests or a stale production client.
      return this.result({ok:false,error:"activation_requires_reviewed_deploy"},403);
    }
    return this.result({ok:false,error:"unknown_endpoint"},404);
  }
}
