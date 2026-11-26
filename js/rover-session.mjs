// JSON-lines terminal application; explicit state adapter, not arbitrary process capture.
import {createInterface} from 'node:readline';
import {Rover,frame} from './application-ground.mjs';
const [path,digest,coordinate]=process.argv.slice(2);
const rover=path?await Rover.restore(path,digest,coordinate):new Rover([123,7,19,31,0]);
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})){
  try{const q=JSON.parse(line);let result;
    if(q.op==='tick')rover.tick(q.count);
    else if(q.op==='input')rover.input(q.impulse,q.bytes??null);
    else if(q.op==='navigate')await rover.navigate(q.tick);
    else if(q.op==='save')result=rover.save(q.path);
    else if(q.op!=='observe')throw Error('unknown operation');
    if(process.env.VLK_AUTOSAVE&&['tick','input','navigate'].includes(q.op))result=rover.save(process.env.VLK_AUTOSAVE);
    console.log(JSON.stringify({ok:true,result,state:rover.state(),frame:frame(rover.state())}));
  }catch(e){console.log(JSON.stringify({ok:false,error:e.message}));}
}
