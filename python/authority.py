"""Single SQLite authority: fenced pure continuations and transactional publication."""
import json
import sqlite3
from contextlib import contextmanager
from debugger import Session, coordinate
from loop_receipt import canonical, digest


class Conflict(RuntimeError):
    pass


def label(value):
    if type(value) is not str or not 1 <= len(value) <= 128 or not value.isascii():
        raise ValueError('invalid identity')
    return value


class Authority:
    def __init__(self, path):
        self.path = str(path)
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS process (id TEXT PRIMARY KEY, owner TEXT NOT NULL, epoch INTEGER NOT NULL, program TEXT NOT NULL, checkpoint TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS publication (pid TEXT NOT NULL, op TEXT NOT NULL, request TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(pid,op))')

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, pid, owner, program):
        pid, owner = label(pid), label(owner)
        s = Session(program)
        with self.transaction() as db:
            db.execute('INSERT INTO process VALUES (?,?,?,?,?)', (pid,owner,1,canonical(s.program),canonical(s.checkpoint())))
        return self.head(pid)

    def _row(self, db, pid):
        row = db.execute('SELECT owner,epoch,program,checkpoint FROM process WHERE id=?',(label(pid),)).fetchone()
        if row is None:
            raise KeyError(pid)
        return row

    def _head(self, row):
        owner,epoch,_,cp = row
        return {'owner':owner,'epoch':epoch,'checkpoint':json.loads(cp)}

    def head(self,pid):
        with self.transaction() as db:
            return self._head(self._row(db,pid))

    def _fence(self,row,owner,epoch):
        if type(epoch) is not int or row[:2] != (label(owner),epoch):
            raise Conflict('stale owner or epoch')

    def transfer(self,pid,owner,epoch,new_owner,expected):
        coordinate(expected);label(new_owner)
        with self.transaction() as db:
            row=self._row(db,pid);self._fence(row,owner,epoch)
            if int(json.loads(row[3])['body']['state']['tick']) != expected:
                raise Conflict('stale coordinate')
            if new_owner==owner or epoch>=2**63-1:
                raise ValueError('invalid transfer')
            db.execute('UPDATE process SET owner=?,epoch=? WHERE id=?',(new_owner,epoch+1,pid))
            return self._head(self._row(db,pid))

    def advance(self,pid,owner,epoch,op,expected,target):
        label(op);coordinate(expected);coordinate(target)
        if target<=expected: raise ValueError('advance must increase coordinate')
        req=canonical({'owner':owner,'epoch':epoch,'expected':str(expected),'target':str(target)})
        def inspect(db):
            row=self._row(db,pid);self._fence(row,owner,epoch)
            prior=db.execute('SELECT request,result FROM publication WHERE pid=? AND op=?',(pid,op)).fetchone()
            if prior is not None:
                if prior[0]!=req: raise Conflict('operation identity reused')
                return row,json.loads(prior[1])
            if int(json.loads(row[3])['body']['state']['tick'])!=expected: raise Conflict('stale coordinate')
            return row,None
        with self.transaction() as db:
            row,prior=inspect(db)
        if prior is not None: return prior
        # Compute outside the write lock. Publication rechecks the complete fence.
        s=Session.restore(json.loads(row[2]),json.loads(row[3]));s.advance(expected,target)
        cp=s.checkpoint()
        body={'pid':pid,'operation':op,'request_sha256':digest(json.loads(req)),'checkpoint':cp}
        result={'body':body,'sha256':digest(body)}
        with self.transaction() as db:
            latest,prior=inspect(db)
            if prior is not None: return prior
            if latest!=row: raise Conflict('state changed during computation')
            db.execute('UPDATE process SET checkpoint=? WHERE id=?',(canonical(cp),pid))
            db.execute('INSERT INTO publication VALUES (?,?,?,?)',(pid,op,req,canonical(result)))
        return result

    def publications(self,pid):
        with self.transaction() as db:
            self._row(db,pid)
            return [json.loads(r[0]) for r in db.execute('SELECT result FROM publication WHERE pid=? ORDER BY rowid',(pid,))]
