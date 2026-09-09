#!/usr/bin/env python3
"""Real mount integration test. Retains fixtures/logs; never deletes files."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
REPO=Path(subprocess.check_output(['git','-C',str(PROJECT),'rev-parse','--show-toplevel'],text=True).strip())

def check(condition,message):
    if not condition: raise AssertionError(message)
    print('PASS:',message,flush=True)

def events(log):
    result=[]
    for line in log.read_text().splitlines():
        if line.startswith('{'):
            try: result.append(json.loads(line))
            except json.JSONDecodeError: pass
    return result

def until(predicate,timeout=15):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(.02)
    raise TimeoutError('Timed out waiting for mount or callback')

def denied(action,message):
    try: action()
    except OSError: check(True,message)
    else: raise AssertionError(message)

def tag(path):
    h=14695981039346656037
    for b in path.encode(): h=((h^b)*1099511628211)&((1<<64)-1)
    return f"{h:016x}"

def read_process(path):
    return subprocess.check_output([sys.executable,"-c","import pathlib,sys;sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())",str(path)],timeout=40)

def main():
    run=REPO/'work'/('proof-'+str(time.time_ns()))
    source=run/'source'; mount=run/'mount'; source.mkdir(parents=True); mount.mkdir()
    (source/'.spindleguard-test-root').write_text('disposable test data\n')
    (source/'Workspace').mkdir(); (source/'Workspace-escape').mkdir()
    payload=bytes(range(256))*8192
    (source/'large.bin').write_bytes(payload)
    (source/'second.txt').write_text('second operation\n')
    (source/'Workspace-escape'/'guard.txt').write_text('guard\n')
    (source/'Workspace'/'existing.txt').write_text('before\n')
    (source/'Workspace'/'escape').symlink_to(source/'second.txt')
    os.link(source/'second.txt',source/'Workspace'/'hardlink')
    log=run/'broker.jsonl'
    print('Retained test directory:',run,flush=True)
    with log.open('w') as output:
        daemon=subprocess.Popen([str(PROJECT/'build/spindleguard'),str(source),str(mount),'/Workspace','150'],stdout=output,stderr=output)
        try:
            until(lambda: os.path.ismount(mount) or daemon.poll() is not None)
            check(daemon.poll() is None and os.path.ismount(mount),'real FUSE-T mount established')
            check('large.bin' in os.listdir(mount),'browse through mount')
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(read_process,mount/'large.bin')
                until(lambda: any(e['event']=='start' and e['op']=='read' for e in events(log)))
                second=pool.submit(read_process,mount/'second.txt')
                check(second.result(timeout=20)==b'second operation\n','second application read completed')
                check(first.result(timeout=30)==payload,'2 MiB read through mount matches backing bytes')
            ev=events(log); start={}; finish={}; queued={}
            active=set(); witnessed=[]
            for e in ev:
                t=e['ticket']
                if e['event']=='queued':
                    queued[t]=e
                    if active: witnessed.append((next(iter(active)),t))
                elif e['event']=='start':
                    check(not active,'backing callbacks do not overlap') if active else None
                    active.add(t); start[t]=e
                elif e['event']=='finish':
                    active.remove(t); finish[t]=e
            pairs=[(a,b) for a,b in witnessed if a in finish and b in start and start[a]['op']=='read' and start[b]['time']>=finish[a]['time'] and start[b]['wait_ms']>20 and start[a]['file_tag']==tag('/large.bin') and start[b]['file_tag']==tag('/second.txt')]
            check(bool(pairs),'a competing callback queued during read and started only after it finished')
            a,b=pairs[0]
            print('QUEUE EVIDENCE:',json.dumps({'active_read':a,'queued':b,'queued_op':start[b]['op'],'wait_ms':start[b]['wait_ms'],'read_finish':finish[a]['time'],'second_start':start[b]['time']}),flush=True)
            (mount/'Workspace'/'created.txt').write_text('allowed write\n')
            check((source/'Workspace'/'created.txt').read_text()=='allowed write\n','explicit write prefix forwards to backing directory')
            denied(lambda:(mount/'second.txt').write_text('bad'),'root write refused')
            denied(lambda:(mount/'Workspace-escape'/'guard.txt').write_text('bad'),'prefix boundary escape refused')
            denied(lambda:(mount/'Workspace'/'escape').read_text(),'symlink escape refused')
            denied(lambda:(mount/'Workspace'/'hardlink').write_text('bad'),'hardlink write refused')
            check((source/'second.txt').read_text()=='second operation\n','protected original content unchanged')
            # Check handles and queue continue after errors.
            check((mount/'second.txt').read_text()=='second operation\n','queue remains usable after denied requests')
        finally:
            if os.path.ismount(mount):
                unmount=subprocess.run(['/sbin/umount',str(mount)],capture_output=True,text=True)
                print('Unmount:',unmount.returncode,unmount.stderr.strip(),flush=True)
                if unmount.returncode: raise RuntimeError('Unmount failed; retained mount: '+str(mount))
            try: daemon.wait(timeout=10)
            except subprocess.TimeoutExpired:
                daemon.terminate(); daemon.wait(timeout=5)
            check(not os.path.ismount(mount),'test mount unmounted')
    # A separate read-only mount proves the default without changing source ACLs.
    with (run/'readonly.jsonl').open('w') as output:
        daemon=subprocess.Popen([str(PROJECT/'build/spindleguard'),str(source),str(mount)],stdout=output,stderr=output)
        try:
            until(lambda: os.path.ismount(mount) or daemon.poll() is not None)
            check(daemon.poll() is None and os.path.ismount(mount),'default read-only mount established')
            denied(lambda:(mount/'Workspace'/'existing.txt').write_text('bad'),'writes refused without explicit prefix')
            check((source/'Workspace'/'existing.txt').read_text()=='before\n','default read-only preserves test content')
        finally:
            if os.path.ismount(mount): subprocess.run(['/sbin/umount',str(mount)],check=True)
            try: daemon.wait(timeout=10)
            except subprocess.TimeoutExpired: daemon.terminate(); daemon.wait(timeout=5)
            check(not os.path.ismount(mount),'read-only mount unmounted')
    all_events=events(log)
    starts=[e['ticket'] for e in all_events if e['event']=='start']
    finishes=[e['ticket'] for e in all_events if e['event']=='finish']
    check(starts==finishes==list(range(len(starts))),'all backing requests finish in FIFO order')
    active=None
    for e in all_events:
        if e['event']=='start':
            if active is not None: raise AssertionError('overlapping callbacks')
            active=e['ticket']
        elif e['event']=='finish':
            if active!=e['ticket']: raise AssertionError('mismatched completion')
            active=None
    check(active is None,'no active request left behind')
    (run/'result.json').write_text(json.dumps({'status':'passed','queue_pair':[a,b],'wait_ms':start[b]['wait_ms'],'log':str(log)},indent=2)+'\n')
    print('ALL MOUNT TESTS PASSED',flush=True)

if __name__=='__main__': main()
