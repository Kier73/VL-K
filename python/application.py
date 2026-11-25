"""Bounded guest file capabilities and fenced, durable output publication."""
import argparse
import hashlib
import io
import json
import sqlite3
import sys
import uuid
from contextlib import closing
from pathlib import Path
from authority import Authority, Conflict, label
from debugger import validate
from guest_image import load
from guest import Guest
from memory import AddressSpace
from loop_receipt import canonical, digest

LIMIT = 65536
TICKS = 2000000


class BoundedOutput(io.BytesIO):
    def write(self, data):
        if self.tell() + len(data) > LIMIT:
            raise RuntimeError('output limit')
        return super().write(data)


def execute(program, data):
    program = validate(program, application=True)
    if type(data) is not bytes or len(data)>LIMIT:
        raise ValueError('invalid input payload')
    source, out = io.BytesIO(data), BoundedOutput()
    memory=AddressSpace(); memory.map(0,LIMIT)
    g=Guest(program,memory,input_stream=source,output_stream=out,
            descriptors={0:(source,None),1:(None,out),3:(source,None)})
    steps=g.run(TICKS, dispatch_budget=TICKS)
    if not g.halted or g.status!=0:
        raise RuntimeError('application failed or exhausted budget')
    return out.getvalue(), steps


class Applications(Authority):
    def __init__(self, path):
        super().__init__(path)
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS app_job (id TEXT PRIMARY KEY, owner TEXT NOT NULL, epoch INTEGER NOT NULL, program TEXT NOT NULL, input BLOB NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS app_outbox (id TEXT PRIMARY KEY, receipt TEXT NOT NULL, payload BLOB NOT NULL, acknowledged INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS app_destination (id TEXT PRIMARY KEY, sink TEXT)')

    def register(self, job, owner, program, data):
        label(job);label(owner);program=validate(program, application=True)
        if type(data) is not bytes or len(data)>LIMIT: raise ValueError('invalid input')
        with self.transaction() as db:
            row=db.execute('SELECT owner,epoch,program,input FROM app_job WHERE id=?',(job,)).fetchone()
            expected=(owner,1,canonical(program),data)
            if row is None: db.execute('INSERT INTO app_job VALUES (?,?,?,?,?)',(job,*expected))
            elif row!=expected: raise Conflict('job identity reused or transferred')

    def _job(self, db, job):
        row=db.execute('SELECT owner,epoch,program,input FROM app_job WHERE id=?',(label(job),)).fetchone()
        if row is None: raise KeyError(job)
        return row

    def transfer_job(self, job, owner, epoch, replacement):
        label(replacement)
        with self.transaction() as db:
            row=self._job(db,job);self._fence(row,owner,epoch)
            if replacement==owner or epoch>=2**63-1: raise ValueError('invalid transfer')
            db.execute('UPDATE app_job SET owner=?,epoch=? WHERE id=?',(replacement,epoch+1,job))
        return epoch+1

    def run_job(self, job, owner, epoch):
        with self.transaction() as db:
            row=self._job(db,job);self._fence(row,owner,epoch)
            prior=db.execute('SELECT receipt FROM app_outbox WHERE id=?',(job,)).fetchone()
            if prior: return json.loads(prior[0])
        output,steps=execute(json.loads(row[2]),row[3])
        receipt={'job':job,'program_sha256':digest(json.loads(row[2])),
                 'input_sha256':hashlib.sha256(row[3]).hexdigest(),
                 'output_sha256':hashlib.sha256(output).hexdigest(),'steps':steps}
        with self.transaction() as db:
            latest=self._job(db,job);self._fence(latest,owner,epoch)
            if latest!=row: raise Conflict('job changed')
            prior=db.execute('SELECT receipt FROM app_outbox WHERE id=?',(job,)).fetchone()
            if prior: return json.loads(prior[0])
            db.execute('INSERT INTO app_outbox(id,receipt,payload) VALUES (?,?,?)',(job,canonical(receipt),output))
            db.execute('INSERT INTO app_destination VALUES (?,NULL)',(job,))
        return receipt

    def deliver(self, job, sink, *, after_sink=None):
        # Only committed outbox content is deliverable. Old committed effects survive transfers.
        with self.transaction() as db:
            row=db.execute('SELECT receipt,payload,acknowledged FROM app_outbox WHERE id=?',(label(job),)).fetchone()
            if row is None: raise Conflict('no committed output')
            bound=db.execute('SELECT sink FROM app_destination WHERE id=?',(job,)).fetchone()
            if bound is None: raise Conflict('legacy output has no verified sink binding')
            if bound==(None,):
                db.execute('UPDATE app_destination SET sink=? WHERE id=?',(sink.identity,job))
            elif bound!=(sink.identity,): raise Conflict('effect destination changed')
        receipt=json.loads(row[0]);sink.accept(receipt,row[1])
        if after_sink: after_sink()
        with self.transaction() as db:
            db.execute('UPDATE app_outbox SET acknowledged=1 WHERE id=?',(job,))
        return receipt


class Sink:
    """Trusted transactional consumer; dedupe is at the effect boundary itself."""
    def __init__(self,path):
        self.path=str(path)
        with closing(sqlite3.connect(self.path,timeout=15,isolation_level=None)) as db, db:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS output (id TEXT PRIMARY KEY, receipt TEXT NOT NULL, payload BLOB NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS sink_identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), identity TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO sink_identity VALUES (1,?)',(uuid.uuid4().hex,))
            self.identity=db.execute('SELECT identity FROM sink_identity WHERE singleton=1').fetchone()[0]

    def accept(self,receipt,payload):
        job=label(receipt['job']); encoded=canonical(receipt)
        if hashlib.sha256(payload).hexdigest()!=receipt['output_sha256']: raise ValueError('payload mismatch')
        with closing(sqlite3.connect(self.path,timeout=15,isolation_level=None)) as db, db:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT identity FROM sink_identity WHERE singleton=1').fetchone()!=(self.identity,): raise Conflict('sink identity changed')
            prior=db.execute('SELECT receipt,payload FROM output WHERE id=?',(job,)).fetchone()
            if prior is None: db.execute('INSERT INTO output VALUES (?,?,?)',(job,encoded,payload))
            elif prior!=(encoded,payload): raise Conflict('conflicting effect identity')

    def read(self,job):
        with closing(sqlite3.connect(self.path)) as db, db:
            row=db.execute('SELECT payload FROM output WHERE id=?',(label(job),)).fetchone()
            if row is None: raise KeyError(job)
            return row[0]


def main():
    p=argparse.ArgumentParser(); p.add_argument('program');p.add_argument('input');p.add_argument('authority');p.add_argument('sink');p.add_argument('job');a=p.parse_args()
    try:
        program=load(a.program)
        with open(a.input,'rb') as f: data=f.read(LIMIT+1)
        app=Applications(a.authority);app.register(a.job,'local',program,data)
        app.run_job(a.job,'local',1);result=app.deliver(a.job,Sink(a.sink));print(canonical(result));return 0
    except (ValueError,RuntimeError,KeyError,OSError,sqlite3.Error) as e:
        print(f'app: {e}',file=sys.stderr);return 125

if __name__=='__main__':sys.exit(main())
