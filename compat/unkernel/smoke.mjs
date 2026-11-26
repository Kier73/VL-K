// Independent acceptance gate for the unmodified pinned Linux substrate.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { StructuralDisk } from './structural-disk.mjs';

if (Number(process.versions.node.split('.')[0]) < 24 ||
    typeof WebAssembly.Suspending !== 'function' ||
    typeof WebAssembly.promising !== 'function') {
  console.error('Node 24+ with WebAssembly JSPI is required');
  process.exit(2);
}
const release = new URL('../../dist/unkernel-compat/', import.meta.url);
const name = process.argv[2] ?? 'alpine';
const digests = {alpine:'4253fdcaf3fe289f6a48eb565b5ca1eb43e147e6b9d9985ffbca865b3984a9a8', debian:'18e863fd85a63b26f1b017ad76f560f169e8dde74619f0378f72bfaae22db30d'};
assert.ok(Object.hasOwn(digests,name), 'distro must be alpine or debian');
const distro = fileURLToPath(new URL(name + '.erofs', release));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
assert.equal(hash(await readFile(distro)), digests[name]);
const { createKernel } = await import(new URL('package/dist/node.mjs', release));
// No network backend, no host directory mounts, no inherited host commands.
const disk = new StructuralDisk(2 * 1024 * 1024);
const vm = await createKernel({ distro, memoryMiB: 512, disks: [disk] });
try {
  async function command(file, args = [], options = {}) {
    const r = await vm.exec(file, args, options);
    assert.equal(r.exitCode, 0, file + ": " + r.stderr);
    return r.stdout;
  }
  assert.equal((await command('cat', ['/proc/sys/kernel/ostype'])).trim(), 'Linux');
  assert.match((await command('uname', ['-m'])).trim(), /^(aarch64|arm64)$/);
  assert.equal(await command('sh', ['-c', 'printf abc | tr a-z A-Z']), 'ABC');
  const data = Uint8Array.from({length: 65536}, (_, i) => (i * 31 + (i >>> 8)) & 255);
  const output = await command('sh', ['-c', 'cat > /tmp/vlk-probe; cat /tmp/vlk-probe'], {input: data, encoding: 'buffer'});
  assert.equal(hash(output), hash(data));
  assert.equal((await command('sha256sum', ['/tmp/vlk-probe'])).split(/\s+/)[0], hash(data));
  const status = await vm.exec('sh', ['-c', 'printf err >&2; exit 23']);
  assert.equal(status.exitCode, 23);
  assert.equal(status.stderr, 'err');
  const concurrent = await Promise.all([command('printf', ['one']), command('printf', ['two'])]);
  assert.deepEqual(concurrent, ['one', 'two']);
  // Distro is /dev/wda; our disposable block device is /dev/wdb.
  const pattern = Uint8Array.from({length: 4096}, (_, i) => i % 7 + 1);
  await command('sh', ['-c', 'cat > /dev/wdb && sync'], {user: 'root', input: pattern});
  const raw = await command('dd', ['if=/dev/wdb','bs=4096','count=1'], {user:'root', encoding:'buffer'});
  assert.equal(hash(raw), hash(pattern));
  const observed = new Uint8Array(4096); disk.read(0,[observed]);
  assert.equal(hash(observed), hash(pattern));
  assert.deepEqual(disk.stats(), {logicalBytes: 2097152, periodic: 1, dense: 0, payloadBytes: 7});
  console.log('PASS: Linux raw block I/O through VL-K structural disk');
  console.log('PASS: actual Linux guest, architecture, pipeline, 64 KiB file roundtrip, exit/stderr, concurrent commands');
} finally {
  await vm.stop();
}
