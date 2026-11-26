// Phase-stable nonlinear drivers, then exact affine continuation of their dependents.
import {dependencyIntention,compileDependencies} from './dependency-ground.mjs';
const MASK=0xffffffffn, mod=x=>x&MASK;
const parity=x=>x.reduce((s,v,i)=>s|(Number(BigInt(v)&1n)<<i),0);
function advance(layers,seed,check){const x=seed.slice();for(const [op,d,v] of layers[parity(x)]){if(check){const b=BigInt(v);x[d]=mod(op==='set'?b:op==='copy'?x[v]:op==='add'?x[d]+b:op==='mul'?x[d]*b:op==='addr'?x[d]+x[v]:x[d]*x[v]);}else{x[d]=(op==='set'?v:op==='copy'?x[v]:op==='add'?x[d]+v:op==='mul'?Math.imul(x[d],v):op==='addr'?x[d]+x[v]:Math.imul(x[d],x[v]))>>>0;}}return x;}
function geometry(i){
  const a=dependencyIntention(i.layers,i.bits,i.targets,i.seed,BigInt(i.steps));if(a.domain!==i.domain||a.source!==i.source||a.steps!==i.steps)throw Error('invalid intention');
  const base=compileDependencies(a.layers,32,[0,1,2,3]), n=BigInt(a.steps), s=parity(a.seed), {tail,period}=base.paths[s];
  if(n<BigInt(tail))return null;
  const h=tail+Number((n-BigInt(tail))%BigInt(period)), q=(n-BigInt(h))/BigInt(period);let phase=s;
  for(let k=0;k<h;k++)phase=base.layers[phase].next;
  const programs=[],matrices=[];for(let k=0;k<period;k++){programs.push(a.layers[phase]);matrices.push(base.layers[phase].rows);phase=base.layers[phase].next;}
  let known=[1,1,1,1],j=0;
  // Fixed point of the monotone precision map; full-width stable coordinates only.
  for(;j<124;j++){let next=known;for(const m of matrices)next=m.map(r=>Math.min(32,...r.map((w,k)=>w+next[k])));if(next.every((v,k)=>v===known[k]))break;known=next;}
  const drivers=known.flatMap((v,r)=>v===32?[r]:[]);
  if(!drivers.length||q<=BigInt(j))return null;
  return {a,programs,drivers,prefix:h+j*period,period,cycles:q-BigInt(j),stabilizationCycles:j};
}
const constant=v=>[0n,0n,0n,0n,mod(BigInt(v))];
const variable=i=>Array.from({length:5},(_,j)=>BigInt(i===j));
const isConstant=r=>r!==null&&r.slice(0,4).every(v=>v===0n);
const add=(a,b)=>a&&b&&a.map((v,j)=>mod(v+b[j]));
const scale=(a,b)=>b===0n?constant(0):a&&a.map(v=>mod(v*b));
function affine(p,seed){const rows=seed.map((v,i)=>p.drivers.includes(i)?constant(v):variable(i));
  for(const program of p.programs)for(const [op,d,v] of program){const a=rows[d],b=rows[v];rows[d]=op==='set'?constant(v):op==='copy'?b:op==='add'?add(a,constant(v)):op==='mul'?scale(a,BigInt(v)):op==='addr'?add(a,b):isConstant(a)?scale(b,a[4]):isConstant(b)?scale(a,b[4]):null;}
  return rows;
}
// Separate bounded polynomial checker, specialized only on proven full-width drivers.
function polynomial(p,seed){
  const z='0000',con=v=>BigInt(v)===0n?new Map():new Map([[z,BigInt(v)]]);
  const rows=seed.map((v,i)=>p.drivers.includes(i)?con(v):new Map([[Array.from({length:4},(_,j)=>Number(i===j)).join(''),1n]]));
  function addP(a,b){if(!a||!b)return null;const r=new Map(a);for(const [k,v] of b){const n=mod((r.get(k)??0n)+v);if(n)r.set(k,n);else r.delete(k);}return r.size<=128?r:null;}
  function mulP(a,b){if(a?.size===0||b?.size===0)return new Map();if(!a||!b||a.size*b.size>4096)return null;const r=new Map();for(const [k,v] of a)for(const [l,w] of b){const c=mod(v*w);if(!c)continue;const e=[...k].map((x,i)=>Number(x)+Number(l[i]));if(e.some(x=>x>9))return null;const key=e.join(''),n=mod((r.get(key)??0n)+c);if(n)r.set(key,n);else r.delete(key);}return r.size<=128?r:null;}
  for(const program of p.programs)for(const [op,d,v] of program){const a=rows[d],b=rows[v];rows[d]=op==='set'?con(v):op==='copy'?b:op==='add'?addP(a,con(v)):op==='mul'?mulP(a,con(v)):op==='addr'?addP(a,b):mulP(a,b);}
  return rows.map(r=>{if(!r)return null;const a=constant(0);for(const [k,v] of r){const d=[...k].reduce((s,x)=>s+Number(x),0);if(d>1)return null;a[d?k.indexOf('1'):4]=v;}return a;});
}
function closed(p,rows,seed){for(const i of p.drivers)rows[i]=constant(seed[i]);let good=rows.map(r=>r!==null),changed=true;while(changed){changed=false;for(let i=0;i<4;i++)if(good[i]&&rows[i].slice(0,4).some((v,j)=>v!==0n&&!good[j])){good[i]=false;changed=true;}}if(p.a.targets.some(i=>!good[i]))throw Error('unresolved driven component');return good;}
function powered(rows,good,seed,q,check){
  let x=seed.map(BigInt);
  if(check){let a=rows.map((r,i)=>good[i]?r:null);while(q){if(q&1n)x=x.map((v,i)=>a[i]?mod(a[i][4]+a[i].slice(0,4).reduce((s,c,j)=>s+c*x[j],0n)):v);q>>=1n;if(q)a=a.map(r=>{if(!r)return null;let next=constant(r[4]);for(let j=0;j<4;j++)if(r[j])next=add(next,scale(a[j],r[j]));return next;});}return x;}
  let m=rows.map((r,i)=>good[i]?r:variable(i));m.push([0n,0n,0n,0n,1n]);x.push(1n);const dot=(a,b)=>mod(a.reduce((s,v,j)=>s+v*b[j],0n));while(q){if(q&1n)x=m.map(r=>dot(r,x));q>>=1n;if(q)m=m.map(r=>Array.from({length:5},(_,j)=>dot(r,m.map(s=>s[j]))));}return x;
}
function evaluate(p,check){let seed=check?p.a.seed.map(BigInt):[...p.a.seed];for(let k=0;k<p.prefix;k++)seed=advance(p.a.layers,seed,check);
  const rows=check?polynomial(p,seed):affine(p,seed),good=closed(p,rows,seed),x=powered(rows,good,seed,p.cycles,check),mask=(1n<<BigInt(p.a.bits))-1n;return p.a.targets.map(i=>Number(x[i]&mask));}
export function inspectDriven(i){const p=geometry(i);return p?{drivers:p.drivers,prefix:p.prefix,period:p.period,cycles:String(p.cycles),stabilizationCycles:p.stabilizationCycles}:null;}
export function drivenBinding(){return {id:'driven-ground',probe:i=>{if(i.domain!=='vlk.dependency-ground.v1')return null;const p=geometry(i);return p?25000+2*p.prefix*Math.max(...p.a.layers.map(l=>l.length)):null;},run:i=>{const p=geometry(i);if(!p)throw Error('no stable driver');return evaluate(p,false);},admit:(i,v)=>{const p=geometry(i);if(!p)throw Error('no stable driver');const expected=evaluate(p,true);if(!Array.isArray(v)||v.length!==expected.length||expected.some((x,j)=>x!==v[j]))throw Error('driven contradiction');return v;}};}
