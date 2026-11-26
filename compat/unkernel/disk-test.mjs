import assert from 'node:assert/strict';
import { StructuralDisk } from './structural-disk.mjs';
const size = 2 * 1024 * 1024, disk = new StructuralDisk(size), oracle = new Uint8Array(size);
let seed = 27183;
function random() { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed; }
function chunks(b) { const at = Math.min(b.length, random() % 711); return [b.subarray(0, at), b.subarray(at)]; }
const pattern = Uint8Array.from({length: size}, (_, i) => (i % 4096) % 7 + 1);
disk.write(0, chunks(pattern)); oracle.set(pattern);
assert.deepEqual(disk.stats(), {logicalBytes:size,periodic:512,dense:0,payloadBytes:3584});
console.log('2 MiB periodic disk -> 3584 representation payload bytes');
for (let i = 0; i < 3000; i++) {
  const n = (1 + (random() >>> 16) % 16) * 512, off = ((random() >>> 8) % ((size-n)/512+1))*512;
  const b = new Uint8Array(n);
  if (i % 3) {
    if (i % 5) for (let j = 0; j < n; j++) b[j] = random() >>> 24;
    disk.write(off, chunks(b)); oracle.set(b, off); b.fill(91);
  } else {
    disk.read(off, chunks(b)); assert.deepEqual(b, oracle.slice(off,off+n));
  }
}
const full = new Uint8Array(size); disk.read(0, chunks(full)); assert.deepEqual(full,oracle);
for (const [off, views] of [[-512,[new Uint8Array(512)]],[1,[new Uint8Array(512)]],[size-512,[new Uint8Array(1024)]],[0,[new Uint8Array(513)]],[0,[new Uint8Array(512),null]]]) assert.throws(()=>disk.write(off,views));
disk.read(0,[full]);assert.deepEqual(full,oracle);
const sentinel = new Uint8Array(1024).fill(42);assert.throws(()=>disk.read(size-512,[sentinel]));assert(sentinel.every(x=>x===42));
disk.write(0,[new Uint8Array(size)]);assert.equal(disk.stats().payloadBytes,0);disk.read(0,[full]);assert(full.every(x=>x===0));
console.log('3000 mixed scatter/gather operations, full byte oracle, refusal atomicity, zero reclaim passed');
