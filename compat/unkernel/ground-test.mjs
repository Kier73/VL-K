import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, readFileSync, writeFileSync, statSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { GroundDisk } from './ground-disk.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
if(process.argv[2]==='child'){
  const d=new GroundDisk(process.argv[3]);d.write(0,[new Uint8Array(512).fill(99)]);if(process.argv[4]==='flush')d.flush();process.kill(process.pid,'SIGKILL');
}else{
  const dir=mkdtempSync(join(tmpdir(),'vlk-ground-')),path=join(dir,'disk');
  try{
    const size=2*1024*1024,pattern=Uint8Array.from({length:size},(_,i)=>(i%4096)%7+1),d=new GroundDisk(path,size);
    const initial=d.receipt();assert.equal(initial.revision,0);assert.equal(statSync(path).size,112);
    d.write(0,[pattern.subarray(0,771),pattern.subarray(771)]);assert.equal(d.receipt().observationDigest,initial.observationDigest);assert(d.receipt().dirty);
    const waiting=d.whenFlushed(d.flushSeq);d.flush();await waiting;const committed=d.receipt();assert.equal(committed.observationDigest,hash(pattern));assert.equal(committed.revision,1);assert.equal(statSync(path).size,133);
    console.log('2 MiB logical disk, 133-byte durable Ground, one shared object and one coordinate run');
    let r=new GroundDisk(path);assert.deepEqual(r.receipt(),committed);const out=new Uint8Array(size);r.read(0,[out]);assert.deepEqual(out,pattern);r.flush();assert.deepEqual(r.receipt(),committed);
    for(const mode of ['dirty','flush']){const child=spawnSync(process.execPath,[new URL(import.meta.url).pathname,'child',path,mode]);assert.equal(child.signal,'SIGKILL');r=new GroundDisk(path);if(mode==='dirty')assert.deepEqual(r.receipt(),committed);else{pattern.fill(99,0,512);assert.equal(r.receipt().revision,2);assert.equal(r.receipt().observationDigest,hash(pattern));}r.read(0,[out]);assert.deepEqual(out,pattern);}
    // Different history/identity, same complete logical Ground.
    const other=new GroundDisk(join(dir,'other'),size);other.write(0,[pattern]);other.flush();assert.equal(other.receipt().observationDigest,r.receipt().observationDigest);assert.notEqual(other.receipt().identity,r.receipt().identity);
    const bad=join(dir,'bad'),bytes=readFileSync(path);bytes[85]^=1;writeFileSync(bad,bytes);assert.throws(()=>new GroundDisk(bad),/integrity/);
    // Re-sign a false logical digest: encoding integrity alone is insufficient.
    const forged=readFileSync(path);forged[40]^=1;Buffer.from(hash(forged.subarray(0,-32)),'hex').copy(forged,forged.length-32);writeFileSync(bad,forged);assert.throws(()=>new GroundDisk(bad),/observation mismatch/);
    assert.throws(()=>new GroundDisk(path,size+4096),/size mismatch/);
    console.log('fresh process SIGKILL before/after flush, logical observation digest across histories, corruption and false observation refusal passed');
  }finally{rmSync(dir,{recursive:true,force:true});}
}
