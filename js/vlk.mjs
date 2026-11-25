// Browser and Node adapter for the import-free VL-K WASM nucleus.
const OPS=Object.freeze({set:1,copy:2,add:3,mul:4,addr:5,mulr:6});
const MODES=Object.freeze({auto:0,reference:1,ground:2});
function uint(x,bits) {
  if(typeof x!=='number'||!Number.isInteger(x)||x<0||x>=2**bits) throw new RangeError('expected u'+bits);
  return x;
}
function coordinate(x) {
  if(typeof x==='number' && Number.isSafeInteger(x)) x=BigInt(x);
  if(typeof x==='string' && /^(0|[1-9][0-9]*)$/.test(x) && x.length<=20) x=BigInt(x);
  if(typeof x!=='bigint'||x<0n||x>=1n<<64n) throw new RangeError('expected exact u64 coordinate');
  return x;
}
export async function createKernel(bytes) {
  const module=bytes instanceof WebAssembly.Module?bytes:await WebAssembly.compile(bytes);
  if(WebAssembly.Module.imports(module).length!==0) throw new Error('expected import-free kernel');
  const {exports:k}=await WebAssembly.instantiate(module);
  if(k.vk_abi()!==1||typeof k.vk1_run!=='function') throw new Error('unsupported kernel ABI');
  return Object.freeze({evaluate({seed,program,steps,budget=100000,mode='auto'}) {
    if(!Array.isArray(seed)||seed.length!==4||!Array.isArray(program)||program.length>64||!Object.hasOwn(MODES,mode)) throw new TypeError('invalid program request');
    const values=seed.map(x=>uint(x,32));
    const ops=program.map(q=>{
      if(!Array.isArray(q)||q.length!==3||!Object.hasOwn(OPS,q[0])) throw new TypeError('invalid instruction');
      const [op,d,x]=q;return [OPS[op],uint(d,2),uint(x,['copy','addr','mulr'].includes(op)?2:32)];
    });
    const n=coordinate(steps);uint(budget,32);
    k.vk1_begin();values.forEach((v,r)=>{if(k.vk1_seed(r,v)!==0)throw new Error('seed rejected');});
    ops.forEach(q=>{if(k.vk1_append(...q)!==0)throw new Error('instruction rejected');});
    const status=k.vk1_run(n,budget,MODES[mode]);
    return {status,registers:status===0?Array.from({length:4},(_,r)=>k.vk1_result(r)>>>0):null,method:status===0?['identity','reference','ground'][k.vk1_method()]:null,work:k.vk1_work()};
  }});
}
