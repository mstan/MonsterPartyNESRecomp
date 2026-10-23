"""Replay retained segment commands after seed changes and prove exact parity.

Each case reuses its recorded input state, route and assists. This checks the
new compiler output against both the recorded build and the interpreter. It
does not establish compatibility with other builds or serialize old layouts.
"""
import argparse
import json
import re
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import mp_run
import cycstate


def machine(path, ignored=(b'MOD ',)):
    data=Path(path).read_bytes()
    return [(b'HEAD',data[:32])]+[(tag,data[at:at+n]) for tag,at,n in cycstate.chunks(data) if tag not in ignored]


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
            if args.match and not re.search(args.match,name):
                continue
            reference_state=stem.with_suffix('.cycstate')
            # Earlier campaigns moved the title snapshot to their fixture
            # source name. The retained commands/hash/PNG still use "title".
            if not reference_state.exists() and name=='title':
                reference_state=source/'title-1000.cycstate'
            state=Path(cmd[cmd.index('--load-state')+1]) if '--load-state' in cmd else None
            end=int(cmd[cmd.index('--frames')+1])
            first=mp_run.start_frame(state)
            text=Path(cmd[cmd.index('--input')+1]).read_text() if '--input' in cmd else ''
            assist=cmd[cmd.index('--mp-assist')+1] if '--mp-assist' in cmd else None
            pokes=[cmd[i+1] for i,k in enumerate(cmd) if k=='--mp-poke']
            out=args.output/source.name/path.parent.relative_to(source)
            opts=[]
            for option in ('--widescreen','--present-size'):
                if option in cmd:
                    opts += [option,cmd[cmd.index(option)+1]]
            iopts=opts.copy()
            if args.widescreen:
                profile=['--widescreen',args.widescreen]
                opts += profile+['--present-out',str(out/f'{name}.present.png')]
                iopts += profile+['--present-out',str(out/'interp'/f'{name}.present.png')]
            if args.audio:
                opts += ['--wav-out',str(out/f'{name}.wav')]
                iopts += ['--wav-out',str(out/'interp'/f'{name}.wav')]
            r=mp_run.run(out,name,end-first,state=state,route=text,assist=assist,pokes=pokes,extra=opts,exe=args.exe)
            i=None if args.native_only else mp_run.run(out/'interp',name,end-first,state=state,route=text,assist=assist,pokes=pokes,extra=iopts,exe=args.exe,interp=True)
            checks={f'before{ext}':(reference_state if ext=='.cycstate' else stem.with_suffix(ext)).read_bytes()==Path(r['state']).with_suffix(ext).read_bytes()
                    for ext in ('.hash','.png','.cycstate')}
            if args.widescreen:
                # Widescreen deliberately changes enemy activation. Qualify
                # this profile against the interpreter, not stock simulation.
                checks={}
            if i:
                checks.update({f'interpreter{ext}':Path(i['state']).with_suffix(ext).read_bytes()==Path(r['state']).with_suffix(ext).read_bytes()
                               for ext in ('.hash','.png','.cycstate')})
            if args.widescreen and i:
                checks['interpreter.present.png']=(out/f'{name}.present.png').read_bytes()==(out/'interp'/f'{name}.present.png').read_bytes()
            if args.audio:
                # Recording enables the APU output resampler; its serialized
                # filter history differs from a run with no audio sink. Full
                # APU/state and WAV parity still compare native vs interpreter.
                checks.pop('before.cycstate',None)
                if not args.widescreen:
                    checks['before.non_audio_state']=machine(reference_state,(b'MOD ',b'APU '))==machine(r['state'],(b'MOD ',b'APU '))
                wav=(out/f'{name}.wav').read_bytes()
                if i:checks['interpreter.wav']=wav==(out/'interp'/f'{name}.wav').read_bytes()
                checks['audio-samples']=len(wav)>44 and any(wav[44:])
            log=stem.with_suffix('.log').read_text(errors='replace')
            rows.append(dict(case=str(stem),checks=checks,passed=all(checks.values()),
                             interpreted_rom_before=None if args.widescreen else mp_run._interp(log,'ROM'),interpreted_rom_after=r['interp_rom'],
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
    ap.add_argument('--widescreen',choices=('32:9',),help='fixed widescreen behavior: native/interpreter simulation and presentation parity')
    ap.add_argument('--match',help='only segment labels matching this regular expression')
    ap.add_argument('--audio',action='store_true',help='retain and compare muted emulated WAV output')
    ap.add_argument('--native-only',action='store_true',help='compare against the recorded build without another interpreter run')
    args=ap.parse_args()
    if args.widescreen and args.native_only:
        ap.error('--widescreen requires its interpreter comparison')
    replay(args)
