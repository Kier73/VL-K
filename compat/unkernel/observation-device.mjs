// A read-only block projection over an admitted immutable coordinate Ground.
import {requireReceipt, verifyWitness} from './coordinate-witness.mjs';
import {realize} from '../../js/realization.mjs';
const PAGE=4096, EMPTY='0'.repeat(64), LIMIT=1024*1024;
export class ObservationDevice {
  #receipt; #routes; #cachePages; #cache=new Map(); #zeros=[]; #busy=0; #timing={discovery:0,realization:0,admission:0,total:0,charged:0}; #stats={attempts:0,refusals:0,verified:0,cache:0,derived:0};
  constructor(receipt,routes,{cachePages=16}={}){
    requireReceipt(receipt,receipt);
    if(!Array.isArray(routes)||routes.length>8||routes.some(r=>typeof r?.observe!=='function')||!Number.isInteger(cachePages)||cachePages<0||cachePages>256)throw Error('invalid realization policy');
    this.#receipt=Object.freeze({...receipt});this.#routes=routes.map(r=>r.observe.bind(r));this.#cachePages=cachePages;
    if(receipt.root===EMPTY)this.#zeros.push([0,receipt.pages]);
  }
  get size(){return this.#receipt.pages*PAGE;} get blockSize(){return 512;} get readOnly(){return true;} get persistent(){return false;}
  stats(){return {...this.#stats};}
  realizationCosts(){return {...this.#timing};}
  async #page(i){
    const intent=Object.freeze({domain:'vlk.block-observation.v1',receipt:this.#receipt,coordinate:i});
    const zero={id:'derived-zero',probe:()=>this.#zeros.some(([lo,hi])=>lo<=i&&i<hi)?1:null,run:()=>new Uint8Array(PAGE),admit:(_,b)=>{this.#stats.derived++;return b;}};
    const cached={id:'retained-page',probe:()=>this.#cache.has(i)?2:null,run:()=>{const b=this.#cache.get(i);if(!b)throw Error('evicted');return b;},admit:(_,b)=>{this.#cache.delete(i);this.#cache.set(i,b);while(this.#cache.size>this.#cachePages)this.#cache.delete(this.#cache.keys().next().value);this.#stats.cache++;return b;}};
    const routes=this.#routes.map((route,j)=>({id:'witness-'+j,probe:()=>3+j,run:async()=>{this.#stats.attempts++;try{return await route(this.#receipt,i);}catch(e){this.#stats.refusals++;throw e;}},admit:(_,w)=>{
      let b;try{b=verifyWitness(w,this.#receipt,i);}catch(e){this.#stats.refusals++;throw e;}
      this.#stats.verified++;
      const depth=w.siblings.length;
      for(let k=0;k<depth;k++)if(w.siblings[k]===EMPTY){const width=2**(depth-1-k),lo=(Math.floor(i/width)^1)*width;if(!this.#zeros.some(([a,z])=>a<=lo&&lo+width<=z))this.#zeros.push([lo,lo+width]);}
      if(b.every(x=>x===0)&&!this.#zeros.some(([a,z])=>a<=i&&i<z))this.#zeros.push([i,i+1]);
      if(this.#cachePages){this.#cache.set(i,b);while(this.#cache.size>this.#cachePages)this.#cache.delete(this.#cache.keys().next().value);}
      return b;
    }}));
    let receipt;
    try{const r=await realize(intent,[zero,cached,...routes],65);receipt=r.receipt;return r.value;}
    catch(e){receipt=e.receipt;throw e;}
    finally{if(receipt){for(const k of ['discovery','realization','admission','total'])this.#timing[k]+=receipt.timing[k];this.#timing.charged+=receipt.charged;}}
  }
  async read(off,views){
    if(!Array.isArray(views)||views.some(v=>!(v instanceof Uint8Array)))throw TypeError('byte views');
    const targets=views.slice(),n=targets.reduce((a,v)=>a+v.length,0);
    if(!Number.isSafeInteger(off)||off<0||off%512||n%512||n>LIMIT||off>this.size||n>this.size-off)throw RangeError('sector range');
    if(this.#busy>=8)throw Error('observation queue full');this.#busy++;
    try{const out=new Uint8Array(n);for(let at=0;at<n;){const i=Math.floor((off+at)/PAGE),within=(off+at)%PAGE,take=Math.min(n-at,PAGE-within);out.set((await this.#page(i)).subarray(within,within+take),at);at+=take;}
      let at=0;for(const v of targets){v.set(out.subarray(at,at+v.length));at+=v.length;}
    }finally{this.#busy--;}
  }
  write(){throw Error('read-only Ground');}
}
