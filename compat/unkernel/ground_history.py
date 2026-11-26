"""Historical coordinate Grounds above the unchanged E-CPU PageBacking."""
from hashlib import sha256
from pathlib import Path
from reused.page_ground import PageGroundBacking, PAGE_SIZE, digest

EMPTY = '0' * 64
ZERO = bytes(PAGE_SIZE)
MAX_PAGES = 16384


class Conflict(RuntimeError):
    pass


def node_digest(level, left, right):
    return sha256(b'VLK-node-v1\0' + bytes([level]) + bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


class GroundHistory:
    """Fixed power-of-two geometry, immutable Merkle paths, transactional branch heads."""
    def __init__(self, path, *, pages=None, bases=()):
        self.backing = PageGroundBacking(Path(path), create=pages is not None, bases=bases)
        self.db = self.backing.db
        try:
            if pages is not None:
                if type(pages) is not int or not 2 <= pages <= MAX_PAGES or pages & (pages-1):
                    raise ValueError('invalid geometry')
                with self.db:
                    self.db.execute('CREATE TABLE IF NOT EXISTS geometry (id INTEGER PRIMARY KEY CHECK(id=1), pages INTEGER NOT NULL)')
                    self.db.execute('CREATE TABLE IF NOT EXISTS node (hash TEXT PRIMARY KEY, level INTEGER NOT NULL, l TEXT NOT NULL, r TEXT NOT NULL) WITHOUT ROWID')
                    self.db.execute('CREATE TABLE IF NOT EXISTS revision (id INTEGER PRIMARY KEY, parent INTEGER, root TEXT NOT NULL)')
                    self.db.execute('CREATE TABLE IF NOT EXISTS branch (name TEXT PRIMARY KEY, revision INTEGER NOT NULL) WITHOUT ROWID')
                    self.db.execute('INSERT OR IGNORE INTO geometry VALUES (1,?)', (pages,))
                    self.db.execute('INSERT OR IGNORE INTO revision VALUES (1,NULL,?)', (EMPTY,))
                    self.db.execute("INSERT OR IGNORE INTO branch VALUES ('main',1)")
            self.pages = self.db.execute('SELECT pages FROM geometry WHERE id=1').fetchone()[0]
            if not 2 <= self.pages <= MAX_PAGES or self.pages & (self.pages-1) or (pages is not None and pages != self.pages):
                raise ValueError('geometry mismatch')
            self.depth = self.pages.bit_length()-1
        except BaseException:
            self.backing.close()
            raise

    def close(self):
        self.backing.close()

    def head(self, branch='main'):
        row = self.db.execute('SELECT revision FROM branch WHERE name=?', (branch,)).fetchone()
        if row is None:
            raise KeyError(branch)
        return row[0]

    def root(self, revision):
        row = self.db.execute('SELECT root FROM revision WHERE id=?', (revision,)).fetchone()
        if row is None:
            raise KeyError(revision)
        return row[0]

    def _children(self, key, level):
        if key == EMPTY:
            return EMPTY, EMPTY
        row = self.db.execute('SELECT level,l,r FROM node WHERE hash=?', (key,)).fetchone()
        if row is None or row[0] != level or node_digest(*row) != key:
            raise ValueError('coordinate node identity mismatch')
        return row[1:]

    def _coordinate(self, index):
        if type(index) is not int or not 0 <= index < self.pages:
            raise ValueError('invalid coordinate')

    def observe(self, revision, index):
        self._coordinate(index)
        key = self.root(revision)
        for level in range(self.depth, 0, -1):
            if key == EMPTY:
                return ZERO
            key = self._children(key, level)[(index >> (level-1)) & 1]
        return ZERO if key == EMPTY else self.backing.get_page(key)

    def read_range(self, revision, offset, length):
        if type(offset) is not int or type(length) is not int or offset < 0 or length < 0 or offset > self.pages*PAGE_SIZE or length > self.pages*PAGE_SIZE-offset:
            raise ValueError('invalid byte range')
        self.root(revision)
        out = bytearray()
        while length:
            index, at = divmod(offset, PAGE_SIZE)
            take = min(length, PAGE_SIZE-at)
            out.extend(self.observe(revision, index)[at:at+take])
            offset += take
            length -= take
        return bytes(out)

    def write_range(self, branch, expected, offset, data):
        if type(offset) is not int or type(data) is not bytes or offset < 0 or offset % 512 or len(data) % 512 or offset > self.pages*PAGE_SIZE or len(data) > self.pages*PAGE_SIZE-offset:
            raise ValueError('invalid sector range')
        if self.head(branch) != expected:
            raise Conflict('stale branch revision')
        updates = {}
        at = 0
        while at < len(data):
            index, within = divmod(offset+at, PAGE_SIZE)
            take = min(len(data)-at, PAGE_SIZE-within)
            page = bytearray(self.observe(expected, index))
            page[within:within+take] = data[at:at+take]
            updates[index] = bytes(page)
            at += take
        return self.commit(branch, expected, updates)

    def _replace(self, key, level, index, value):
        if level == 0:
            return value
        left, right = self._children(key, level)
        if index & (1 << (level-1)):
            right = self._replace(right, level-1, index, value)
        else:
            left = self._replace(left, level-1, index, value)
        if left == right == EMPTY:
            return EMPTY
        key = node_digest(level, left, right)
        self.db.execute('INSERT OR IGNORE INTO node VALUES (?,?,?,?)', (key,level,left,right))
        if self._children(key, level) != (left,right):
            raise ValueError('node publication conflict')
        return key

    def fork(self, name, revision):
        if type(name) is not str or not name or len(name)>128:
            raise ValueError('invalid branch')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.root(revision)
            self.db.execute('INSERT INTO branch VALUES (?,?)', (name,revision))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def commit(self, branch, expected, updates):
        """Retain immutable pages first, then atomically publish a CAS-checked root."""
        if type(updates) is not dict:
            raise ValueError('invalid updates')
        for index, raw in updates.items():
            self._coordinate(index)
            self.backing._check(raw)
        if self.head(branch) != expected:
            raise Conflict('stale branch revision')
        staged = {i: EMPTY if raw == ZERO else self.backing.put_page(raw) for i,raw in updates.items()}
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.head(branch) != expected:
                raise Conflict('stale branch revision')
            old = key = self.root(expected)
            for index, value in sorted(staged.items()):
                key = self._replace(key, self.depth, index, value)
            if old == key:
                revision = expected
            else:
                revision = self.db.execute('INSERT INTO revision(parent,root) VALUES (?,?)', (expected,key)).lastrowid
                self.db.execute('UPDATE branch SET revision=? WHERE name=?', (revision,branch))
            self.db.commit()
            return revision
        except BaseException:
            self.db.rollback()
            raise

    def receipt(self, revision):
        return {'groundVersion':'vlk.coordinate-ground.v1','pages':self.pages,'revision':revision,'root':self.root(revision)}
