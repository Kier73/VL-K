import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createKernel} from '../js/vlk.mjs';
import {realize,RealizationRefusal} from '../js/realization.mjs';
import {temporalIntention,temporalBindings,observeTemporal} from '../js/temporal-realization.mjs';
const kernel=await createKernel(await readFile(new URL('../dist/vlk.wasm',import.meta.url)));
let seed=9143;const rnd=()=>seed=(Math.imul(seed,1664525)+1013904223)>>>0;
const selected={},times={discovery:0,realization:0,admission:0,total:0};
function accumulate(r){selected[r.selected]=(selected[r.selected]??0)+1;for(const k of Object.keys(times))times[k]+=r.timing[k];assert(r.charged<=r.budget);}
for(let j=0;j<600;j++){
  const s=rnd(),a=rnd(),b=rnd(),n=j%2?1000+rnd()%4000:rnd()%20;
  let x=s;for(let k=0;k<n;k++)x=(Math.imul(a,x)+b)>>>0;
  const r=await observeTemporal(kernel,temporalIntention(s,a,b,BigInt(n)),20000);assert.equal(r.value,x);accumulate(r.receipt);
}
assert.equal(selected['wasm-reference'],300);assert.equal(selected['wasm-ground'],300);
console.log('600 independently iterated affine observations:',selected, 'phase milliseconds:',times);
const huge=1000000000000n;let last;
for(let j=0;j<64;j++){
  const s=rnd(),b=rnd(),n=huge+BigInt(rnd()),i=temporalIntention(s,1,b,n);
  const r=await observeTemporal(kernel,i,20000);assert.equal(r.value,Number((BigInt(s)+n*BigInt(b))&0xffffffffn));assert.equal(r.receipt.selected,'wasm-ground');last=r.receipt;
}
const max=temporalIntention(7,0xffffffff,9,(1n<<64n)-1n);assert.equal((await observeTemporal(kernel,max,20000)).value,2);
console.log('64 trillion-step translations and max-u64 reflection verified; final receipt:',JSON.stringify(last));
// Force a false candidate and prove fallback uses the independent admission law.
let runs=0;const corrupt={evaluate(q){runs++;const r=kernel.evaluate(q);if(q.mode==='reference')r.registers[0]^=1;return r;}};
const small=temporalIntention(3,5,1,3n),fallback=await observeTemporal(corrupt,small,20000);assert.equal(fallback.value,406);assert.equal(fallback.receipt.selected,'wasm-ground');assert(fallback.receipt.trace.some(t=>t.status==='admission-refused'));assert.equal(runs,2);
runs=0;await assert.rejects(observeTemporal(corrupt,small,2),e=>e instanceof RealizationRefusal&&e.receipt.charged===2);assert.equal(runs,0);
// A failed realization is charged; an over-budget alternative is never called.
const i=Object.freeze({domain:'test'});let called=false;
await assert.rejects(realize(i,[{id:'broken',probe:()=>3,run:()=>{throw Error('fail');},admit:()=>0},{id:'expensive',probe:()=>4,run:()=>{called=true;},admit:()=>0}],8),e=>e.receipt.charged===5&&e.receipt.trace.some(t=>t.status==='over-budget'));assert(!called);
assert.throws(()=>temporalIntention(0,1,0,1n<<64n));assert.equal(temporalBindings(kernel)[0].probe(Object.freeze({domain:'other'})),null);
console.log('corrupt candidate rejected, independent fallback, budget/refusal accounting and domain separation passed');
