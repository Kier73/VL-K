import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn,execFileSync} from 'node:child_process';
import {once} from 'node:events';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import {HistoryDevice} from './history-device.mjs';
import {ObservationDevice} from './observation-device.mjs';
import {tlsObservation} from './tls-observation.mjs';
const dir=await mkdtemp(join(tmpdir(),'vlk-projection-')),path=join(dir,'replacement.sqlite');
let h,server;
try{
  h=await HistoryDevice.open(path,{pages:16384});const empty=h.receipt(),zero=new ObservationDevice(empty,[]);
  const out=new Uint8Array(4096);await zero.read(0,[out]);assert.equal(zero.stats().attempts,0);
  const a=Uint8Array.from({length:4096},(_,i)=>i%251+1),b=new Uint8Array(4096).fill(19);
  await h.write(0,[a]);await h.write(8192*4096,[b]);const seal=await h.seal();
  const receipt=Object.fromEntries(['groundVersion','identity','pages','revision','root'].map(k=>[k,seal[k]]));
  const worker=h,local={observe:(r,i)=>worker.witness(r.revision,i)};
  const invalid={observe:async(r,i)=>{const w=await local.observe(r,i);w.page=Buffer.alloc(4096,9).toString('base64');return w;}};
  const device=new ObservationDevice(receipt,[invalid,local],{cachePages:1});
  await device.read(0,[out]);assert.deepEqual(out,a);assert.equal(device.stats().refusals,1);
  // One witness certifies the empty sibling subtrees in the left half.
  for(let i=1;i<8192;i++){await device.read(i*4096,[out]);assert(out.every(x=>x===0));}
  assert.equal(device.stats().attempts,2);assert.equal(device.stats().derived,8191);
  await device.read(0,[out]);assert.deepEqual(out,a);assert.equal(device.stats().cache,1);
  const stranded=new ObservationDevice(receipt,[invalid]);const sentinel=new Uint8Array(8192).fill(42);
  await assert.rejects(stranded.read(0,[sentinel]),/no sufficient/);assert(sentinel.every(x=>x===42));
  // A failed later page must not publish even the verified prefix.
  const partial=new ObservationDevice(receipt,[{observe:(r,i)=>i===8192?Promise.reject(Error('unavailable')):local.observe(r,i)}]);
  await assert.rejects(partial.read(8191*4096,[sentinel]),/no sufficient/);assert(sentinel.every(x=>x===42));
  await assert.rejects(device.read(1,[out]),/range/);assert.throws(()=>device.write(),/read-only/);
  await h.close();h=undefined;
  // Reuse the previous authenticated server fixture, without a Python client bridge.
  const script=fileURLToPath(new URL('./remote-observer-test.py',import.meta.url));
  execFileSync('python3',['-c','import runpy,sys; from pathlib import Path; m=runpy.run_path(sys.argv[1]); m["fixture"].certs(Path(sys.argv[2]))',script,dir],{env:{...process.env,PYTHONPATH:fileURLToPath(new URL('.',import.meta.url))}});
  await writeFile(join(dir,'policy.json'),JSON.stringify({receipt,coordinates:[0,8192]}));
  server=spawn('python3',[script,'server',dir,'replacement'],{stdio:['ignore','pipe','inherit']});
  const ended=once(server,'exit');const lines=createInterface({input:server.stdout});const [line]=await Promise.race([once(lines,'line'),ended.then(()=>{throw Error('server exited');})]);
  const remote=tlsObservation({host:'127.0.0.1',port:Number(line),ca:await readFile(join(dir,'ca.crt')),cert:await readFile(join(dir,'observer.crt')),key:await readFile(join(dir,'observer.key'))});
  const projection=new ObservationDevice(receipt,[local,remote],{cachePages:0});
  await projection.read(0,[out.subarray(0,777),out.subarray(777)]);assert.deepEqual(out,a);
  await projection.read(8192*4096,[out]);assert.deepEqual(out,b);assert.equal(projection.stats().verified,2);assert.equal(projection.stats().refusals,2);
  server.kill();await ended;server=undefined;
  await projection.read(16383*4096,[out]);assert(out.every(x=>x===0));
  await assert.rejects(projection.read(0,[out]),/no sufficient/);
  console.log('8191 zero-page observations from one verified path; two native TLS observations; cache, failover, offline derivation and atomic refusal passed');
}finally{if(h)await h.close();if(server){const e=once(server,'exit');server.kill();await e;}await rm(dir,{recursive:true,force:true});}
