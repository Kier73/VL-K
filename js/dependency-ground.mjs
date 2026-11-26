// Source-qualified precision propagation over the four-register WASM algebra.
import {createHash} from 'node:crypto';
import {realize} from './realization.mjs';
const DOMAIN='vlk.dependency-ground.v1', MAX=1n<<64n, MASK=0xffffffffn;
const u32=x=>Number.isInteger(x)&&x>=0&&x<=0xffffffff;
const reg=x=>Number.isInteger(x)&&x>=0&&x<4;
function normalize(layers){
  if(!Array.isArray(layers)||layers.length!==16)throw Error('16 parity layers required');
  return Object.freeze(layers.map(p=>{
    if(!Array.isArray(p)||p.length<1||p.length>64)throw Error('invalid layer');
    return Object.freeze(p.map(q=>{if(!Array.isArray(q)||q.length!==3||!reg(q[1])||!(['set','add','mul'].includes(q[0])&&u32(q[2])||['copy','addr','mulr'].includes(q[0])&&reg(q[2])))throw Error('unqualified opcode');return Object.freeze([...q]);}));
  }));
}
const hash=(p,b,targets)=>createHash('sha256').update(JSON.stringify([DOMAIN,p,b,targets])).digest('hex');
function selector(x){return x.reduce((s,v,i)=>s|((v&1)<<i),0);}
function step(p,seed){const x=[...seed];for(const [op,d,v] of p)x[d]=(op==='set'?v:op==='copy'?x[v]:op==='add'?x[d]+v:op==='mul'?Math.imul(x[d],v):op==='addr'?x[d]+x[v]:Math.imul(x[d],x[v]))>>>0;return x;}
function exact(p,seed){const x=[...seed];for(const [op,d,v] of p){const b=BigInt(v);x[d]=(op==='set'?b:op==='copy'?x[v]:op==='add'?x[d]+b:op==='mul'?x[d]*b:op==='addr'?x[d]+x[v]:x[d]*x[v])&MASK;}return x;}
function v2(x){if(!x)return 32;let k=0;while(x%2===0){x/=2;k++;}return k;}
// Each row maps initial agreement bounds to a minimum of shifted bounds.
// 32 is both the saturation value and the absence of a dependency.
function layer(p,s){
  let rows=Array.from({length:4},(_,i)=>Array.from({length:4},(_,j)=>i===j?0:32));
  const parity=Array.from({length:4},(_,i)=>(s>>i)&1), cap=x=>Math.min(32,x), shift=(r,k)=>r.map(x=>cap(x+k)), min=(a,b)=>a.map((x,i)=>Math.min(x,b[i]));
  for(const [op,d,v] of p){const a=parity[d],b=reg(v)?parity[v]:0;let r=rows[d];
    if(op==='set'){r=[32,32,32,32];parity[d]=v&1;}
    else if(op==='copy'){r=rows[v].slice();parity[d]=b;}
    else if(op==='add')parity[d]=(a+v)&1;
    else if(op==='mul'){r=shift(r,v2(v));parity[d]=a*(v&1);}
    else if(op==='addr'){r=d===v?shift(r,1):min(r,rows[v]);parity[d]=(a+b)&1;}
    else{r=d===v?shift(r,1):min(shift(r,1-b),shift(rows[v],1-a));parity[d]=a*b;}
    rows[d]=r;
  }
  return {next:selector(parity),rows};
}
const apply=(m,k)=>m.map(r=>Math.min(32,...r.map((w,j)=>w+k[j])));
function plan(p,b,targets){
  const layers=p.map(layer);for(let s=0;s<16;s++){const seed=Array.from({length:4},(_,i)=>BigInt((s>>i)&1));if(selector(exact(p[s],seed).map(Number))!==layers[s].next)throw Error('selector contradiction');}
  const paths=layers.map((_,start)=>{const seen=new Map(),path=[];let x=start;while(!seen.has(x)){seen.set(x,path.length);path.push(x);x=layers[x].next;}const tail=seen.get(x),period=path.length-tail,cycle=path.slice(tail);
    let k=[1,1,1,1],bound=null,agreement;
    // Compare phase-aligned states at tail and tail+period. Monotone iteration
    // of the cycle map from the all-one vector reaches a fixed point in <=124 increases.
    for(let j=0;j<=124;j++){
      let q=k,ok=true;for(const s of cycle){if(targets.some(r=>q[r]<b))ok=false;q=apply(layers[s].rows,q);}
      if(ok){bound=tail+j*period;agreement=k;break;}
      if(q.every((v,i)=>v===k[i])){agreement=k;break;}k=q;
    }
    return {tail,period,bound,agreement};
  });return {layers,paths};
}
export function dependencyIntention(layers,bits,targets,seed,steps){const p=normalize(layers);if(!Number.isInteger(bits)||bits<1||bits>32||!Array.isArray(targets)||!targets.length||targets.length>4||targets.some(x=>!reg(x))||new Set(targets).size!==targets.length||!Array.isArray(seed)||seed.length!==4||!seed.every(u32)||typeof steps!=='bigint'||steps<0n||steps>=MAX)throw Error('invalid dependency intention');const t=Object.freeze([...targets]);return Object.freeze({domain:DOMAIN,layers:p,bits,targets:t,seed:Object.freeze([...seed]),steps:String(steps),source:hash(p,bits,t)});}
export function compileDependencies(layers,bits,targets){const i=dependencyIntention(layers,bits,targets,[0,0,0,0],0n);return {source:i.source,...plan(i.layers,bits,i.targets)};}
function reduced(n,path){if(path.bound===null)return null;const t=BigInt(path.bound);return n<t?Number(n):Number(t+(n-t)%BigInt(path.period));}
export function dependencyBindings(kernel){
  const resolve=i=>{if(i.domain!==DOMAIN)return null;const j=dependencyIntention(i.layers,i.bits,i.targets,i.seed,BigInt(i.steps));if(j.source!==i.source||j.steps!==i.steps)throw Error('invalid source');const law=plan(j.layers,j.bits,j.targets);return {n:BigInt(j.steps),path:law.paths[selector(j.seed)],length:Math.max(...j.layers.map(p=>p.length))};};
  const project=(i,x)=>i.targets.map(r=>Number(BigInt(x[r])&((1n<<BigInt(i.bits))-1n)));
  const verify=(i,n)=>{let x=i.seed.map(BigInt);for(let k=0;k<n;k++)x=exact(i.layers[selector(x.map(Number))],x);return project(i,x);};
  const same=(a,b)=>Array.isArray(a)&&a.length===b.length&&a.every((x,i)=>x===b[i]);
  return [{id:'wasm-dependency-reference',probe:i=>{const a=resolve(i);if(!a)return null;const w=a.n*BigInt(a.length);return w>1000000n?null:2*Number(w)+1;},run:i=>{let x=[...i.seed];for(let k=0;k<Number(BigInt(i.steps));k++){const r=kernel.evaluate({seed:x,program:i.layers[selector(x)],steps:1,budget:64,mode:'reference'});if(r.status!==0||r.registers?.length!==4||!r.registers.every(u32))throw Error('reference failed');x=r.registers;}return project(i,x);},admit:(i,r)=>{if(!same(r,verify(i,Number(BigInt(i.steps)))))throw Error('reference contradiction');return r;}},
  {id:'dependency-ground',probe:i=>{const a=resolve(i);if(!a)return null;const t=reduced(a.n,a.path);return t===null?null:2*t*a.length+5;},run:i=>{const a=resolve(i),t=reduced(a.n,a.path);if(t===null)throw Error('unqualified projection');let x=[...i.seed];for(let k=0;k<t;k++)x=step(i.layers[selector(x)],x);return {t,value:project(i,x)};},admit:(i,r)=>{const a=resolve(i),t=reduced(a.n,a.path);if(t===null||r.t!==t||!same(r.value,verify(i,t)))throw Error('dependency contradiction');return r.value;}}];
}
export function observeDependencies(kernel,i,budget=2000003){return realize(i,dependencyBindings(kernel),budget);}
