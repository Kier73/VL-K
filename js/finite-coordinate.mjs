// Exact navigation of a complete finite functional graph, with a local certificate.
export function compileCoordinates(table){
  const n=table.length;
  if(!Number.isInteger(n)||n<1||n>4096||Array.from(table).some(x=>!Number.isInteger(x)||x<0||x>=n))throw Error('invalid finite transition');
  const indegree=new Uint16Array(n), peeled=[];
  for(const y of table)indegree[y]++;
  for(let x=0;x<n;x++)if(!indegree[x])peeled.push(x);
  for(let i=0;i<peeled.length;i++){const y=table[peeled[i]];if(--indegree[y]===0)peeled.push(y);}
  const cycle=new Int16Array(n).fill(-1), position=new Uint16Array(n), depth=new Uint16Array(n), cycles=[];
  for(let x=0;x<n;x++)if(indegree[x]&&cycle[x]<0){const members=[];let y=x;do{cycle[y]=cycles.length;position[y]=members.length;members.push(y);y=table[y];}while(y!==x);cycles.push(Uint16Array.from(members));}
  let maxDepth=0;
  for(let i=peeled.length-1;i>=0;i--){const x=peeled[i],y=table[x];cycle[x]=cycle[y];position[x]=position[y];depth[x]=depth[y]+1;maxDepth=Math.max(maxDepth,depth[x]);}
  // Binary jumps are needed only for coordinates before cycle entry.
  const jumps=[];if(maxDepth>1){jumps.push(Uint16Array.from(table));for(let k=1;2**k<maxDepth;k++){const prev=jumps[k-1];jumps.push(Uint16Array.from(prev,y=>prev[y]));}}
  // Check the certificate by local equations, independent of the peeling order.
  for(let x=0;x<n;x++){
    const y=table[x],c=cycles[cycle[x]],p=position[x];
    if(!c||p>=c.length)throw Error('invalid cycle certificate');
    if(depth[x]===0){if(c[p]!==x||depth[y]!==0||cycle[y]!==cycle[x]||position[y]!==((p+1)%c.length))throw Error('invalid cycle edge');}
    else if(depth[y]!==depth[x]-1||cycle[y]!==cycle[x]||position[y]!==p)throw Error('invalid tail edge');
  }
  for(let k=0;k<jumps.length;k++)for(let x=0;x<n;x++)if(jumps[k][x]!==(k?jumps[k-1][jumps[k-1][x]]:table[x]))throw Error('invalid jump certificate');
  return Object.freeze({at(x,t){
    if(!Number.isInteger(x)||x<0||x>=n||typeof t!=='bigint'||t<0n||t>=1n<<64n)throw Error('invalid coordinate');
    if(t>=BigInt(depth[x])){const c=cycles[cycle[x]],p=(position[x]+Number((t-BigInt(depth[x]))%BigInt(c.length)))%c.length;return c[p];}
    let k=0;while(t){if(t&1n)x=jumps[k][x];t>>=1n;k++;}return x;
  },stats(){return {states:n,cycles:cycles.length,maxDepth,jumpLevels:jumps.length,indexBytes:cycle.byteLength+position.byteLength+depth.byteLength+cycles.reduce((a,c)=>a+c.byteLength,0)+jumps.reduce((a,j)=>a+j.byteLength,0)};}});
}
