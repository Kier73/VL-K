// A source-qualified, parity-selected composition of u32 operations.
import {createHash} from 'node:crypto';
import {realize} from './realization.mjs';
const DOMAIN='vlk.layered-parity-u32.v1', MAX=1n<<64n;
const u32=x=>Number.isInteger(x)&&x>=0&&x<=0xffffffff;
function normalize(layers){
  if(!Array.isArray(layers)||layers.length!==2)throw Error('two parity layers required');
  return Object.freeze(layers.map(p=>{
    if(!Array.isArray(p)||p.length<1||p.length>64)throw Error('invalid layer length');
    return Object.freeze(p.map(q=>{
      if(!Array.isArray(q)||q.length!==3||q[1]!==0||!(['set','add','mul'].includes(q[0])&&u32(q[2])||q[0]==='mulr'&&q[2]===0))throw Error('unqualified layer operation');
      return Object.freeze([...q]);
    }));
  }));
}
const identity=(layers,bits)=>createHash('sha256').update(JSON.stringify([DOMAIN,bits,layers])).digest('hex');
function step(p,x){for(const [op,,v] of p)x=(op==='set'?v:op==='add'?x+v:op==='mul'?Math.imul(x,v):Math.imul(x,x))>>>0;return x;}
function exact(p,x){for(const [op,,v] of p){const b=BigInt(v);x=(op==='set'?b:op==='add'?x+b:op==='mul'?x*b:x*x)&0xffffffffn;}return x;}
export function layeredIntention(layers,bits,seed,steps){
  const p=normalize(layers);if(!Number.isInteger(bits)||bits<1||bits>32||!u32(seed)||typeof steps!=='bigint'||steps<0n||steps>=MAX)throw Error('invalid intention coordinate');
  return Object.freeze({domain:DOMAIN,layers:p,bits,seed,steps:String(steps),source:identity(p,bits)});
}
// A conservative lower bound on extra known low bits preserved by each layer.
// Squaring gains >=1 bit for equal parity; multiplying by 2^k gains k.
function gain(program){let g=0;for(const [op,,v] of program){if(op==='set'||op==='mul'&&v===0)return 32;if(op==='mulr')g++;if(op==='mul'&&v){let a=v;while(a%2===0){g++;a/=2;}}}return Math.min(32,g);}
function plan(layers,bits){
  const next=layers.map((p,i)=>step(p,i)&1),gains=layers.map(gain);
  const paths=next.map((_,start)=>{const seen=new Map(),path=[];let x=start;while(!seen.has(x)){seen.set(x,path.length);path.push(x);x=next[x];}const tail=seen.get(x),period=path.length-tail;
    const g=path.slice(tail).reduce((a,p)=>a+gains[p],0);
    const bound=bits===1?tail:g>0?tail+Math.ceil((bits-1)/g)*period:null;
    return Object.freeze({tail,period,gain:g,bound});});
  return Object.freeze({next:Object.freeze(next),gains:Object.freeze(gains),paths:Object.freeze(paths)});
}
// Admission derives its own parity path using exact arithmetic and verifies
// gain certificates from the allowed opcodes, without executing the long orbit.
function admittedPlan(i){
  const p=normalize(i.layers);
  if(!Number.isInteger(i.bits)||i.bits<1||i.bits>32||!u32(i.seed)||typeof i.steps!=='string'||! /^(0|[1-9][0-9]{0,19})$/.test(i.steps)||BigInt(i.steps)>=MAX||identity(p,i.bits)!==i.source)throw Error('invalid layered source');
  const law=plan(p,i.bits);
  for(let parity=0;parity<2;parity++)if(Number(exact(p[parity],BigInt(parity))&1n)!==law.next[parity])throw Error('parity contradiction');
  return {p,law,path:law.paths[i.seed&1],n:BigInt(i.steps)};
}
function reduced(n,path){if(path.bound===null)return null;const t=BigInt(path.bound);return n<t?Number(n):Number(t+(n-t)%BigInt(path.period));}
function referenceCost(i,n){const w=n*BigInt(Math.max(...i.layers.map(p=>p.length)));return w>1000000n?null:2*Number(w)+1;}
function groundCost(i,path,n){const t=reduced(n,path);return t===null?null:2*t*Math.max(...i.layers.map(p=>p.length))+5;}
export function compileLayered(layers,bits){const i=layeredIntention(layers,bits,0,0n);return Object.freeze({source:i.source,bits,layers:i.layers,certificate:plan(i.layers,bits)});}
export function layeredBindings(kernel){
  const resolve=i=>i.domain===DOMAIN?admittedPlan(i):null;
  const verify=(i,t)=>{let x=BigInt(i.seed);for(let k=0;k<t;k++)x=exact(i.layers[Number(x&1n)],x);return Number(x&((1n<<BigInt(i.bits))-1n));};
  return [
    {id:'wasm-layered-reference',probe:i=>{const a=resolve(i);return a?referenceCost(i,a.n):null;},run:i=>{let x=i.seed;for(let k=0;k<Number(BigInt(i.steps));k++){const r=kernel.evaluate({seed:[x,0,0,0],program:i.layers[x&1],steps:1,budget:64,mode:'reference'});if(r.status!==0||r.registers?.length!==4||!u32(r.registers[0])||r.registers.slice(1).some(v=>v!==0))throw Error('source refused');x=r.registers[0];}return x%2**i.bits;},admit:(i,r)=>{if(r!==verify(i,Number(BigInt(i.steps))))throw Error('reference contradiction');return r;}},
    {id:'layered-contracting-ground',probe:i=>{const a=resolve(i);return a?groundCost(i,a.path,a.n):null;},run:i=>{const a=resolve(i),t=reduced(a.n,a.path);if(t===null)throw Error('noncontracting cycle');let x=i.seed;for(let k=0;k<t;k++)x=step(i.layers[x&1],x);return {t,value:x%2**i.bits};},admit:(i,r)=>{const a=resolve(i),t=reduced(a.n,a.path);if(t===null||r.t!==t||r.value!==verify(i,t))throw Error('layered Ground contradiction');return r.value;}}
  ];
}
export function observeLayered(kernel,i,budget=2000003){return realize(i,layeredBindings(kernel),budget);}
