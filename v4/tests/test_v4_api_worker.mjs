import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";
const src=await readFile(new URL("../../cloudflare/v4_api_worker.js",import.meta.url),"utf8");
// Data-URL modules cannot resolve relative exports; the test only needs the default worker.
const selfContained=src.replace('export { V4OpportunityLedger } from "./v4_store.js";','');
const {default:worker}=await import("data:text/javascript;base64,"+Buffer.from(selfContained).toString("base64"));
function envWithFailure(){
  return {V4_API_KEY:"protected-test-key",V4_LEDGER:{idFromName:()=> "production",get:()=>{throw new Error("sqlite runtime failed");}}};
}
test("public health failure redacts cloud backend exception",async()=>{
  const log=console.error;console.error=()=>{};
  try{
    const r=await worker.fetch(new Request("https://store.test/health"),envWithFailure());
    assert.equal(r.status,503);
    const body=await r.json();
    assert.equal(body.error,"ledger_backend_exception");
    assert.equal(body.detail,undefined);
  } finally{console.error=log;}
});
test("authorized health probe can inspect bounded exception only",async()=>{
  const log=console.error;console.error=()=>{};
  try{
    const req=new Request("https://store.test/health",{headers:{"Authorization":"Bearer protected-test-key"}});
    const r=await worker.fetch(req,envWithFailure());
    assert.equal(r.status,503);
    const body=await r.json();
    assert.equal(body.detail.exception_type,"Error");
    assert.match(body.detail.exception_message,/sqlite runtime failed/);
  }finally{console.error=log;}
});

test("status does not invoke Durable Object while daily SQL quota is blocked",async()=>{
  const env={V4_RELEASE_ENABLED:"0",V4_API_KEY:"test",
             V4_LEDGER:{idFromName(){throw Error("DB not allowed");},
                        get(){throw Error("DB not allowed");}}};
  const res=await worker.fetch(new Request("https://store.test/status"),env);
  assert.equal(res.status,200);
  const body=await res.json();
  assert.equal(body.dispatch_enabled,false);
  assert.equal(body.ledger_protocol,4);
  assert.equal(body.durable_sql_status,"NOT_CHECKED");
});
