import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';import {execFileSync} from 'node:child_process';import {join} from 'node:path';
import {createKernel} from '../js/vlk.mjs';import {GroundAtlas,residueIntention} from '../js/ground-atlas.mjs';
const kernel=await createKernel(readFileSync(new URL('../dist/vlk.wasm',import.meta.url)));
const dir=mkdtempSync(join(tmpdir(),'vlk-atlas-')),path=join(dir,'atlas.json');
const program=[['mulr',0,0],['add',0,17],['mul',0,3]],bits=12,mask=4095;
let calls=0;const counted={evaluate(q){calls++;return kernel.evaluate(q);}};
function oracle(seed,steps){let x=seed&mask;const seen=new Map(),trace=[];while(!seen.has(x)){seen.set(x,trace.length);trace.push(x);x=(Math.imul(x,x)+17)*3&mask;}return trace[Number(steps<BigInt(trace.length)?steps:BigInt(seen.get(x))+(steps-BigInt(seen.get(x)))%BigInt(trace.length-seen.get(x)))];}
try{
 let a=new GroundAtlas();const start=performance.now();a.discover(counted,program,bits);const discovery=performance.now()-start;assert.equal(calls,4096);const bytes=a.save(path);a=GroundAtlas.open(path);calls=0;
 let seed=4321;const rnd=()=>seed=(Math.imul(seed,1664525)+1013904223)>>>0;
 for(let j=0;j<512;j++){const s=rnd(),n=j%2?BigInt(1000+rnd()%4000):((1n<<63n)|BigInt(rnd()));const i=residueIntention(program,bits,s,n),r=await a.observe(counted,i);assert.equal(r.receipt.selected,'atlas-residue');assert.equal(r.value,oracle(s,n));if(j%2){const ref=kernel.evaluate({seed:[s,0,0,0],program,steps:n,budget:20000,mode:'reference'});assert.equal(ref.status,0);assert.equal(ref.registers[0]&mask,r.value);}}
 assert.equal(calls,0);const small=await a.observe(counted,residueIntention(program,bits,123,2n));assert.equal(small.receipt.selected,'wasm-reference-residue');assert.equal(small.value,oracle(123,2n));assert.equal(calls,1);
 // Fresh process with no source kernel available at all.
 const moduleURL=new URL('../js/ground-atlas.mjs',import.meta.url).href;
 const child=execFileSync(process.execPath,['--input-type=module','-e',
   'import {GroundAtlas,residueIntention} from '+JSON.stringify(moduleURL)+';const a=GroundAtlas.open(process.argv[1]);const i=residueIntention('+JSON.stringify(program)+',12,987654321,18446744073709551615n);const r=await a.observe({evaluate(){throw Error("source unavailable");}},i);console.log(r.value);',path],{encoding:'utf8'});
 assert.equal(Number(child.trim()),oracle(987654321,(1n<<64n)-1n));
 const bad=JSON.parse(readFileSync(path));bad.laws[0].table[0]^=1;writeFileSync(path,JSON.stringify(bad));assert.throws(()=>GroundAtlas.open(path),/contradiction/);
 assert.throws(()=>residueIntention([['copy',0,1]],bits,1,1n));
 await assert.rejects(a.observe(counted,residueIntention([['add',0,7]],bits,1,1n<<63n)),/no sufficient/);
 const corrupt={evaluate(q){const r=kernel.evaluate(q);r.registers[0]^=1;return r;}};assert.throws(()=>new GroundAtlas().discover(corrupt,program,bits),/contradiction/);
 console.log({discoveryCalls:4096,discoveryMs:discovery,serializedBytes:bytes,unseen:512,sourceCallsForUnseen:0,moderateWasmChecks:256});console.log('source contradiction, tampered atlas, domain refusal, fresh process without source and conventional selection passed');
}finally{rmSync(dir,{recursive:true,force:true});}
