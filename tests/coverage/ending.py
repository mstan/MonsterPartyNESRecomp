"""Finish the final guardian and observe the game's ending and credits."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from campaign import Chain, mash, mp_run


def finish(args):
    c=Chain(args.output,args,'ending')
    c.state=args.state
    r=c.ram()
    if (r[0x97],r[0x4f],r[0x58]) != (8,15,1):
        raise AssertionError('Expected the original final-boss entry, round=8 area=15 guardians=1')
    for k in range(6):
        c.seg(f'final-guardian{k}',1200,lambda f:mash(f,1200))
        if c.ram()[0x58] == 0:
            break
    if c.ram()[0x58] != 0:
        raise AssertionError('Final guardian not defeated')
    # The story advances with its own timers and action presses. Save each
    # section for visual inspection; no success or ending flags are written.
    for k in range(args.sections):
        c.seg(f'ending{k:02d}',1200,lambda f:[f'{f+100} A',f'{f+106} -',f'{f+700} A',f'{f+706} -'],assist=None)
    (c.out/'checks.json').write_text(json.dumps({'final_guardian_defeated':True,'ending_visual_review':'pending'},indent=1)+'\n',newline='\n')


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--state',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--sections',type=int,default=20)
    ap.add_argument('--parity',action='store_true')
    ap.add_argument('--exe',type=Path,default=mp_run.EXE)
    ap.add_argument('--widescreen',choices=('32:9',))
    finish(ap.parse_args())
