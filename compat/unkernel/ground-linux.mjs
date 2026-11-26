// Runtime acceptance: actual ext4 over a structural, durable host BlockDevice.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { GroundDisk } from './ground-disk.mjs';
if(typeof WebAssembly.Suspending!=='function'||typeof WebAssembly.promising!=='function')throw Error('JSPI required');
const release=new URL('../../dist/unkernel-compat/',import.meta.url);
const {createKernel}=await import(new URL('package/dist/node.mjs',release));
const path=process.argv[3];assert(path);const image=await readFile(process.argv[2]);
let disk=new GroundDisk(path,image.length);assert.equal(disk.receipt().revision,0);disk.write(0,[image]);disk.flush();
const data=Uint8Array.from({length:65536},(_,i)=>(i*13+(i>>>8))&255);
async function boot(write){
  const vm=await createKernel({distro:fileURLToPath(new URL('alpine.erofs',release)),memoryMiB:512,disks:[disk]});
  try{
    async function cmd(file,args=[],opts={}){const r=await vm.exec(file,args,{user:'root',...opts});assert.equal(r.exitCode,0,file+': '+r.stderr);return r.stdout;}
    await cmd('mkdir',['-p','/mnt/vlkground']);await cmd('mount',['-t','ext4','/dev/wdb','/mnt/vlkground']);
    if(write)await cmd('sh',['-c','cat > /mnt/vlkground/result'],{input:data});
    const result=await cmd('cat',['/mnt/vlkground/result'],{encoding:'buffer'});assert.deepEqual(Uint8Array.from(result),data);
    await cmd('umount',['/mnt/vlkground']);assert.equal(await vm.sync({timeout:20000}),true);assert.equal(disk.receipt().dirty,false);
  }finally{await vm.stop();}
}
await boot(true);const receipt=disk.receipt();assert(receipt.revision>1);disk=new GroundDisk(path);assert.deepEqual(disk.receipt(),receipt);await boot(false);
console.log('PASS: real ext4 write, guest flush, new machine mount and exact file recovery');
