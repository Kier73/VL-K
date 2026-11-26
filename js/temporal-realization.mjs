// Two actual execution modes of the original WASM nucleus, one exact scalar domain.
import {realize} from './realization.mjs';
const MASK=0xffffffffn;
function u32(x){return Number.isInteger(x)&&x>=0&&x<=0xffffffff;}
function expected(i){
  let a=BigInt(i.a),b=BigInt(i.b),x=BigInt(i.seed),n=BigInt(i.steps);
  while(n){if(n&1n)x=(a*x+b)&MASK;n>>=1n;b=(a*b+b)&MASK;a=a*a&MASK;}
  return Number(x);
}
export function temporalIntention(seed,a,b,steps){
  if(![seed,a,b].every(u32)||typeof steps!=='bigint'||steps<0n||steps>=1n<<64n)throw RangeError('invalid affine intention');
  return Object.freeze({domain:'vlk.affine-u32.v1',seed,a,b,steps:steps.toString()});
}
export function temporalBindings(kernel){
  const geometry=i=>{if(i.domain!=='vlk.affine-u32.v1')return null;const n=BigInt(i.steps);if(![i.seed,i.a,i.b].every(u32)||n<0n||n>=1n<<64n||n.toString()!==i.steps)throw Error('invalid intention');return n;};
  function cost(i,mode){const n=geometry(i);if(n===null)return null;let v=n,ground=n?10:0,verify=1;while(v){if(v&1n)ground+=25;v>>=1n;if(v)ground+=125;verify+=3;}
    const work=mode==='reference'?2n*n:BigInt(ground);return work>1000000n?null:Number(work)+verify;}
  return ['reference','ground'].map(mode=>({id:'wasm-'+mode,probe:i=>cost(i,mode),run:(i,reserved)=>kernel.evaluate({seed:[i.seed,0,0,0],program:[['mul',0,i.a],['add',0,i.b]],steps:i.steps,budget:reserved,mode}),admit:(i,r)=>{
    if(r.status!==0||r.registers?.length!==4||r.registers[0]!==expected(i)||r.registers.slice(1).some(x=>x!==0))throw Error('affine observation mismatch');return r.registers[0];
  }}));
}
export function observeTemporal(kernel,intention,budget){return realize(intention,temporalBindings(kernel),budget);}
