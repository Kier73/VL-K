// Async BlockDevice adapter: one persistent worker, serialized admitted requests.
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { requireReceipt } from './coordinate-witness.mjs';
const LIMIT = 1024*1024;
export class HistoryDevice {
  #child; #lines; #pending; #failure; #tail=Promise.resolve(); #receipt; #seq=0; #done=0; #wait=[]; #closed=false; #ended; #queued=0;
  static async open(path, {branch='main', pages, python='python3', expected}={}) {
    const d=new HistoryDevice();
    d.#child=spawn(python,[fileURLToPath(new URL('./ground_worker.py',import.meta.url)),path,branch,...(pages===undefined?[]:[String(pages)])],{stdio:['pipe','pipe','inherit']});
    d.#ended=new Promise(resolve=>d.#child.once('close',resolve));
    d.#lines=createInterface({input:d.#child.stdout,crlfDelay:Infinity});
    d.#lines.on('line',line=>{
      if(!d.#pending){d.#fail(Error('unsolicited worker response'));return;}
      let r;try{r=JSON.parse(line);}catch(e){d.#fail(e);return;}
      if(r.ok!==true){d.#fail(Error(r.error||'worker refusal'));return;}
      const p=d.#pending;d.#pending=undefined;clearTimeout(p.timer);p.resolve(r.value);
    });
    d.#child.on('error',e=>d.#fail(e));d.#child.stdin.on('error',e=>d.#fail(e));
    d.#child.on('exit',(code,signal)=>d.#fail(Error('Ground worker exited: '+(signal??code))));
    try{d.#receipt=await d.#response();if(expected!==undefined){requireReceipt(d.#receipt,expected);if(expected.branch!==d.#receipt.branch||expected.dirty!==false||d.#receipt.dirty!==false)throw Error('branch seal mismatch');}return d;}catch(e){d.abort();await d.close();throw e;}
  }
  #fail(e){if(this.#failure)return;this.#failure=e;const p=this.#pending;this.#pending=undefined;if(p){clearTimeout(p.timer);p.reject(e);}for(const w of this.#wait)w.reject(e);this.#wait=[];this.#child.kill();}
  #response(){if(this.#failure)return Promise.reject(this.#failure);return new Promise((resolve,reject)=>{const timer=setTimeout(()=>this.#fail(Error('Ground worker timeout')),30000);this.#pending={resolve,reject,timer};});}
  #enqueue(q,apply){if(this.#closed)return Promise.reject(Error('device closed'));if(this.#queued>=32)return Promise.reject(Error('pathway queue full'));this.#queued++;const run=this.#tail.then(async()=>{if(this.#failure)throw this.#failure;const result=this.#response();this.#child.stdin.write(JSON.stringify(q)+'\n');return apply(await result);});const settled=run.finally(()=>{this.#queued--;});this.#tail=settled.catch(()=>{});return settled;}
  get size(){return this.#receipt.pages*4096;} get blockSize(){return 512;} get persistent(){return true;} get flags(){return 2;} get flushSeq(){return this.#seq;}
  receipt(){if(this.#failure)throw this.#failure;return {...this.#receipt};}
  #range(off,views){if(!Array.isArray(views)||views.some(v=>!(v instanceof Uint8Array)))throw TypeError('byte views');const n=views.reduce((a,v)=>a+v.length,0);if(!Number.isSafeInteger(off)||off<0||off%512||n%512||n>LIMIT||off>this.size||n>this.size-off)throw RangeError('sector range');return n;}
  read(off,views){const length=this.#range(off,views);const targets=views.slice();return this.#enqueue({op:'read',off,length},value=>{const raw=Buffer.from(value,'base64');if(raw.length!==length){const e=Error('worker read length');this.#fail(e);throw e;}let at=0;for(const v of targets){v.set(raw.subarray(at,at+v.length));at+=v.length;}});}
  write(off,views){const n=this.#range(off,views);const data=Buffer.concat(views,n).toString('base64');return this.#enqueue({op:'write',off,data},r=>{this.#receipt=r;});}
  flush(){const seq=++this.#seq;return this.#enqueue({op:'flush'},r=>{this.#receipt=r;this.#done=seq;this.#wait=this.#wait.filter(w=>{if(w.after<seq){w.resolve();return false;}return true;});return {...r};});}
  whenFlushed(after){if(this.#done>after)return Promise.resolve();if(this.#failure||this.#closed)return Promise.reject(this.#failure??Error('device closed'));return new Promise((resolve,reject)=>this.#wait.push({after,resolve,reject}));}
  witness(revision,coordinate){return this.#enqueue({op:'witness',revision,coordinate},r=>r);}
  // A flush receipt is a durable storage seal, not a machine snapshot.
  async seal(){return this.flush();}
  fork(name){return this.#enqueue({op:'fork',name},r=>{this.#receipt=r;});}
  abort(){this.#closed=true;this.#fail(Error('device aborted'));this.#child.kill('SIGKILL');}
  async close(){if(!this.#closed){this.#closed=true;await this.#tail;if(!this.#failure)this.#child.stdin.end();}await this.#ended;}
}
