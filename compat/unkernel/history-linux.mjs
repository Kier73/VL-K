// Qualification only: boot actual Linux over a historical coordinate Ground.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { HistoryDevice } from './history-device.mjs';
if(typeof WebAssembly.Suspending!=='function'||typeof WebAssembly.promising!=='function')throw Error('JSPI required');
const release=new URL('../../dist/unkernel-compat/',import.meta.url);
const {createKernel}=await import(new URL('package/dist/node.mjs',release));
const path=process.argv[3];assert(path);const image=await readFile(process.argv[2]);
let disk=await HistoryDevice.open(path,{pages:image.length/4096});
const first=Uint8Array.from({length:65536},(_,i)=>(i*13+(i>>>8))&255),second=first.map(x=>x^81);
async function boot(disk,write,expected){
  const vm=await createKernel({distro:fileURLToPath(new URL('alpine.erofs',release)),memoryMiB:512,disks:[disk]});
  try{
    async function cmd(file,args=[],opts={}){const r=await vm.exec(file,args,{user:'root',...opts});assert.equal(r.exitCode,0,file+': '+r.stderr);return r.stdout;}
    await cmd('mkdir',['-p','/mnt/vlkground']);await cmd('mount',['-t','ext4','/dev/wdb','/mnt/vlkground']);
    if(write)await cmd('sh',['-c','cat > /mnt/vlkground/result'],{input:write});
    const result=await cmd('cat',['/mnt/vlkground/result'],{encoding:'buffer'});assert.deepEqual(Uint8Array.from(result),expected);
    await cmd('umount',['/mnt/vlkground']);assert.equal(await vm.sync({timeout:20000}),true);assert.equal(disk.receipt().dirty,false);
  }finally{await vm.stop();}
}
try{
  assert.equal(disk.receipt().revision,1);
  for(let off=0;off<image.length;off+=1024*1024)await disk.write(off,[image.subarray(off,off+1024*1024)]);
  await disk.flush();await boot(disk,first,first);const shared=disk.receipt();await disk.fork('alternative');await disk.close();
  disk=await HistoryDevice.open(path,{branch:'alternative'});assert.equal(disk.receipt().root,shared.root);await boot(disk,second,second);await disk.close();
  disk=await HistoryDevice.open(path);assert.equal(disk.receipt().root,shared.root);await boot(disk,null,first);await disk.close();
  disk=await HistoryDevice.open(path,{branch:'alternative'});await boot(disk,null,second);
  console.log('PASS: four Linux boots, ext4 branch divergence and independent file recovery');
}finally{await disk.close();}
