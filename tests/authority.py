import json, os, sqlite3, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from authority import Authority, Conflict
from process import Supervisor, PIPE
from loop_receipt import canonical
PROGRAM=json.loads((ROOT/'examples/guest-debug.json').read_text())['program']
CUT=32212254723; END=CUT+5


def worker():
    db,kind,*args=sys.argv[2:];a=Authority(db)
    try:
        if kind=='transfer': result=a.transfer('p','origin',1,args[0],0)
        elif kind=='advance': result=a.advance('p',args[0],int(args[1]),args[2],int(args[3]),int(args[4]))
        elif kind=='crash':
            a.advance('p',args[0],int(args[1]),'distant',0,CUT)
            print('committed',flush=True);time.sleep(60);return
        else: raise ValueError(kind)
        print(canonical(result))
    except Conflict:
        print('conflict');sys.exit(3)


def main():
    with tempfile.TemporaryDirectory() as d, Supervisor(32) as sup:
        path=str(Path(d,'authority.db')); a=Authority(path);a.create('p','origin',PROGRAM)
        def spawn(*args):
            return sup.spawn([str(ROOT/'dist/vlk'),'run',sys.executable,__file__,'worker',path,*args],stdout=PIPE,stderr=PIPE)
        def collect(h):
            out,err=sup.communicate(h,timeout=20);status=sup.wait(h);sup.release(h);assert not err,err
            return status,out
        hs=[spawn('transfer',f'worker{i}') for i in range(12)]
        results=[collect(h) for h in hs];assert sorted(r[0] for r in results)==[0]+[3]*11
        head=a.head('p');owner=head['owner'];assert head['epoch']==2
        h=spawn('crash',owner,'2');p=sup._get(h)
        import select
        assert select.select([p.stdout],[],[],15)[0] and p.stdout.readline()==b'committed\n'
        sup.kill(h);assert sup.wait(h,timeout=10)==-9;sup.release(h)
        # Retry after actual process death; duplicates all return same committed result.
        hs=[spawn('advance',owner,'2','distant','0',str(CUT)) for _ in range(12)]
        rs=[collect(h) for h in hs];assert all(r==rs[0] and r[0]==0 for r in rs)
        assert len(a.publications('p'))==1
        assert collect(spawn('advance','origin','1','late','0',str(CUT)))[0]==3
        assert collect(spawn('advance',owner,'2','distant','0',str(END)))[0]==3
        a.transfer('p',owner,2,'replacement',CUT)
        assert collect(spawn('advance',owner,'2','stale',str(CUT),str(END)))[0]==3
        hs=[spawn('advance','replacement','3',f'finish{i}',str(CUT),str(END)) for i in range(12)]
        rs=[collect(h) for h in hs];assert sorted(r[0] for r in rs)==[0]+[3]*11
        cp=a.head('p')['checkpoint']['body']['state'];assert cp['tick']==str(END) and cp['halted'] and cp['registers'][0]==0
        assert len(a.publications('p'))==2
        with sqlite3.connect(path) as db: assert db.execute('PRAGMA integrity_check').fetchone()==('ok',)
        print('12 competing transfers, 12 replay retries after SIGKILL, 12 competing final commits; 2 durable publications, 3 epochs; exact final state',cp)
        # VL-K hosts a real native SQL consumer of the authority database.
        h=sup.spawn([str(ROOT/'dist/vlk'),'run',sys.executable,'-c','import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("SELECT count(*) FROM publication").fetchone()[0])',path],stdout=PIPE,stderr=PIPE)
        assert collect(h)==(0,b'2\n')
        print('native SQL consumer via VL-K verified publication count')


if __name__=='__main__':
    if len(sys.argv)>1:worker()
    else:main()
