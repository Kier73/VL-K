// State observation digest identifies logical bytes, not their encoding.
import { createHash, randomUUID } from 'node:crypto';
import { openSync, closeSync, readFileSync, writeFileSync, fsyncSync, renameSync, unlinkSync, existsSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { StructuralDisk } from './structural-disk.mjs';
const PAGE=4096, MAX=64*1024*1024, HEAD=80, MAGIC=Buffer.from('VLKGRD01');
const digest = b => createHash('sha256').update(b).digest();
function logical(disk) {
  const h=createHash('sha256'), b=new Uint8Array(65536);
  for(let off=0;off<disk.size;off+=b.length){const v=b.subarray(0,Math.min(b.length,disk.size-off));disk.read(off,[v]);h.update(v);}
  return h.digest();
}
function encode(disk,id,revision) {
  const objects=[], ids=new Map(), runs=[];
  for(const [index,p] of disk.records()){
    const key=Buffer.from(p).toString('hex');let object=ids.get(key);
    if(object===undefined){object=objects.length;ids.set(key,object);objects.push(Buffer.from(p));}
    const r=runs.at(-1);if(r&&r[0]+r[1]===index&&r[2]===object)r[1]++;else runs.push([index,1,object]);
  }
  const head=Buffer.alloc(HEAD);MAGIC.copy(head);head.writeUInt32LE(disk.size,8);head.writeUInt32LE(revision,12);Buffer.from(id,'hex').copy(head,16);
  head.writeUInt32LE(objects.length,32);head.writeUInt32LE(runs.length,36);logical(disk).copy(head,40);
  const parts=[head];for(const b of objects){const n=Buffer.alloc(2);n.writeUInt16LE(b.length);parts.push(n,b);}
  for(const r of runs){const b=Buffer.alloc(12);r.forEach((x,i)=>b.writeUInt32LE(x,4*i));parts.push(b);}
  const body=Buffer.concat(parts);return Buffer.concat([body,digest(body)]);
}
function decode(b) {
  if(b.length<HEAD+32||!b.subarray(0,8).equals(MAGIC)||!digest(b.subarray(0,-32)).equals(b.subarray(-32)))throw Error('Ground encoding integrity');
  const size=b.readUInt32LE(8),revision=b.readUInt32LE(12),id=b.subarray(16,32).toString('hex'),n=b.readUInt32LE(32),m=b.readUInt32LE(36);
  if(!size||size>MAX||size%PAGE||n>size/PAGE||m>size/PAGE||b.subarray(72,80).some(x=>x))throw Error('Ground header');
  const disk=new StructuralDisk(size), objects=[], keys=new Set(), used=new Set();let at=HEAD,end=b.length-32;
  for(let i=0;i<n;i++){
    if(at+2>end)throw Error('Ground object length');const len=b.readUInt16LE(at);at+=2;
    if(!((len>=1&&len<=16)||len===PAGE)||at+len>end)throw Error('Ground object bounds');
    const p=b.subarray(at,at+len),key=p.toString('hex');at+=len;if(keys.has(key)||p.every(x=>x===0))throw Error('Ground object duplication/zero');keys.add(key);
    const page=new Uint8Array(PAGE);for(let j=0;j<PAGE;j++)page[j]=p[j%len];objects.push(page);
  }
  if(end-at!==12*m)throw Error('Ground run length');let prior=0;
  for(let i=0;i<m;i++,at+=12){const start=b.readUInt32LE(at),count=b.readUInt32LE(at+4),object=b.readUInt32LE(at+8);
    if(start<prior||!count||start>size/PAGE||count>size/PAGE-start||object>=n)throw Error('Ground run bounds');
    for(let j=0;j<count;j++)disk.write((start+j)*PAGE,[objects[object]]);prior=start+count;used.add(object);
  }
  if(used.size!==n||!logical(disk).equals(b.subarray(40,72)))throw Error('Ground observation mismatch');
  return {disk,id,revision,observationDigest:b.subarray(40,72).toString('hex')};
}
// One trusted writer per path; no distributed fencing or snapshot claim.
export class GroundDisk {
  #path; #disk; #id; #revision; #observationDigest; #dirty=false; #poison=false; #seq=0; #done=0; #wait=[];
  constructor(path,size) {
    this.#path=resolve(path);
    if(existsSync(this.#path)){
      if(statSync(this.#path).size>MAX+1024*1024)throw Error('Ground file too large');
      const x=decode(readFileSync(this.#path));if(size!==undefined&&size!==x.disk.size)throw Error('Ground size mismatch');
      this.#disk=x.disk;this.#id=x.id;this.#revision=x.revision;this.#observationDigest=x.observationDigest;
    }else{
      if(!Number.isSafeInteger(size)||size<=0||size>MAX||size%PAGE)throw Error('Ground size');
      this.#disk=new StructuralDisk(size);this.#id=randomUUID().replaceAll('-','');this.#revision=0;this.#publish(0);
    }
  }
  get size(){return this.#disk.size;} get blockSize(){return 512;} get flags(){return 2;} get persistent(){return true;} get flushSeq(){return this.#seq;}
  #check(){if(this.#poison)throw Error('Ground publication uncertain; reopen');}
  read(off,views){this.#check();this.#disk.read(off,views);}
  write(off,views){this.#check();this.#disk.write(off,views);this.#dirty=true;}
  stats(){return this.#disk.stats();}
  receipt(){this.#check();return {groundVersion:'vlk.block-ground.v1',identity:this.#id,revision:this.#revision,observationDigest:this.#observationDigest,dirty:this.#dirty};}
  #publish(revision){
    const bytes=encode(this.#disk,this.#id,revision),tmp=this.#path+'.'+randomUUID()+'.tmp';let renamed=false,fd;
    try{fd=openSync(tmp,'wx',0o600);try{writeFileSync(fd,bytes);fsyncSync(fd);}finally{closeSync(fd);}renameSync(tmp,this.#path);renamed=true;
      fd=openSync(dirname(this.#path),'r');try{fsyncSync(fd);}finally{closeSync(fd);}
    }catch(e){if(renamed)this.#poison=true;else try{unlinkSync(tmp);}catch{}throw e;}
    this.#revision=revision;this.#observationDigest=bytes.subarray(40,72).toString('hex');this.#dirty=false;
  }
  flush(){this.#check();const seq=++this.#seq;
    if(this.#dirty){if(this.#revision===0xffffffff)throw Error('Ground revision exhausted');this.#publish(this.#revision+1);}
    this.#done=seq;this.#wait=this.#wait.filter(w=>{if(w.after<seq){w.resolve();return false;}return true;});
  }
  whenFlushed(after){if(this.#done>after)return Promise.resolve();return new Promise(resolve=>this.#wait.push({after,resolve}));}
}
