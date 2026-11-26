import assert from 'node:assert/strict';
import {mkdtempSync,rmSync,readFileSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';import {join} from 'node:path';
import {spawnSync} from 'node:child_process';import {createHash} from 'node:crypto';
import {Rover,frame} from '../js/application-ground.mjs';
const dir=mkdtempSync(join(tmpdir(),'vlk-pac-')),path=join(dir,'application.json'),branch=join(dir,'branch.json'),huge=join(dir,'huge.json');
const app=new URL('../js/rover-session.mjs',import.meta.url), seed=[123,7,19,31,0], max=(1n<<64n)-1n,M=0xffffffffn;
function processRun(args,commands,autosave=''){const p=spawnSync(process.execPath,[app.pathname,...args],{input:commands.map(x=>JSON.stringify(x)).join('\n')+'\n',encoding:'utf8',timeout:30000,env:{...process.env,VLK_AUTOSAVE:autosave}});assert.equal(p.status,0,p.stderr);const out=p.stdout.trim().split('\n').map(JSON.parse);assert(out.every(x=>x.ok),p.stdout);return out;}
const tick=count=>({op:'tick',count}), input=(impulse,bytes=null)=>({op:'input',impulse,bytes}), save=path=>({op:'save',path}), observe={op:'observe'};
try{
 const script=[tick(120),input(-9,'AP8BAg=='),tick(333),input(11),input(-3,'AAECAwQ='),tick(500),save(path),tick(251),input(44),tick(101)];
 const live=processRun([],script),seal=live[6].result;assert.equal(seal.head,'953');
 const resumed=processRun([path,seal.digest],[observe,...script.slice(7)]);assert.deepEqual(resumed[0].state,live[6].state);assert.deepEqual(resumed[0].frame,live[6].frame);for(let j=1;j<resumed.length;j++){assert.deepEqual(resumed[j].state,live[j+6].state);assert.deepEqual(resumed[j].frame,live[j+6].frame);}
 const at=processRun([path,seal.digest,'453'],[observe,input(23,'/wA='),tick(500),save(branch)]);assert.deepEqual(at[0].state,live[4].state);
 const separate=processRun([],script.slice(0,5).concat([input(23,'/wA='),tick(500)]));assert.deepEqual(at[2].state,separate.at(-1).state);assert.notDeepEqual(at[2].state,live[6].state);
 const b=await Rover.restore(branch,at[3].result.digest);assert.deepEqual(b.state(),at[2].state);assert.deepEqual((await Rover.restore(path,seal.digest)).state(),live[6].state);
 // Independent eager oracle checks every selected coordinate, including event boundaries.
 let x=seed.slice(1).map(BigInt),bytes='',k=0,historicalChecks=0;const events=[[120,-9,'AP8BAg=='],[453,11,null],[453,-3,'AAECAwQ=']];
 for(let t=0;t<=953;t++){while(k<events.length&&events[k][0]===t){x[2]=(x[2]+BigInt(events[k][1]))&M;if(events[k][2]!==null)bytes=events[k][2];k++;}if(t%29===0||[120,453,953].includes(t)){const r=await Rover.restore(path,seal.digest,String(t));historicalChecks++;assert.deepEqual(r.state(),{terrain:123,tick:String(t),registers:x.map(Number),note:bytes});}x[0]=(2n*x[0]*x[0]+3n)&M;x[3]=x[0]*x[2]&M;x[1]=(x[1]+x[3])&M;x[2]=(x[2]+3n)&M;}
 // Navigate a huge active application state and continue in a fresh process.
 const r=new Rover(seed);await r.navigate(String(max-2n));const h=r.save(huge);let [a,y,z,c]=seed.slice(1).map(BigInt);for(let j=0;j<64;j++){a=(2n*a*a+3n)&M;c=a*z&M;y=(y+c)&M;z=(z+3n)&M;}const q=max-2n-64n;const expected=[a,(y+a*(q*z+3n*q*(q-1n)/2n))&M,(z+3n*q)&M,a*(z+3n*(q-1n))&M].map(Number);assert.deepEqual(r.state().registers,expected);
 const restored=processRun([huge,h.digest],[observe,tick(2)]);assert.deepEqual(restored[0].state,r.state());r.tick(2);assert.deepEqual(restored[1].state,r.state());assert.deepEqual(restored[1].frame,frame(r.state()));
 const auto=join(dir,'auto.json'),autoRun=processRun([],[tick(100),input(7,'AP8='),tick(80)],auto),autoSeal=autoRun.at(-1).result;assert.equal(autoSeal.head,'180');assert.deepEqual(processRun([auto,autoSeal.digest],[observe])[0].state,autoRun.at(-1).state);
 const raw=readFileSync(path);const bad=JSON.parse(raw);bad.headHash='0'.repeat(64);const payload=JSON.stringify(bad);writeFileSync(path,payload);await assert.rejects(Rover.restore(path,seal.digest),/commitment/);await assert.rejects(Rover.restore(path,createHash('sha256').update(payload).digest('hex')),/head observation/);writeFileSync(path,raw);await assert.rejects(Rover.restore(path,seal.digest,'954'),/outside/);
 console.log(JSON.stringify({savedBytes:seal.bytes,head:seal.head,branchBytes:at[3].result.bytes,hugeBytes:h.bytes,hugeHead:h.head,processContinuations:2,historicalChecks,automaticSaveChecks:3}));
}finally{rmSync(dir,{recursive:true,force:true});}
