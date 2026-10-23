"""Replay retained segment commands after seed changes and prove exact parity.

Each case reuses its recorded input state, route and assists. This checks the
new compiler output against both the recorded build and the interpreter. It
does not establish compatibility with other builds or serialize old layouts.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import mp_run
import cycstate


def replay(args):
    args.output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for source in args.sources:
        paths=sorted(source.glob('round*/*.command.json'))+sorted(source.glob('*.command.json'))
        for path in paths:
            cmd=json.loads(path.read_text())
            if '--interp-only' in cmd:
                continue
            stem=path.with_suffix('').with_suffix('')
            name=stem.name
            state=Path(cmd[cmd.index('--load-state')+1]) if '--load-state' in cmd else None
            end=int(cmd[cmd.index('--frames')+1])
            first=mp_run.start_frame(state)
            text=Path(cmd[cmd.index('--input')+1]).read_text() if '--input' in cmd else ''
            assist=cmd[cmd.index('--mp-assist')+1] if '--mp-assist' in cmd else None
            pokes=[cmd[i+1] for i,k in enumerate(cmd) if k=='--mp-poke']
            out=args.output/source.name/path.parent.relative_to(source)
            opts=[]
            for option in ('--widescreen','--widescreen-enemies','--widescreen-camera','--present-size'):
                if option in cmd:
                    opts += [option,cmd[cmd.index(option)+1]]
            r=mp_run.run(out,name,end-first,state=state,route=text,assist=assist,pokes=pokes,extra=opts,exe=args.exe)
            i=mp_run.run(out/'interp',name,end-first,state=state,route=text,assist=assist,pokes=pokes,extra=opts,exe=args.exe,interp=True)
            checks={f'before{ext}':stem.with_suffix(ext).read_bytes()==Path(r['state']).with_suffix(ext).read_bytes()
                    for ext in ('.hash','.png','.cycstate')}
            checks.update({f'interpreter{ext}':Path(i['state']).with_suffix(ext).read_bytes()==Path(r['state']).with_suffix(ext).read_bytes()
                           for ext in ('.hash','.png','.cycstate')})
            log=stem.with_suffix('.log').read_text(errors='replace')
            rows.append(dict(case=str(stem),checks=checks,passed=all(checks.values()),
                             interpreted_rom_before=mp_run._interp(log,'ROM'),interpreted_rom_after=r['interp_rom'],
                             executed_cycles=r['cycles']-(cycstate.cycles(state.read_bytes()) if state else 0)))
            (args.output/'results.json').write_text(json.dumps(rows,indent=1)+'\n',newline='\n')
            print(str(stem),checks,'ROM',rows[-1]['interpreted_rom_before'],'->',r['interp_rom'],flush=True)
            if not all(checks.values()):
                raise AssertionError(str(stem))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('sources',type=Path,nargs='+')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--exe',type=Path,default=mp_run.EXE)
    replay(ap.parse_args())
