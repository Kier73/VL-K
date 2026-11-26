// Compose separately qualified temporal observations, with no partial-result admission.
import {dependencyIntention,compileDependencies,dependencyBindings} from './dependency-ground.mjs';
import {realize} from './realization.mjs';
const MASK=0xffffffffn, mod=x=>x&MASK;
const parity=x=>x.reduce((s,v,i)=>s|(Number(BigInt(v)&1n)<<i),0);
const identity=()=>Array.from({length:4},(_,i)=>Array.from({length:5},(_,j)=>BigInt(i===j)));
const constant=v=>[0n,0n,0n,0n,BigInt(v)];
const isConstant=r=>r!==null&&r.slice(0,4).every(v=>v===0n);
const scale=(r,c)=>c===0n?constant(0):r&&r.map(v=>mod(v*c));
const add=(r,s)=>r&&s&&r.map((v,i)=>mod(v+s[i]));
function affine(programs){
  const rows=identity();
  for(const p of programs)for(const [op,d,v] of p){const a=rows[d],b=rows[v];
    rows[d]=op==='set'?constant(v):op==='copy'?b:op==='add'?add(a,constant(v)):op==='mul'?scale(a,BigInt(v)):op==='addr'?add(a,b):isConstant(a)?scale(b,a[4]):isConstant(b)?scale(a,b[4]):null;
  }return rows;
}
// Independent symbolic checker: sparse polynomial ring, bounded terms/degrees.
// Overflow discards the row, never approximates it as affine.
function polynomial(programs){
  const zero='0,0,0,0', con=v=>v===0n?new Map():new Map([[zero,v]]);
  const rows=Array.from({length:4},(_,i)=>new Map([[Array.from({length:4},(_,j)=>Number(i===j)).join(','),1n]]));
  function sum(a,b){if(!a||!b)return null;const r=new Map(a);for(const [k,v] of b){const n=mod((r.get(k)??0n)+v);if(n)r.set(k,n);else r.delete(k);}return r.size<=128?r:null;}
  function prod(a,b){if(a?.size===0||b?.size===0)return new Map();if(!a||!b||a.size*b.size>4096)return null;let r=new Map();for(const [k,v] of a)for(const [l,w] of b){const e=k.split(',').map((x,i)=>Number(x)+Number(l.split(',')[i]));const c=mod(v*w);if(!c)continue;if(e.some(x=>x>64))return null;const key=e.join(','),n=mod((r.get(key)??0n)+c);if(n)r.set(key,n);else r.delete(key);}return r.size<=128?r:null;}
  for(const p of programs)for(const [op,d,v] of p){const a=rows[d],b=rows[v];rows[d]=op==='set'?con(BigInt(v)):op==='copy'?b:op==='add'?sum(a,con(BigInt(v))):op==='mul'?prod(a,con(BigInt(v))):op==='addr'?sum(a,b):prod(a,b);}
  return rows.map(p=>{if(!p)return null;const r=constant(0);for(const [k,v] of p){const e=k.split(',').map(Number),degree=e.reduce((a,b)=>a+b,0);if(degree>1)return null;r[degree?e.indexOf(1):4]=v;}return r;});
}
function closed(rows){let good=rows.map(r=>r!==null),changed=true;while(changed){changed=false;for(let i=0;i<4;i++)if(good[i]&&rows[i].slice(0,4).some((v,j)=>v!==0n&&!good[j])){good[i]=false;changed=true;}}return good;}
function step(layers,seed){const x=[...seed];for(const [op,d,v] of layers[parity(x)])x[d]=(op==='set'?v:op==='copy'?x[v]:op==='add'?x[d]+v:op==='mul'?Math.imul(x[d],v):op==='addr'?x[d]+x[v]:Math.imul(x[d],x[v]))>>>0;return x;}
function exact(layers,seed){const x=[...seed];for(const [op,d,v] of layers[parity(x)]){const c=BigInt(v);x[d]=mod(op==='set'?c:op==='copy'?x[v]:op==='add'?x[d]+c:op==='mul'?x[d]*c:op==='addr'?x[d]+x[v]:x[d]*x[v]);}return x;}
function plan(i,checker=false){
  const a=dependencyIntention(i.layers,i.bits,i.targets,i.seed,BigInt(i.steps));if(a.domain!==i.domain||a.source!==i.source||a.steps!==i.steps)throw Error('invalid source');
  const n=BigInt(a.steps),base=compileDependencies(a.layers,a.bits,a.targets),s=parity(a.seed),{tail,period}=base.paths[s];
  // Move the initial state to the final selector phase, then power whole cycles there.
  const prefix=n<BigInt(tail)?Number(n):tail+Number((n-BigInt(tail))%BigInt(period));
  const cycles=(n-BigInt(prefix))/BigInt(period);let phase=s;
  for(let k=0;k<prefix;k++)phase=base.layers[phase].next;
  const programs=[],matrices=[];for(let k=0;k<period;k++){programs.push(a.layers[phase]);matrices.push(base.layers[phase].rows);phase=base.layers[phase].next;}
  const rows=cycles===0n?identity():(checker?polynomial(programs):affine(programs)),good=closed(rows);
  // Only the requested phase must contract; other phases may permute the lanes.
  let known=[1,1,1,1],bounds=Array(4).fill(null);
  for(let j=0;j<=124;j++){
    for(let r=0;r<4;r++)if(bounds[r]===null&&known[r]>=a.bits)bounds[r]=j;
    let next=known;for(const m of matrices)next=m.map(row=>Math.min(32,...row.map((w,k)=>w+next[k])));
    if(next.every((v,k)=>v===known[k]))break;known=next;
  }
  const targets=a.targets.map(r=>{const b=bounds[r];if(b!==null){const t=prefix+Number(cycles<BigInt(b)?cycles:BigInt(b))*period;return {r,method:'contracting',t};}return good[r]?{r,method:'affine',t:prefix}:{r,method:'unresolved'};});
  return {a,rows,good,targets,prefix,cycles,period};
}
// Homogeneous matrix power over the certified closed affine subspace.
function matrixPower(p,seed){const ids=p.good.flatMap((v,i)=>v?[i]:[]),n=ids.length+1;
  let m=ids.map(i=>[...ids.map(j=>p.rows[i][j]),p.rows[i][4]]);m.push([...ids.map(()=>0n),1n]);let x=[...ids.map(i=>BigInt(seed[i])),1n],q=p.cycles;
  const dot=(a,b)=>mod(a.reduce((v,c,j)=>v+c*b[j],0n));
  while(q){if(q&1n)x=m.map(r=>dot(r,x));q>>=1n;if(q)m=m.map(r=>Array.from({length:n},(_,j)=>dot(r,m.map(s=>s[j]))));}
  return new Map(ids.map((id,i)=>[id,x[i]]));
}
// Checker powers the affine substitution independently, as a composition of rows.
function substitute(p,seed){let rows=p.rows.map((r,i)=>p.good[i]?r:null),x=seed.slice(),q=p.cycles;
  const evalRow=(r,x)=>mod(r[4]+r.slice(0,4).reduce((v,c,j)=>v+c*x[j],0n));
  while(q){if(q&1n)x=x.map((v,i)=>rows[i]?evalRow(rows[i],x):v);q>>=1n;if(q)rows=rows.map(r=>{if(!r)return null;let next=constant(r[4]);for(let j=0;j<4;j++)if(r[j])next=add(next,scale(rows[j],r[j]));return next;});}
  return x;
}
function evaluate(p,checker=false){if(p.targets.some(t=>t.method==='unresolved'))throw Error('unresolved component');const {a}=p,mask=(1n<<BigInt(a.bits))-1n;
  let seed=checker?a.seed.map(BigInt):[...a.seed];const advance=checker?exact:step;for(let k=0;k<p.prefix;k++)seed=advance(a.layers,seed);
  const powered=checker?substitute(p,seed):matrixPower(p,seed);
  return p.targets.map(t=>{if(t.method==='affine')return Number((checker?powered[t.r]:powered.get(t.r))&mask);let x=checker?a.seed.map(BigInt):[...a.seed];for(let k=0;k<t.t;k++)x=advance(a.layers,x);return Number(BigInt(x[t.r])&mask);});
}
export function inspectComposite(i){const p=plan(i);return {prefix:p.prefix,period:p.period,cycles:String(p.cycles),components:p.targets};}
export function compositeBindings(kernel){let last,compiled;const get=i=>{if(i.domain!=='vlk.dependency-ground.v1')return null;if(i!==last){compiled=plan(i);last=i;}return compiled;};
  const composite={id:'composite-ground',probe:i=>{const p=get(i);if(!p||p.targets.some(t=>t.method==='unresolved'))return null;const width=Math.max(...i.layers.map(l=>l.length));return 2*width*(p.prefix+p.targets.filter(t=>t.method==='contracting').reduce((s,t)=>s+t.t,0))+12800;},run:i=>evaluate(get(i)),admit:(i,value)=>{const p=plan(i,true),expected=evaluate(p,true);if(!Array.isArray(value)||value.length!==expected.length||expected.some((x,j)=>x!==value[j]))throw Error('composite contradiction');return value;}};
  return [...dependencyBindings(kernel),composite];}
export function observeComposite(kernel,i,budget=2000003){return realize(i,compositeBindings(kernel),budget);}
