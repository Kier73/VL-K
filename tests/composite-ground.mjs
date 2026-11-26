import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createKernel} from '../js/vlk.mjs';
import {dependencyIntention,compileDependencies} from '../js/dependency-ground.mjs';
import {observeComposite,inspectComposite,compositeBindings} from '../js/composite-ground.mjs';
import {realize} from '../js/realization.mjs';
const kernel=await createKernel(await readFile(new URL('../dist/vlk.wasm',import.meta.url)));
let calls=0;const counted={evaluate(q){calls++;return kernel.evaluate(q);}};
const swap=[['copy',2,0],['copy',0,1],['copy',1,2],['add',3,1]],square=[['copy',2,0],['copy',0,1],['mulr',0,0],['copy',1,2],['add',3,1]];
const mixed=Array.from({length:16},(_,s)=>s&8?square:swap), all=[0,1,2,3],mask=0xffffffffn,max=(1n<<64n)-1n;
const same=p=>Array.from({length:16},()=>p);
let rng=1729;const rnd=()=>rng=(Math.imul(rng,1664525)+1013904223)>>>0;
function pair(seed,n){let [x,y,,c]=seed.map(BigInt),q=n/2n;let v=c&1n?y:x;for(let j=0n;j<q&&j<32n;j++)v=v*v&mask;if(c&1n)y=v;else x=v;if(n&1n)[x,y]=[c&1n?y*y&mask:y,x];return [x,y];}
function mixedOracle(seed,n){const [x,y]=pair(seed,n),z=n?pair(seed,n-1n)[0]:BigInt(seed[2]);return [x,y,z,(BigInt(seed[3])+n)&mask].map(Number);}
function eager(l,s,n){let x=s;for(let j=0;j<n;j++){const p=x.reduce((a,v,i)=>a|((v&1)<<i),0),r=kernel.evaluate({seed:x,program:l[p],steps:1,budget:64,mode:'reference'});assert.equal(r.status,0);x=r.registers;}return x;}
assert(compileDependencies(mixed,32,all).paths.every(p=>p.bound===null));
for(let j=0;j<128;j++){const seed=[rnd(),rnd(),rnd(),(rnd()&0xfffffffe|j%2)>>>0],n=max-BigInt(j)*123456789n;const i=dependencyIntention(mixed,32,all,seed,n),p=inspectComposite(i);assert(p.components.some(c=>c.method==='contracting'));assert(p.components.some(c=>c.method==='affine'));const before=calls,r=await observeComposite(counted,i);assert.equal(r.receipt.selected,'composite-ground');assert.deepEqual(r.value,mixedOracle(seed,n));assert.equal(calls,before);}
for(let j=0;j<64;j++){const seed=[rnd(),rnd(),rnd(),rnd()],n=BigInt(j*3);const i=dependencyIntention(mixed,32,all,seed,n);assert.deepEqual((await observeComposite(counted,i)).value,eager(mixed,seed,Number(n)));assert.deepEqual(mixedOracle(seed,n),eager(mixed,seed,Number(n)));}
// A noncontracting affine coupled block is driven by a separate contracting nonlinear lane.
const coupled=same([['mulr',0,0],['addr',1,2],['add',1,7],['add',2,3],['add',3,1]]);
for(let j=0;j<96;j++){const seed=[rnd(),rnd(),rnd(),rnd()],n=max-BigInt(j),i=dependencyIntention(coupled,32,[3,0,2,1],seed,n);const before=calls,r=await observeComposite(counted,i);let [x,y,z,c]=seed.map(BigInt);for(let k=0;k<32;k++)x=x*x&mask;const expected=[c+n,x,z+3n*n,y+n*z+3n*n*(n-1n)/2n+7n*n].map(v=>Number(v&mask));assert.deepEqual(r.value,expected);assert.equal(calls,before);}
// Transient selector phase: clock is set once, then affine block follows fixed parity.
const tail=Array.from({length:16},(_,s)=>s&8?[['mulr',0,0],['add',1,2],['add',2,4]]:[['set',3,1],['add',1,1]]);
for(let j=0;j<32;j++){const seed=[rnd(),rnd(),rnd(),rnd()&0xfffffffe>>>0].map(x=>x>>>0),n=max-BigInt(j);const i=dependencyIntention(tail,32,all,seed,n);let x=BigInt(seed[0]);for(let k=0;k<32;k++)x=x*x&mask;assert.deepEqual((await observeComposite(counted,i)).value,[x,BigInt(seed[1])+1n+2n*(n-1n),BigInt(seed[2])+4n*(n-1n),1n].map(v=>Number(v&mask)));}
const unknown=same([['copy',1,0],['mulr',1,0],['mul',1,2],['addr',0,1]]),bad=dependencyIntention(unknown,32,[0],[1,0,0,0],max);assert.equal(inspectComposite(bad).components[0].method,'unresolved');await assert.rejects(observeComposite(counted,bad),/no sufficient/);
const i=dependencyIntention(mixed,32,all,[1,3,9,2],max),b=compositeBindings(counted).at(-1);await assert.rejects(realize(i,[{...b,run:q=>{const x=b.run(q);x[1]^=1;return x;}}],2000003),e=>e.receipt.trace.some(t=>t.status==='admission-refused'));
console.log('128 mixed full-state, 96 coupled affine/nonlinear, 32 selector-tail huge-coordinate results, 64 moderate WASM checks, unresolved and corrupted proposals refused');
console.log(inspectComposite(i));
