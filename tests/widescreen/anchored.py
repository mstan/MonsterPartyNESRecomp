"""Anchored viewport simulation must be independent of presentation cadence."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import mp_run
sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate import route


def main(args):
    args.output.mkdir(parents=True,exist_ok=True)
    results=[]
    for n in (1,8):
        state=ROOT/'evidence'/'rounds'/f'round{n}-start.cycstate'
        first=mp_run.start_frame(state)
        extra=['--widescreen','32:9']
        runs=[]
        for cadence in (0,1,60):
            name=f'round{n}-every{cadence}'
            present=['--present-out',str(args.output/f'{name}.present.png')]
            if cadence:present+=['--present-every',str(cadence)]
            runs.append(mp_run.run(args.output,name,args.frames,state=state,route=route(first,args.frames),assist='life',
                                    extra=extra+present,exe=args.exe))
        checks={f'{cadence}{ext}':Path(runs[0]['state']).with_suffix(ext).read_bytes()==Path(runs[k]['state']).with_suffix(ext).read_bytes()
                for k,cadence in enumerate((1,60),1) for ext in ('.hash','.png','.cycstate','.present.png')}
        i=mp_run.run(args.output,f'round{n}-interp',args.frames,state=state,route=route(first,args.frames),assist='life',
                     extra=extra+['--present-out',str(args.output/f'round{n}-interp.present.png')],exe=args.exe,interp=True)
        checks.update({f'interp{ext}':Path(runs[0]['state']).with_suffix(ext).read_bytes()==Path(i['state']).with_suffix(ext).read_bytes()
                       for ext in ('.hash','.png','.cycstate','.present.png')})
        results.append(dict(round=n,checks=checks,passed=all(checks.values())))
        (args.output/'results.json').write_text(json.dumps(results,indent=1)+'\n',newline='\n')
        print(n,checks,flush=True)
        if not all(checks.values()):raise AssertionError(n)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--exe',type=Path,required=True)
    ap.add_argument('--frames',type=int,default=180)
    main(ap.parse_args())
