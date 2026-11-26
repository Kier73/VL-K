import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { verifyWitness } from './coordinate-witness.mjs';
const batch=JSON.parse(readFileSync(0,'utf8'));
for(const {witness,receipt,coordinate,expected} of batch)
  assert.equal(Buffer.from(verifyWitness(witness,receipt,coordinate)).toString('hex'),expected);
console.log(batch.length+" detached observations independently verified");
