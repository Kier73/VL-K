import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const mod=await WebAssembly.compile(await readFile(new URL('../dist/vlk.wasm',import.meta.url)));
const k=(await WebAssembly.instantiate(mod)).exports;
let rng=123456789;
const rand=()=>{rng^=rng<<13;rng^=rng>>>17;rng^=rng<<5;return rng>>>0;};
const U=x=>x>>>0;
function load(seed,ops) { k.vk1_begin(); seed.forEach((v,i)=>assert.equal(k.vk1_seed(i,v),0)); ops.forEach(q=>assert.equal(k.vk1_append(...q),0)); }
function run(t,mode,budget=1000000) { assert.equal(k.vk1_run(BigInt(t),budget,mode),0); return Array.from({length:4},(_,i)=>U(k.vk1_result(i))); }
function reference(seed,ops,t) {let s=[...seed];for(let j=0;j<t;j++) for(const [op,d,x] of ops) { switch(op) {case 1:s[d]=x;break;case 2:s[d]=s[x];break;case 3:s[d]=U(s[d]+x);break;case 4:s[d]=U(Math.imul(s[d],x));break;case 5:s[d]=U(s[d]+s[x]);break;case 6:s[d]=U(Math.imul(s[d],s[x]));break;} }return s;}
for(let i=0;i<2000;i++) { const seed=Array.from({length:4},rand), ops=Array.from({length:1+rand()%32},()=>{let op=1+rand()%5;return [op,rand()%4,op===2||op===5?rand()%4:rand()];}), t=rand()%100; load(seed,ops); const expect=reference(seed,ops,t); assert.deepEqual(run(t,1),expect);assert.deepEqual(run(t,2),expect);assert.deepEqual(run(t,0),expect); }
console.log('K1 wasm: 2000 randomized programs, 3 modes vs independent reference');
load([0,1,0,0],[[5,0,1],[5,1,0]]); const t=1000000000000n;
const fib=n=>{if(n===0n)return [0n,1n];const [a,b]=fib(n>>1n),c=(a*(2n*b-a))&0xffffffffn,d=(a*a+b*b)&0xffffffffn;return n&1n?[d,(c+d)&0xffffffffn]:[c,d];};
const f=fib(2n*t); assert.deepEqual(run(t,0),[Number(f[0]),Number(f[1]),0,0]);assert.equal(k.vk1_method(),2);let cost=k.vk1_work();console.log('K1 coupled recurrence:',String(t),'blocks,',cost,'charged work units, state',run(t,0));
assert.equal(k.vk1_run(t,cost-1,0),-4);assert.equal(k.vk1_result(0),0);assert.equal(k.vk1_run(t,cost,0),0);
load([2,3,0,0],[[6,0,1]]);assert.deepEqual(run(5,0),[486,3,0,0]);assert.equal(k.vk1_method(),1);assert.equal(k.vk1_run(5n,4,0),-4);assert.equal(k.vk1_run(5n,100,2),-1);
assert.equal(k.vk1_append(2,0,4),-1);assert.equal(k.vk1_append(9,0,0),-1);
load([1,2,3,4],[]);assert.deepEqual(run(2n**64n-1n,0,0),[1,2,3,4]);
load([1,0,0,0],[[3,0,1]]);assert.deepEqual(run(2n**64n-1n,0),[0,0,0,0]);
console.log('K1 wasm: nonlinear fallback, exact budget, malformed instruction, empty block, max coordinate');
