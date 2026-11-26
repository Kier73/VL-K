// Independent acceptance gate for the unmodified pinned Linux substrate.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';

if (Number(process.versions.node.split('.')[0]) < 24 ||
    typeof WebAssembly.Suspending !== 'function' ||
    typeof WebAssembly.promising !== 'function') {
  console.error('Node 24+ with WebAssembly JSPI is required');
  process.exit(2);
}
const release = new URL('../../dist/unkernel-compat/', import.meta.url);
const distro = fileURLToPath(new URL('alpine.erofs', release));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
assert.equal(hash(await readFile(distro)), '4253fdcaf3fe289f6a48eb565b5ca1eb43e147e6b9d9985ffbca865b3984a9a8');
const { createKernel } = await import(new URL('package/dist/node.mjs', release));
// No network backend, no host directory mounts, no inherited host commands.
const vm = await createKernel({ distro, memoryMiB: 256 });
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
  console.log('PASS: actual Linux guest, architecture, pipeline, 64 KiB file roundtrip, exit/stderr, concurrent commands');
} finally {
  await vm.stop();
}
