"""Headless title/attract, pause, death/continue and real pill pickup cases."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from campaign import Chain, ROOT, TITLE_ROUTE
sys.path.insert(0,str(ROOT/'tools'))
import cycstate
import mp_run


def run(args):
    args.output.mkdir(parents=True,exist_ok=True)
    checks={}
    def check(name,passed):
        checks[name]=bool(passed)
        (args.output/'checks.json').write_text(json.dumps(checks,indent=1)+'\n',newline='\n')
        if not passed:
            raise AssertionError(name)
    c=Chain(args.output/'cases',args,'extra cases')
    c.seg('title',300,assist=None)
    c.seg('attract',4500,assist=None)
    # Start a clean game, retaining a complete separate attract branch.
    c.state=None
    c.seg('round-card',1000,lambda f:TITLE_ROUTE.splitlines(),assist=None)
    c.seg('start',400,lambda f:[f'{f+10} START',f'{f+16} -'],assist=None)
    c.seg('objects',450,lambda f:[f'{f} RIGHT',f'{f+449} -'],assist='life')
    objects=c.state
    ram=c.ram()
    slot=next(i for i in range(6,9) if ram[0x300+i]<128 and ram[0x3c0+i]&128)
    c.fixture('one-life-overlap',{0x9e:1,0x3cb+slot:ram[0x3cb],0x3d6+slot:ram[0x3d6],0x40d+slot:ram[0x40d]},
              'One life and an enemy overlap; the original collision, death and game-over paths must execute without life assist')
    c.seg('death',1000,assist=None)
    check('death-game-over',c.ram()[0x32f]==6 and c.ram()[0x9e]==0)
    c.seg('continue-card',800,lambda f:[f'{f+20} START',f'{f+26} -'],assist=None)
    c.seg('continue-level',500,lambda f:[f'{f+20} START',f'{f+26} -'],assist=None)
    check('continue-level',c.ram()[0x32f]==4 and c.ram()[0x300]==0 and c.ram()[0x9e]>0)
    c.state=objects
    ram=c.ram()
    # Model an enemy's pill drop, keeping it still through the next collision
    # scan. No writes to Bert's flag, timer, or Mark's animation state.
    slot=7
    check('pill-slot-live',ram[0x300+slot]<128 and bool(ram[0x3c0+slot]&128))
    c.fixture('pill-drop',{0x30c+slot:60,0x330+slot:ram[0x330+slot]|16,0x418+slot:0x80,0x42e+slot:0x2f,
                          0x3cb+slot:ram[0x3cb],0x3d6+slot:ram[0x3d6],0x40d+slot:ram[0x40d],
                          0x3c0+slot:0x80,0x3ec+slot:8,0x3f7+slot:8},
              'Assisted pill-drop prerequisite; actual collision invokes 4:90D2 and 4:887D to transform Mark')
    c.seg('bert-pickup',500,assist='life')
    check('bert-transformed',bool(c.ram()[0x5e]&128) and c.ram()[0x54]>0)
    c.seg('bert-flying',600,lambda f:[f'{f} UP B',f'{f+100} RIGHT B',f'{f+250} LEFT B',f'{f+500} -'],assist='life')
    check('bert-flight',bool(c.ram()[0x5e]&128))
    c.seg('bert-expiry',2400,assist='life')
    check('bert-return-to-mark',not(c.ram()[0x5e]&128))
    c.state=objects
    c.seg('pause-on',120,lambda f:[f'{f+10} START',f'{f+16} -'],assist=None)
    paused=c.ram()[0x300:0x449]
    c.seg('paused',240,assist=None)
    check('pause-freezes-objects',c.ram()[0x300:0x449]==paused)
    c.seg('pause-off',240,lambda f:[f'{f+10} START',f'{f+16} -',f'{f+60} RIGHT',f'{f+200} -'],assist=None)
    check('unpause-resumes-objects',c.ram()[0x300:0x449]!=paused)
    print(json.dumps(checks),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--parity',action='store_true')
    ap.add_argument('--exe',type=Path,default=mp_run.EXE)
    ap.add_argument('--widescreen',choices=('32:9',))
    run(ap.parse_args())
