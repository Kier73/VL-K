// Shared pure-intention dispatcher. Bindings and cost declarations are receiver-owned.
export class RealizationRefusal extends Error {
  constructor(receipt){super('no sufficient admitted realization');this.receipt=receipt;}
}
export async function realize(intention,candidates,budget){
  if(!Object.isFrozen(intention)||typeof intention.domain!=='string'||!Array.isArray(candidates)||candidates.length>16||!Number.isSafeInteger(budget)||budget<0)throw TypeError('invalid realization request');
  const ids=new Set();for(const c of candidates){if(typeof c.id!=='string'||ids.has(c.id)||typeof c.probe!=='function'||typeof c.run!=='function'||typeof c.admit!=='function')throw TypeError('invalid binding');ids.add(c.id);}
  const start=performance.now(),trace=[],timing={discovery:0,realization:0,admission:0};let charged=0;
  const receipt=selected=>({intention,selected,budget,charged,trace,timing:{...timing,total:performance.now()-start}});
  if(budget<candidates.length)throw new RealizationRefusal(receipt(null));
  const eligible=[];
  for(const c of candidates){
    charged++;const t=performance.now();let cost;
    try{cost=c.probe(intention);if(cost!==null&&(!Number.isSafeInteger(cost)||cost<1))throw Error('invalid cost');}
    catch{trace.push({id:c.id,status:'probe-refused'});continue;}
    finally{timing.discovery+=performance.now()-t;}
    if(cost===null)trace.push({id:c.id,status:'ineligible'});else eligible.push({c,cost});
  }
  eligible.sort((a,b)=>a.cost-b.cost);
  for(const {c,cost} of eligible){
    if(cost>budget-charged){trace.push({id:c.id,status:'over-budget',cost});continue;}
    charged+=cost;let proposal;const t=performance.now();
    try{proposal=await c.run(intention,cost);}
    catch{trace.push({id:c.id,status:'realization-refused',cost});continue;}
    finally{timing.realization+=performance.now()-t;}
    const v=performance.now();let value,ok=false;
    try{value=await c.admit(intention,proposal);ok=true;}
    catch{trace.push({id:c.id,status:'admission-refused',cost});}
    finally{timing.admission+=performance.now()-v;}
    if(ok){trace.push({id:c.id,status:'admitted',cost});return {value,receipt:receipt(c.id)};}
  }
  throw new RealizationRefusal(receipt(null));
}
