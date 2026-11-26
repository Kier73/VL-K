// Existing VL-K bounded length-prefixed TLS observation protocol, direct Node client.
import {connect} from 'node:tls';
import {randomBytes} from 'node:crypto';
export function tlsObservation({host,port,ca,cert,key,servername='worker'}){
  return {observe(receipt,coordinate){return new Promise((resolve,reject)=>{
    const nonce=randomBytes(16).toString('hex'), pinned=Object.fromEntries(['groundVersion','identity','pages','revision','root'].map(k=>[k,receipt[k]]));
    const body=Buffer.from(JSON.stringify({version:1,op:'observe',nonce,receipt:pinned,coordinate}));
    const head=Buffer.alloc(4);head.writeUInt32BE(body.length);
    const socket=connect({host,port,ca,cert,key,servername,minVersion:'TLSv1.2',rejectUnauthorized:true});
    let data=Buffer.alloc(0),settled=false;
    const finish=(err,w)=>{if(settled)return;settled=true;clearTimeout(timer);socket.destroy();if(err)reject(err);else resolve(w);};
    const timer=setTimeout(()=>finish(Error('observation timeout')),5000);
    socket.on('secureConnect',()=>socket.write(Buffer.concat([head,body])));
    socket.on('error',e=>finish(e));socket.on('end',()=>finish(Error('incomplete response')));socket.on('close',()=>finish(Error('closed pathway')));
    socket.on('data',chunk=>{if(settled)return;if(data.length+chunk.length>16388){finish(Error('oversize response'));return;}data=Buffer.concat([data,chunk]);if(data.length<4)return;const n=data.readUInt32BE();if(n<1||n>16384||data.length>n+4){finish(Error('invalid frame'));return;}if(data.length===n+4){try{const r=JSON.parse(data.subarray(4).toString('utf8'));if(r.nonce!==nonce||!r.witness)throw Error('response nonce mismatch');finish(null,r.witness);}catch(e){finish(e);}}});
  });}};
}
