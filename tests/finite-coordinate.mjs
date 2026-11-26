import assert from 'node:assert/strict';
import {compileCoordinates} from '../js/finite-coordinate.mjs';
const n=4096, max=(1n<<64n)-1n;
let seed=913;const rnd=()=>seed=(Math.imul(seed,1664525)+1013904223)>>>0;
function oracle(table,x,t){const seen=new Map(),trace=[];while(!seen.has(x)){seen.set(x,trace.length);trace.push(x);x=table[x];}const p=BigInt(seen.get(x));return trace[Number(t<BigInt(trace.length)?t:p+(t-p)%BigInt(trace.length-Number(p)))];}
const tables=[Array.from({length:n},(_,i)=>Math.min(i+1,n-1)),Array.from({length:n},(_,i)=>(i+1)%n),Array.from({length:n},(_,i)=>(Math.imul(i,i)+17)*3&4095),Array.from({length:n},()=>rnd()>>>20)];
for(const table of tables){const g=compileCoordinates(table);for(let j=0;j<512;j++){const x=rnd()>>>20,t=j%2?BigInt(rnd()%4096):max-BigInt(rnd());assert.equal(g.at(x,t),oracle(table,x,t));}for(let x=0;x<n;x++)assert.equal(g.at(x,1n),table[x]);console.log(g.stats());}
assert.throws(()=>compileCoordinates([1]));assert.throws(()=>compileCoordinates([0,NaN]));assert.throws(()=>compileCoordinates([0]).at(0,1n<<64n));
console.log('2048 differential coordinates and 16384 one-step checks passed');
