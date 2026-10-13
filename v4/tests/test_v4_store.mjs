import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const moduleSource = await readFile(new URL('../../cloudflare/v4_store.js', import.meta.url), 'utf8');
const {V4OpportunityLedger} = await import('data:text/javascript;base64,' + Buffer.from(moduleSource).toString('base64'));

class InMemorySQL {
  constructor() { this.runs=new Set(); this.versions=new Map(); this.history=new Set(); }
  exec(sql, ...p) {
    if(sql.startsWith('CREATE TABLE')) return [];
    if(sql.startsWith('INSERT OR REPLACE INTO scan_runs')) { this.runs.add(p[0]); return []; }
    if(sql.startsWith('SELECT 1 AS found FROM scan_runs')) return this.runs.has(p[0])?[{found:1}]:[];
    if(sql.startsWith('SELECT outcome,coverage,started FROM scan_runs'))
      return this.runs.has(p[0])?[{outcome:'SHADOW',coverage:'{}',started:'2026-10-13T00:00:00Z'}]:[];
    if(sql.startsWith('SELECT COUNT(*) AS total FROM versions'))
      return [{total:[...this.versions.keys()].filter(k=>k.startsWith(p[0]+':')).length}];
    if(sql.startsWith("SELECT json_extract(proof,'$.status') AS status")) {
      const counts=new Map();
      for(const [key,raw] of this.versions)
        if(key.startsWith(p[0]+':')) {
          const status=JSON.parse(raw).status;
          counts.set(status,(counts.get(status)||0)+1);
        }
      return [...counts.entries()].map(([status,n])=>({status,n}));
    }
    if(sql.startsWith('SELECT proof FROM versions')) {
      const old=this.versions.get(p[0]+':'+p[1]);return old===undefined?[]:[{proof:old}];
    }
    if(sql.startsWith('INSERT INTO versions')) {
      const key=p[0]+':'+p[1];
      assert.equal(this.versions.has(key),false);
      this.versions.set(key,p[2]);return [];
    }
    if(sql.startsWith('SELECT COUNT(*) AS n FROM versions'))
      return [{n:[...this.versions.keys()].filter(k=>k.startsWith(p[0]+':')).length}];
    if(sql.startsWith('SELECT 1 AS x FROM eligible_history'))
      return this.history.has(p[0])?[{x:1}]:[];
    if(sql.startsWith('INSERT INTO eligible_history')) {this.history.add(p[0]);return [];}
    throw Error('Unexpected SQL: '+sql);
  }
}
function makeActor(enabled='0') {
  const sql=new InMemorySQL();
  const actor=new V4OpportunityLedger({storage:{sql,transactionSync(fn){fn();}}},{V4_RELEASE_ENABLED:enabled});
  return {actor,sql};
}
async function post(actor,endpoint,body) {
  const resp=await actor.fetch(new Request('https://ledger.internal/'+endpoint,{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
  }));
  return {status:resp.status,body:await resp.json()};
}
const runId='v4-test-001';
const proof=(id,reason='test')=>({instance:'contract:'+id,status:'WATCH',reason});
async function registered(enabled='0') {
  const {actor,sql}=makeActor(enabled);
  assert.equal((await post(actor,'run',{run_id:runId,outcome:'SHADOW'})).status,200);
  return {actor,sql};
}
test('reject invalid identity atomically rather than falsely count',async()=>{
  const {actor,sql}=await registered();
  const result=await post(actor,'record',{run_id:runId,proofs:[proof(10001),{status:'WATCH',instance:null}]});
  assert.equal(result.status,422);
  assert.equal(sql.versions.size,0);
});
test('reject duplicates within a batch without partial ingest',async()=>{
  const {actor,sql}=await registered();
  assert.equal((await post(actor,'record',{run_id:runId,proofs:[proof(10001),proof(10001)]})).status,409);
  assert.equal(sql.versions.size,0);
});
test('no orphan proofs for unknown run',async()=>{
  const {actor,sql}=makeActor();
  assert.equal((await post(actor,'record',{run_id:runId,proofs:[proof(10001)]})).status,409);
  assert.equal(sql.versions.size,0);
});
test('cumulative durable unique row counts and identical retry',async()=>{
  const {actor,sql}=await registered();
  const request={run_id:runId,proofs:[proof(10001),proof(10002)]};
  const a=await post(actor,'record',request);
  assert.equal(a.status,200);
  assert.deepEqual([a.body.committed,a.body.stored_total],[2,2]);
  const b=await post(actor,'record',request);
  assert.equal(b.status,200);
  assert.deepEqual([b.body.committed,b.body.stored_total],[2,2]);
  assert.equal(sql.versions.size,2);
});
test('reject contradictory same-run revisions without replacing proof',async()=>{
  const {actor,sql}=await registered();
  await post(actor,'record',{run_id:runId,proofs:[proof(10001)]});
  await assert.rejects(()=>post(actor,'record',{run_id:runId,proofs:[proof(10001,'changed')]}),
    /CONFLICTING_PROOF_INSTANCE/);
  assert.equal(JSON.parse(sql.versions.get(runId+':contract:10001')).reason,'test');
});
test('release switch alone cannot authorize unverified formal MAIL',async()=>{
  const {actor,sql}=await registered('1');
  const result=await post(actor,'record',{run_id:runId,proofs:[{...proof(10001),status:'MAIL'}]});
  assert.equal(result.status,409);
  assert.equal(result.body.error,'live_execution_gate_not_implemented');
  assert.equal(sql.versions.size,0);
});

test('authenticated audit reports actual SQLite unique proof count and statuses',async()=>{
  const {actor,sql}=await registered();
  const written=await post(actor,'record',{run_id:runId,proofs:[proof(10001),{...proof(10002),status:'RESEARCH'}]});
  assert.equal(written.body.stored_total,2);
  const response=await actor.fetch(new Request('https://ledger.internal/audit?run_id='+runId));
  assert.equal(response.status,200);
  const audit=await response.json();
  assert.equal(audit.sql_unique_proofs,2);
  assert.deepEqual(audit.status_counts,{RESEARCH:1,WATCH:1});
  assert.equal(audit.dispatch_enabled,false);
  const unknown=await actor.fetch(new Request('https://ledger.internal/audit?run_id=v4-unknown'));
  assert.equal(unknown.status,404);
});

test('health is read-only when Durable Object free-tier writes are exhausted',async()=>{
  const sql={exec(){throw new Error('Exceeded allowed rows written in Durable Objects free tier.')}};
  const actor=new V4OpportunityLedger({storage:{sql,transactionSync(fn){fn();}}},{V4_RELEASE_ENABLED:'0'});
  const response=await actor.fetch(new Request('https://ledger.internal/health'));
  assert.equal(response.status,200);
  const health=await response.json();
  assert.equal(health.ledger_version,4);
  assert.equal(health.dispatch_enabled,false);
});
