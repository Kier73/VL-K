// PAC-001: explicit application adapter; logical ticks, not host wall time.
import {createHash,randomUUID} from 'node:crypto';
import {openSync,writeFileSync,fsyncSync,closeSync,renameSync,unlinkSync,readFileSync,statSync} from 'node:fs';
import {dirname} from 'node:path';
import {dependencyIntention} from './dependency-ground.mjs';
import {drivenBinding} from './driven-ground.mjs';
import {realize} from './realization.mjs';
const M=0xffffffffn, MAX=(1n<<64n)-1n, VERSION='vlk.rover.v1', LIMIT=3*1024*1024;
const program=Object.freeze([['mulr',0,0],['mul',0,2],['add',0,3],['copy',3,2],['mulr',3,0],['addr',1,3],['add',2,3]].map(Object.freeze));
const layers=Array.from({length:16},()=>program), sha=v=>createHash('sha256').update(v).digest('hex');
const law=sha(JSON.stringify([VERSION,program,'terrain-sha256-v1','event-before-observation-v1']));
const u32=x=>Number.isInteger(x)&&x>=0&&x<=0xffffffff;
function time(s){if(typeof s!=='string'||!/^(0|[1-9][0-9]{0,19})$/.test(s)||BigInt(s)>MAX)throw Error('invalid tick');return BigInt(s);}
function note(s){if(typeof s!=='string'||s.length>5464||Buffer.from(s,'base64').toString('base64')!==s||Buffer.from(s,'base64').length>4096)throw Error('invalid opaque bytes');return s;}
function initial(seed){if(!Array.isArray(seed)||seed.length!==5||!seed.every(u32))throw Error('invalid seed');return {terrain:seed[0],registers:seed.slice(1),note:'',tick:'0'};}
function advance(r){const [x,y,z]=r,a=(Math.imul(Math.imul(x,x),2)+3)>>>0,c=Math.imul(a,z)>>>0;return [a,(y+c)>>>0,(z+3)>>>0,c];}
function exact(r,n){let [x,y,z,c]=r.map(BigInt);for(let i=0n;i<n;i++){x=(2n*x*x+3n)&M;c=x*z&M;y=(y+c)&M;z=(z+3n)&M;}return [x,y,z,c].map(Number);}
function event(e){if(!Array.isArray(e)||e.length!==3||!Number.isSafeInteger(e[1])||e[1]<-0x80000000||e[1]>0x7fffffff)throw Error('invalid input');time(e[0]);if(e[2]!==null)note(e[2]);return e.slice();}
function apply(s,e){s.registers[2]=(s.registers[2]+e[1])>>>0;if(e[2]!==null)s.note=e[2];}
function stateHash(s){return sha(JSON.stringify([law,s.terrain,s.tick,s.registers,s.note]));}
export function frame(s){const p=s.registers[1]>>>4;return {tick:s.tick,driver:s.registers[0],position:s.registers[1],velocity:s.registers[2],force:s.registers[3],terrain:Array.from({length:9},(_,i)=>sha(JSON.stringify([s.terrain,(p+i-4)>>>0])).slice(0,2)),note:s.note};}
async function segment(s,t){const n=t-time(s.tick);if(n<0n)throw Error('backward segment');if(!n)return;
  const i=dependencyIntention(layers,32,[0,1,2,3],s.registers,n);
  const ref={id:'application-reference',probe:()=>n<=4096n?1+14*Number(n):null,run:()=>{let r=s.registers.slice();for(let k=0n;k<n;k++)r=advance(r);return r;},admit:(_,r)=>{if(JSON.stringify(r)!==JSON.stringify(exact(s.registers,n)))throw Error('reference contradiction');return r;}};
  s.registers=(await realize(i,[ref,drivenBinding()],2000003)).value;s.tick=String(t);
}
function manifest(d){if(!d||d.version!==VERSION||d.law!==law||!Array.isArray(d.events)||d.events.length>512||typeof d.headHash!=='string'||!/^[0-9a-f]{64}$/.test(d.headHash))throw Error('invalid application Ground');initial(d.seed);const head=time(d.head);let last=0n;const events=d.events.map(e=>{const v=event(e),t=time(v[0]);if(t<last||t>head)throw Error('invalid event order');last=t;return v;});return {version:VERSION,law,seed:d.seed.slice(),events,head:d.head,headHash:d.headHash};}
async function reconstruct(d,t){const s=initial(d.seed);for(const e of d.events){const x=time(e[0]);if(x>t)break;await segment(s,x);apply(s,e);}await segment(s,t);return s;}
export class Rover {
  #seed;#events;#state;
  constructor(seed){this.#seed=seed.slice();this.#events=[];this.#state=initial(seed);}
  state(){return structuredClone(this.#state);}
  tick(n){if(!Number.isInteger(n)||n<0||n>100000||time(this.#state.tick)+BigInt(n)>MAX)throw Error('invalid live tick');for(let i=0;i<n;i++)this.#state.registers=advance(this.#state.registers);this.#state.tick=String(time(this.#state.tick)+BigInt(n));return this.state();}
  input(impulse,bytes=null){if(this.#events.length>=512)throw Error('event capacity');const e=event([this.#state.tick,impulse,bytes]);apply(this.#state,e);this.#events.push(e);return this.state();}
  async navigate(t){const target=time(t);if(target<time(this.#state.tick))throw Error('use restore for history');const s=this.state();await segment(s,target);this.#state=s;return this.state();}
  save(path){const d={version:VERSION,law,seed:this.#seed,events:this.#events,head:this.#state.tick,headHash:stateHash(this.#state)};const raw=Buffer.from(JSON.stringify(d));if(raw.length>LIMIT)throw Error('manifest capacity');const tmp=path+'.'+randomUUID()+'.tmp';let fd;try{fd=openSync(tmp,'wx',0o600);writeFileSync(fd,raw);fsyncSync(fd);closeSync(fd);fd=undefined;renameSync(tmp,path);const dir=openSync(dirname(path),'r');try{fsyncSync(dir);}finally{closeSync(dir);}}catch(e){if(fd!==undefined)closeSync(fd);try{unlinkSync(tmp);}catch{}throw e;}return {digest:sha(raw),bytes:raw.length,head:d.head,headHash:d.headHash};}
  static async restore(path,digest,coordinate){if(typeof digest!=='string'||!/^[0-9a-f]{64}$/.test(digest)||statSync(path).size>LIMIT)throw Error('invalid receipt');const raw=readFileSync(path);if(raw.length>LIMIT||sha(raw)!==digest)throw Error('manifest commitment mismatch');const d=manifest(JSON.parse(raw)),head=time(d.head),t=coordinate===undefined?head:time(coordinate);if(t>head)throw Error('outside retained history');const final=await reconstruct(d,head);if(stateHash(final)!==d.headHash)throw Error('head observation mismatch');const r=new Rover(d.seed);r.#state=t===head?final:await reconstruct(d,t);r.#events=d.events.filter(e=>time(e[0])<=t);return r;}
}
