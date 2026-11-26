// Volatile exact block device. No persistent or snapshot capability is advertised.
const PAGE = 4096;
const MAX = 64 * 1024 * 1024;
export class StructuralDisk {
  #pages = new Map();
  #size;
  constructor(size) {
    if (!Number.isSafeInteger(size) || size <= 0 || size > MAX || size % 512) throw new RangeError('disk size');
    this.#size = size;
  }
  get size() { return this.#size; }
  get blockSize() { return 512; }
  get persistent() { return false; }
  #range(off, n) {
    if (!Number.isSafeInteger(off) || !Number.isSafeInteger(n) || off < 0 || n < 0 || off % 512 || n % 512 || off > this.size || n > this.size - off) throw new RangeError('block range');
  }
  #check(off, views) {
    if (!Array.isArray(views)) throw new TypeError('views');
    let n = 0;
    for (const v of views) { if (!(v instanceof Uint8Array)) throw new TypeError('byte view'); n += v.length; }
    this.#range(off, n);
    return n;
  }
  #copy(index, at, out) {
    const p = this.#pages.get(index);
    if (!p) out.fill(0);
    else if (p.length === PAGE) out.set(p.subarray(at, at + out.length));
    else for (let i = 0; i < out.length; i++) out[i] = p[(at + i) % p.length];
  }
  #classify(index, bytes) {
    if (bytes.every(x => x === 0)) { this.#pages.delete(index); return; }
    for (let p = 1; p <= 16; p++) {
      let i = p;
      while (i < PAGE && bytes[i] === bytes[i - p]) i++;
      if (i === PAGE) { this.#pages.set(index, bytes.slice(0, p)); return; }
    }
    this.#pages.set(index, bytes);
  }
  read(off, views) {
    this.#check(off, views);
    for (const v of views) for (let i = 0; i < v.length;) {
      const at = off % PAGE, n = Math.min(v.length - i, PAGE - at);
      this.#copy(Math.floor(off / PAGE), at, v.subarray(i, i + n)); i += n; off += n;
    }
  }
  write(off, views) {
    this.#check(off, views);
    let index = -1, bytes;
    for (const v of views) for (let i = 0; i < v.length;) {
      const next = Math.floor(off / PAGE), at = off % PAGE, n = Math.min(v.length - i, PAGE - at);
      if (next !== index) {
        if (index !== -1) this.#classify(index, bytes);
        index = next; bytes = new Uint8Array(PAGE); this.#copy(index, 0, bytes);
      }
      bytes.set(v.subarray(i, i + n), at); i += n; off += n;
    }
    if (index !== -1) this.#classify(index, bytes);
  }
  // Detached representation records; no caller may mutate live backing.
  records() { return [...this.#pages].sort((a,b) => a[0]-b[0]).map(([i,p]) => [i,p.slice()]); }
  stats() {
    let periodic = 0, dense = 0, payload = 0;
    for (const p of this.#pages.values()) { payload += p.length; if (p.length === PAGE) dense++; else periodic++; }
    return { logicalBytes: this.size, periodic, dense, payloadBytes: payload };
  }
}
