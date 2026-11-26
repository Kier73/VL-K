import assert from 'node:assert/strict';
import {dependencyIntention} from '../js/dependency-ground.mjs';
import {drivenBinding,inspectDriven} from '../js/driven-ground.mjs';
import {realize} from '../js/realization.mjs';
const M=0xffffffffn, max=(1n<<64n)-1n, mod=x=>x&M;
const same=p=>Array.from({length:16},()=>p), all=[0,1,2,3];
const nonlinear=[['mulr',0,0],['mul',0,2],['add',0,3]];
const addLaw=same([...nonlinear,['addr',1,0],['add',2,3],['add',3,1]]);
const mulLaw=same([...nonlinear,['mulr',1,0],['add',1,7],['add',2,3],['add',3,1]]);
const coupled=same([...nonlinear,['copy',3,2],['mulr',3,0],['addr',1,3],['add',2,3]]);
const phased=Array.from({length:16},(_,s)=>s&8?[...nonlinear,['mulr',1,0],['add',1,7],['add',3,1]]:[['add',0,2],['addr',1,0],['add',2,3],['add',3,1]]);
const f=x=>mod(2n*x*x+3n);
const laws=[{l:addLaw,step:([x,y,z,c])=>{x=f(x);return [x,mod(y+x),mod(z+3n),mod(c+1n)];}}, {l:mulLaw,step:([x,y,z,c])=>{x=f(x);return [x,mod(y*x+7n),mod(z+3n),mod(c+1n)];}}, {l:coupled,step:([x,y,z,c])=>{x=f(x);c=mod(x*z);return [x,mod(y+c),mod(z+3n),c];}}, {l:phased,step:([x,y,z,c])=>{if(c&1n){x=f(x);y=mod(y*x+7n);}else{x=mod(x+2n);y=mod(y+x);z=mod(z+3n);}return [x,y,z,mod(c+1n)];}}];
// Independent scalar affine power, geometric sum without division in the ring.
function affine(a,b,x,n){let s=0n,p=1n,g=1n;while(n){if(n&1n){s=mod(s+p*g);p=mod(p*a);}n>>=1n;g=mod(g*(1n+a));a=mod(a*a);}return mod(p*x+b*s);}
function oracle(k,seed,n){let x=seed.map(BigInt),t=n<128n?n:128n;for(let j=0n;j<t;j++)x=laws[k].step(x);if(n===t)return x;const q=n-t;let [a,y,z,c]=x;
  if(k===0)return [a,mod(y+q*a),mod(z+3n*q),mod(c+q)];
  if(k===1)return [a,affine(a,7n,y,q),mod(z+3n*q),mod(c+q)];
  if(k===2)return [a,mod(y+a*(q*z+3n*q*(q-1n)/2n)),mod(z+3n*q),mod(a*(z+3n*(q-1n)))];
  const first=laws[k].step(x),second=laws[k].step(first);assert.equal(second[0],a);const mult=c&1n?first[0]:second[0],offset=mod(second[1]-mult*y),cycles=q/2n;
  const out=[a,affine(mult,offset,y,cycles),mod(z+3n*cycles),mod(c+2n*cycles)];return q&1n?laws[k].step(out):out;
}
let state=97531;const rnd=()=>state=(Math.imul(state,1664525)+1013904223)>>>0;
const b=drivenBinding();let huge=0,moderate=0,projected=0;const examples=[];
for(let k=0;k<laws.length;k++){
  const {l}=laws[k];for(let j=0;j<64;j++){const seed=[rnd(),rnd(),rnd(),(rnd()&0xfffffffe|j%2)>>>0],n=max-BigInt(j)*123456789n,i=dependencyIntention(l,32,all,seed,n),plan=inspectDriven(i);assert(plan.drivers.includes(0));const r=await realize(i,[b],2000003);assert.deepEqual(r.value,oracle(k,seed,n).map(Number));huge++;if(j===0)examples.push(plan);}
  for(let j=0;j<48;j++){const seed=[rnd(),rnd(),rnd(),rnd()],n=BigInt(128+rnd()%256),i=dependencyIntention(l,32,all,seed,n);let x=seed.map(BigInt);for(let t=0n;t<n;t++)x=laws[k].step(x);assert.deepEqual((await realize(i,[b],2000003)).value,x.map(Number));moderate++;}
  for(let width=1;width<=32;width++){const seed=[rnd(),rnd(),rnd(),rnd()],i=dependencyIntention(l,width,[3,1],seed,max),mask=(1n<<BigInt(width))-1n;assert.deepEqual((await realize(i,[b],2000003)).value,[3,1].map(r=>Number(oracle(k,seed,max)[r]&mask)));projected++;}
}
const unknown=same([...nonlinear,['copy',2,1],['mulr',2,1],['mul',2,2],['addr',1,2]]);
await assert.rejects(realize(dependencyIntention(unknown,32,[1],[1,1,0,0],max),[b],2000003),e=>e.receipt.trace.some(t=>t.status==='realization-refused'));
const none=same([['add',0,1],['add',1,1],['add',2,1],['add',3,1]]);assert.equal(b.probe(dependencyIntention(none,32,all,[0,0,0,0],max)),null);
const i=dependencyIntention(mulLaw,32,all,[123,456,789,2],max);
await assert.rejects(realize(i,[{...b,run:q=>{const v=b.run(q);v[1]=(v[1]^1)>>>0;return v;}}],2000003),e=>e.receipt.trace.some(t=>t.status==='admission-refused'));
await assert.rejects(realize(i,[b],100),e=>e.receipt.trace.some(t=>t.status==='over-budget'));
// Exercise the actual composite dispatcher with the source kernel unavailable.
const {observeComposite}=await import('../js/composite-ground.mjs');let calls=0;
const unavailable={evaluate(){calls++;throw Error('source unavailable');}};
for(let k=0;k<4;k++){const seed=[rnd(),rnd(),rnd(),rnd()],i=dependencyIntention(laws[k].l,32,all,seed,max),r=await observeComposite(unavailable,i);assert.equal(r.receipt.selected,'driven-ground');assert.deepEqual(r.value,oracle(k,seed,max).map(Number));}assert.equal(calls,0);
console.log('four integrated dispatcher selections passed without source');
// Actual source-kernel qualification is run by make test.
if(process.argv.includes('--wasm')){
  const {readFile}=await import('node:fs/promises'),{createKernel}=await import('../js/vlk.mjs');
  const kernel=await createKernel(await readFile(new URL('../dist/vlk.wasm',import.meta.url)));
  for(let k=0;k<4;k++)for(let j=0;j<12;j++){const seed=[rnd(),rnd(),rnd(),rnd()],n=BigInt(128+rnd()%128);let x=seed;for(let t=0n;t<n;t++){const s=x.reduce((a,v,i)=>a|((v&1)<<i),0),r=kernel.evaluate({seed:x,program:laws[k].l[s],steps:1,budget:64,mode:'reference'});assert.equal(r.status,0);x=r.registers;}assert.deepEqual((await realize(dependencyIntention(laws[k].l,32,all,seed,n),[b],2000003)).value,x);}
  console.log('48 WASM eager comparisons passed');
}
console.log(JSON.stringify({huge,moderate,projected,examples}));
