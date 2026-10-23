"""Retained scene checkpoints and a signed margin-sprite fixture."""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageChops
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import cycstate, mp_run


def main(args):
    args.output.mkdir(parents=True,exist_ok=True)
    records=[]
    def record(name,**checks):
        records.append(dict(case=name,checks=checks,passed=all(checks.values())))
        (args.output/'results.json').write_text(json.dumps(records,indent=1)+'\n',newline='\n')
        print(name,checks,flush=True)
        if not all(checks.values()):raise AssertionError(name)
    def run(name,state,frames=120,wide=True,interp=False):
        out=args.output/name
        extra=['--present-out',str(out.with_suffix('.present.png'))]
        if wide:extra+=['--widescreen','32:9','--widescreen-report',str(out.with_suffix('.jsonl'))]
        if wide and args.anchored:extra+=['--widescreen-camera','anchored']
        r=mp_run.run(args.output,name,frames,state=state,extra=extra,exe=args.exe,interp=interp)
        r['stem']=out
        r['rows']=[json.loads(s) for s in out.with_suffix('.jsonl').read_text().splitlines()] if wide else []
        return r
    def same(a,b,ext):return a['stem'].with_suffix(ext).read_bytes()==b['stem'].with_suffix(ext).read_bytes()
    for path in args.states:
        name=path.parent.name+'-'+path.stem
        r=run(name,path)
        i=run(name+'-interp',path,interp=True)
        record(name,**{ext:same(r,i,ext) for ext in ('.hash','.png','.present.png','.cycstate')},
               failures=all(row['failures']==0 and row['mod_failures']==0 and row['overflow']==0 for row in r['rows']),
               terrain=all(row['terrain_errors']==0 for row in r['rows']))
        print('scene',r['rows'][-1],flush=True)
    if args.sprite_state:
        data=cycstate.ram(args.sprite_state.read_bytes())
        slot=next(i for i in range(6,9) if data[0x300+i]<128 and data[0x3c0+i]&128)
        sprites={0x30c+slot:60,0x3d6+slot:args.sprite_x&255,0x40d+slot:(args.sprite_x>>8)&255}
        on=args.output/'fixture-sprite-on.cycstate'
        off=args.output/'fixture-sprite-off.cycstate'
        cycstate.fixture(args.sprite_state,on,sprites,f'Freeze an existing enemy task at signed screen X={args.sprite_x}; the original object drawer must supply real margin pieces')
        cycstate.fixture(on,off,{0x3c0+slot:0},'Same fixture with this object hidden; presentation difference must be confined to its pieces')
        r=run('sprite-on',on,frames=8)
        empty=run('sprite-off',off,frames=8)
        i=run('sprite-interp',on,frames=8,interp=True)
        picture=Image.open(r['stem'].with_suffix('.present.png')).convert('RGB')
        hidden=Image.open(empty['stem'].with_suffix('.present.png')).convert('RGB')
        delta=ImageChops.difference(picture,hidden)
        x0=(picture.width-256)//2
        if args.anchored:
            cam=data[0x50]*256+data[0x25]
            x0=min(x0,cam)
        box=delta.getbbox()
        record('margin-sprite',visible=box is not None,margin=box is not None and (box[2]<=x0 if args.sprite_x<0 else box[0]>=x0+256),
               parity=same(r,i,'.present.png') and same(r,i,'.cycstate'),native_unchanged=same(r,empty,'.png'))
        # Hiding the object in a loaded state must clear its old DMA packet.
        gone=args.output/'fixture-sprite-gone.cycstate'
        cycstate.fixture(r['state'],gone,{0x3c0+slot:0},'Remove the fixture object and verify that its saved presentation packet disappears after the next OAM build')
        g=run('sprite-gone',gone,frames=8)
        hidden_after=run('sprite-off-later',empty['state'],frames=8)
        record('no-stale-margin-packet',picture=same(g,hidden_after,'.present.png'))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--exe',type=Path,default=ROOT/'build-wide'/'MonsterPartyRecomp.exe')
    ap.add_argument('--states',type=Path,nargs='*',default=[])
    ap.add_argument('--sprite-state',type=Path)
    ap.add_argument('--sprite-x',type=int,default=-40)
    ap.add_argument('--anchored',action='store_true')
    main(ap.parse_args())
