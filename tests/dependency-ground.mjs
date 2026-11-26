import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createKernel} from '../js/vlk.mjs';
import {compileDependencies,dependencyIntention,observeDependencies,dependencyBindings} from '../js/dependency-ground.mjs';
import {realize} from '../js/realization.mjs';
const kernel=await createKernel(await readFile(new URL('../dist/vlk.wasm',import.meta.url)));
let calls=0;const counted={evaluate(q){calls++;return kernel.evaluate(q);}};
const same=p=>Array.from({length:16},()=>p), targets=[0,1,2];
const swap=[['copy',2,0],['copy',0,1],['mulr',0,0],['copy',1,2],['add',3,1]];
const mixed=Array.from({length:16},(_,s)=>s&8?swap:[['copy',2,0],['copy',0,1],['copy',1,2],['add',3,1]]);
const coupled=same([['mul',0,2],['addr',0,1],['copy',1,0],['mul',1,2],['mulr',2,1],['set',3,0]]);
const product=same([['mulr',0,1],['mul',1,2],['copy',2,0],['set',3,0]]);
const families=[{l:same(swap),t:targets},{l:mixed,t:targets},{l:coupled,t:[0,1,2,3]},{l:product,t:[0,1,2,3]}];
let rng=901;const rnd=()=>rng=(Math.imul(rng,1664525)+1013904223)>>>0;
const max=(1n<<64n)-1n, mask=0xffffffffn;
function transition(l,x){const p=l[x.reduce((s,v,i)=>s|Number((v&1n)<<BigInt(i)),0)],y=x.slice();for(const [op,d,v] of p){const q=BigInt(v);switch(op){case 'copy':y[d]=y[v];break;case 'set':y[d]=q;break;case 'mul':y[d]*=q;break;case 'add':y[d]+=q;break;case 'addr':y[d]+=y[v];break;case 'mulr':y[d]*=y[v];break;}y[d]&=mask;}return y;}
function oracle(l,seed,n,ignore3){let x=seed.map(BigInt),seen=new Map(),trace=[];while(true){const key=(ignore3?[...x.slice(0,3),x[3]&1n]:x).join(',');if(seen.has(key)){const p=BigInt(seen.get(key));return trace[Number(n<BigInt(trace.length)?n:p+(n-p)%BigInt(trace.length-Number(p)))];}seen.set(key,trace.length);trace.push(x.map(Number));assert(trace.length<10000);x=transition(l,x);}}
let moderate=0,huge=0,refused=0,relations=0,wasm=0;const stats=[];
for(const {l,t} of families){const cert=compileDependencies(l,32,t);stats.push({bounds:cert.paths.map(p=>p.bound),periods:cert.paths.map(p=>p.period)});for(let s=0;s<16;s++){
  // Independently challenge each layer's precision-transfer matrix on high-bit pairs.
  for(let j=0;j<16;j++){const k=Array.from({length:4},()=>1+(rnd()>>>16)%32);const x=k.map((_,i)=>((rnd()&0xfffffffe)|((s>>i)&1))>>>0);const y=x.map((v,i)=>Number((BigInt(v)+(BigInt(rnd())<<BigInt(k[i])))&mask));const a=transition(l,x.map(BigInt)),b=transition(l,y.map(BigInt));for(let r=0;r<4;r++){const known=Math.min(32,...cert.layers[s].rows[r].map((w,i)=>w+k[i]));assert.equal((a[r]-b[r])&((1n<<BigInt(known))-1n),0n);relations++;}}
  for(let j=0;j<8;j++){const x=Array.from({length:4},(_,i)=>((rnd()&0xfffffffe)|((s>>i)&1))>>>0),n=BigInt(j?100+rnd()%100:j);let y=x.map(BigInt);for(let k=0n;k<n;k++)y=transition(l,y);const r=await observeDependencies(counted,dependencyIntention(l,32,t,x,n));assert.deepEqual(r.value,t.map(i=>Number(y[i])));moderate++;}
  const x=Array.from({length:4},(_,i)=>((rnd()&0xfffffffe)|((s>>i)&1))>>>0);let y=x;for(let k=0;k<160;k++){const p=y.reduce((s,v,i)=>s|((v&1)<<i),0);const r=kernel.evaluate({seed:y,program:l[p],steps:1,budget:64,mode:'reference'});assert.equal(r.status,0);y=r.registers;}assert.deepEqual((await observeDependencies(counted,dependencyIntention(l,32,t,x,160n))).value,t.map(i=>y[i]));wasm++;
  for(let j=0;j<4;j++){const seed=Array.from({length:4},(_,i)=>((rnd()&0xfffffffe)|((s>>i)&1))>>>0),n=max-BigInt(rnd()),intent=dependencyIntention(l,32,t,seed,n);if(cert.paths[s].bound===null){await assert.rejects(observeDependencies(counted,intent),/no sufficient/);refused++;continue;}const before=calls,r=await observeDependencies(counted,intent);assert.equal(calls,before);assert.deepEqual(r.value,t.map(i=>oracle(l,seed,n,t.length===3)[i]));huge++;}
}}
// The unobserved clock has period 2^32. Full-state contraction is deliberately refused.
assert(compileDependencies(same(swap),32,[0,1,2,3]).paths.every(p=>p.bound===null));
await assert.rejects(observeDependencies(counted,dependencyIntention(same(swap),32,[0,1,2,3],[1,2,3,4],max)),/no sufficient/);
const i=dependencyIntention(mixed,32,targets,[1,3,9,2],max),b=dependencyBindings(counted)[1];await assert.rejects(realize(i,[{...b,run:q=>({...b.run(q),value:[0,0,0]})}],2000003),/no sufficient/);
assert.throws(()=>dependencyIntention(mixed,32,[0,0],[0,0,0,0],1n));
console.log(JSON.stringify({moderate,huge,refused,relations,wasm,stats}));
