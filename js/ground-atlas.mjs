// A retained finite observation law, not a cache of intention answers.
import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,renameSync,statSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {realize} from './realization.mjs';
import {compileCoordinates} from './finite-coordinate.mjs';
const VERSION='vlk.residue-ground.v1', sha=x=>createHash('sha256').update(x).digest('hex');
const u32=x=>Number.isInteger(x)&&x>=0&&x<=0xffffffff;
function source(program,bits){
  if(!Number.isInteger(bits)||bits<1||bits>12||!Array.isArray(program)||!program.length||program.length>64)throw Error('invalid source geometry');
  return program.map(q=>{if(!Array.isArray(q)||q.length!==3||q[1]!==0||!(['set','add','mul'].includes(q[0])&&u32(q[2])||q[0]==='mulr'&&q[2]===0))throw Error('unqualified source operation');return Object.freeze([...q]);});
}
function step(program,x,bits){let a=BigInt(x),mask=(1n<<BigInt(bits))-1n;for(const [op,,v] of program){const b=BigInt(v);a=(op==='set'?b:op==='add'?a+b:op==='mul'?a*b:a*a)&mask;}return Number(a);}
function key(program,bits){return sha(JSON.stringify([VERSION,bits,program]));}
export function residueIntention(program,bits,seed,steps){
  const p=Object.freeze(source(program,bits));if(!u32(seed)||typeof steps!=='bigint'||steps<0n||steps>=1n<<64n)throw Error('invalid coordinate');
  return Object.freeze({domain:VERSION,source:key(p,bits),program:p,bits,seed,steps:String(steps)});
}
export class GroundAtlas {
  #laws=new Map();
  // Source closure follows from congruence modulo 2^bits of the admitted integer operations.
  discover(kernel,program,bits){
    const p=source(program,bits),n=2**bits,table=[];
    for(let x=0;x<n;x++){const r=kernel.evaluate({seed:[x,0,0,0],program:p,steps:1,budget:64,mode:'reference'});if(r.status!==0||r.registers[0]%n!==step(p,x,bits))throw Error('source observation contradiction');table.push(r.registers[0]%n);}
    return this.#admit(p,bits,table);
  }
  #admit(program,bits,table){
    const p=source(program,bits),n=2**bits,id=key(p,bits);if(!Array.isArray(table)||table.length!==n||table.some((v,x)=>v!==step(p,x,bits)))throw Error('transition law contradiction');
    const coordinates=compileCoordinates(table);
    if(!this.#laws.has(id)&&this.#laws.size>=16)throw Error('atlas capacity');
    this.#laws.set(id,{program:p,bits,table:[...table],coordinates});return id;
  }
  stats(id){const law=this.#laws.get(id);if(!law)throw Error('unknown law');return law.coordinates.stats();}
  save(path){const data=JSON.stringify({version:VERSION,laws:[...this.#laws.values()].map(({program,bits,table})=>({program,bits,table}))});const tmp=path+'.'+randomUUID()+'.tmp';writeFileSync(tmp,data,{flag:'wx',mode:0o600});renameSync(tmp,path);return Buffer.byteLength(data);}
  static open(path){if(statSync(path).size>512*1024)throw Error('atlas size');const a=new GroundAtlas(),d=JSON.parse(readFileSync(path,'utf8'));if(d.version!==VERSION||!Array.isArray(d.laws)||d.laws.length>16)throw Error('atlas format');for(const l of d.laws)a.#admit(l.program,l.bits,l.table);return a;}
  bindings(kernel){
    const resolve=i=>{if(i.domain!==VERSION)return null;const p=source(i.program,i.bits);if(key(p,i.bits)!==i.source||!u32(i.seed)||!/^([0]|[1-9][0-9]{0,19})$/.test(i.steps)||BigInt(i.steps)>=1n<<64n)throw Error('invalid intention');return this.#laws.get(i.source);};
    return [{id:'wasm-reference-residue',probe:i=>{if(i.domain!==VERSION)return null;resolve(i);const work=BigInt(i.steps)*BigInt(i.program.length);return work>1000000n?null:2*Number(work)+1;},run:(i,reserved)=>kernel.evaluate({seed:[i.seed,0,0,0],program:i.program,steps:i.steps,budget:Math.floor((reserved-1)/2),mode:'reference'}),admit:(i,r)=>{if(r.status!==0)throw Error('reference failed');let x=i.seed%2**i.bits;for(let t=0n;t<BigInt(i.steps);t++)x=step(i.program,x,i.bits);if(r.registers[0]%2**i.bits!==x)throw Error('reference contradiction');return x;}},
      {id:'atlas-residue',probe:i=>resolve(i)?130:null,run:i=>resolve(i).coordinates.at(i.seed%2**i.bits,BigInt(i.steps)),admit:(i,r)=>{const law=resolve(i);if(r!==law.coordinates.at(i.seed%2**i.bits,BigInt(i.steps)))throw Error('invalid observation');return r;}}];
  }
  observe(kernel,i,budget=2000003){return realize(i,this.bindings(kernel),budget);}
}
