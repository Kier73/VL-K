import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createKernel} from '../js/vlk.mjs';
import {compileLayered,layeredIntention,observeLayered,layeredBindings} from '../js/layered-realization.mjs';
import {realize} from '../js/realization.mjs';
const kernel=await createKernel(await readFile(new URL('../dist/vlk.wasm',import.meta.url)));
let calls=0;const counted={evaluate(q){calls++;return kernel.evaluate(q);}};
const A=[['mulr',0,0],['add',0,17],['mul',0,3]],B=[['add',0,1]],C=[['mul',0,8],['add',0,1]],D=[['set',0,42]],E=[['mul',0,3],['add',0,2]];
const laws=[[A,A],[B,A],[C,B],[D,E],[E,E],[B,B],[B,C],[B,E]];
let seed=182;const rnd=()=>seed=(Math.imul(seed,1664525)+1013904223)>>>0;
function f(l,x){for(const [op,,v] of l[Number(x&1n)]){const b=BigInt(v);x=op==='set'?b:op==='add'?x+b:op==='mul'?x*b:x*x;x&=0xffffffffn;}return x;}
function eager(l,x,n){x=BigInt(x);for(let i=0;i<n;i++)x=f(l,x);return Number(x);}
// Independently lift a fixed point of the cyclic composition one bit at a time.
// No reduced-time bound or compiler gain used in this oracle.
function oracle(l,x,n){let p=x&1;const visited=[],next=y=>Number(f(l,BigInt(y))&1n);while(!visited.includes(p)){visited.push(p);p=next(p);}const tail=visited.indexOf(p),period=visited.length-tail;
  let fixed=BigInt(p);const cycle=y=>{for(let k=0;k<period;k++)y=f(l,y);return y;};
  for(let bit=1;bit<32;bit++){const mask=(1n<<BigInt(bit+1))-1n,alt=fixed|(1n<<BigInt(bit));const opts=[fixed,alt].filter(v=>(cycle(v)&mask)===v);assert.equal(opts.length,1);fixed=opts[0];}
  assert.equal(cycle(fixed),fixed);let r=(n-BigInt(tail))%BigInt(period);while(r--)fixed=f(l,fixed);return Number(fixed);}
let checks=0,large=0,refused=0;const selected={};
for(const l of laws){const cert=compileLayered(l,32);console.log('certificate',cert.certificate);for(let j=0;j<80;j++){const x=rnd(),n=j<8?BigInt(j):BigInt(80+rnd()%120),i=layeredIntention(l,32,x,n);const result=await observeLayered(counted,i);assert.equal(result.value,eager(l,x,Number(n)));selected[result.receipt.selected]=(selected[result.receipt.selected]??0)+1;checks++;}
  for(let j=0;j<64;j++){const x=((rnd()&0xfffffffe)|(j&1))>>>0,n=((1n<<64n)-1n)-BigInt(rnd()),path=cert.certificate.paths[x&1];const i=layeredIntention(l,32,x,n);if(path.bound===null){await assert.rejects(observeLayered(counted,i),/no sufficient/);refused++;continue;}const before=calls,r=await observeLayered(counted,i);assert.equal(r.value,oracle(l,x,n));assert.equal(r.receipt.selected,'layered-contracting-ground');assert.equal(calls,before);large++;}}
// Full width source cross-check, including upper-bit carry and selector changes.
for(let j=0;j<160;j++){const l=laws[j%4],s=rnd(),n=100+rnd()%200;let x=s;for(let k=0;k<n;k++){const r=kernel.evaluate({seed:[x,0,0,0],program:l[x&1],steps:1,budget:64,mode:'reference'});assert.equal(r.status,0);x=r.registers[0];}assert.equal((await observeLayered(counted,layeredIntention(l,32,s,BigInt(n)))).value,x);}
// Projections and full-width maximum coordinate. Both parity classes separately.
for(let b=1;b<=32;b++)for(let p=0;p<2;p++){const s=(rnd()&0xfffffffe|p)>>>0,n=(1n<<64n)-1n;const r=await observeLayered(counted,layeredIntention([B,A],b,s,n));assert.equal(r.value,oracle([B,A],s,n)%2**b);}
// Exhaustively check every projected seed, for every test law, against explicit orbit detection.
let finiteChecks=0;
for(const l of laws){const cert=compileLayered(l,8);for(let s=0;s<256;s++){
  if(cert.certificate.paths[s&1].bound===null)continue;
  const seen=new Map(),trace=[];let x=s;while(!seen.has(x)){seen.set(x,trace.length);trace.push(x);x=Number(f(l,BigInt(x))&255n);}
  const p=BigInt(seen.get(x)),n=(1n<<64n)-1n,answer=trace[Number(p+(n-p)%BigInt(trace.length-Number(p)))];
  assert.equal((await observeLayered(counted,layeredIntention(l,8,s,n))).value,answer);finiteChecks++;
}}
const noncontract=layeredIntention([E,E],32,1,1n<<63n);await assert.rejects(observeLayered(counted,noncontract),/no sufficient/);
const intent=layeredIntention([A,A],32,7,10000n),bindings=layeredBindings(counted),bad={...bindings[1],run:i=>({...bindings[1].run(i),value:0xffffffff})};await assert.rejects(realize(intent,[bad],2000003),e=>e.receipt.trace.some(t=>t.status==='admission-refused'));
assert.throws(()=>compileLayered([[['copy',0,1]],B],32));assert.throws(()=>layeredIntention([A,A],33,1,1n));
console.log({moderateChecks:checks,largeCoordinates:large,unqualifiedLargeRefusals:refused,wasmCrossChecks:160,projectionChecks:64,finiteChecks,selected,sourceCalls:calls});
