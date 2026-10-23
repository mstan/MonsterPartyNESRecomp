"""Headless widescreen acceptance matrix; every comparison retains its inputs.

Run with Windows Python -I. Evidence is outside C: and includes native pictures,
presentation pictures, full states, routes, commands, and decoder diagnostics.
"""
import argparse
import json
import shutil
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import cycstate
import mp_run


def machine(path):
    data = Path(path).read_bytes()
    return [(b'HEAD', data[:32])] + [(tag, data[at:at+n]) for tag, at, n in cycstate.chunks(data) if tag != b'MOD ']


def route(first, frames):
    lines = []
    for f in range(first, first + frames, 48):
        d = 'RIGHT' if f < first + frames * 2 // 3 else 'LEFT'
        lines += [f'{f} {d}', f'{f+20} {d} A', f'{f+34} {d} B', f'{f+40} {d}']
    return '\n'.join(lines) + '\n'


def validate(args):
    records = []
    args.output.mkdir(parents=True, exist_ok=True)
    def record(name, **checks):
        records.append(dict(case=name, checks=checks, passed=all(checks.values())))
        (args.output / 'results.json').write_text(json.dumps(records, indent=1) + '\n', newline='\n')
        print(name, checks, flush=True)
        if not all(checks.values()):
            raise AssertionError(name)

    def run(out, name, state, frames=args.frames, extra=(), exe=args.exe, interp=False, text=None, report=True):
        first = mp_run.start_frame(state)
        stem = out / name
        extra = list(extra) + ['--present-out', str(stem.with_suffix('.present.png'))]
        if report:
            extra += ['--widescreen-report', str(stem.with_suffix('.jsonl'))]
        r = mp_run.run(out, name, frames, state=state, route=route(first, frames) if text is None else text,
                       assist='life', extra=extra, exe=exe, interp=interp)
        r['stem'] = stem
        r['rows'] = [json.loads(line) for line in stem.with_suffix('.jsonl').read_text().splitlines()] if report else []
        return r

    def same(a, b, ext):
        return a['stem'].with_suffix(ext).read_bytes() == b['stem'].with_suffix(ext).read_bytes()

    for n in args.rounds:
        out = args.output / f'round{n}'
        state = ROOT / 'evidence' / 'rounds' / f'round{n}-start.cycstate'
        if args.catalog_only:
            out.mkdir(parents=True,exist_ok=True)
            catalog=out/'catalog'
            shutil.copytree(ROOT/'mods'/'preloaded'/'packages',catalog/'packages',dirs_exist_ok=True)
            (catalog/'state.toml').write_text('',newline='\n')
            base=run(out,'base',state,frames=120,exe=args.base,report=False)
            disabled=run(out,'default',state,frames=120,extra=['--mods-root',str(catalog)])
            record(f'round{n}/catalog-default',hash=same(base,disabled,'.hash'),picture=same(base,disabled,'.png'),state=same(base,disabled,'.cycstate'))
            config='[[package]]\nid = "monster-party.enhancement.widescreen"\nversion = "1.0.0"\n\n[[feature]]\npackage_id = "monster-party.enhancement.widescreen"\nid = "widescreen"\nenabled = true\n[feature.values]\naspect = "32-9"\nenemy_activation = "classic"\ncamera = "centered"\n'
            (catalog/'state.toml').write_text(config,newline='\n')
            enabled=run(out,'enabled',state,frames=120,extra=['--mods-root',str(catalog)])
            cli=run(out,'cli',state,frames=120,extra=['--widescreen','32:9'])
            record(f'round{n}/catalog-enabled',**{ext:same(enabled,cli,ext) for ext in ('.hash','.png','.present.png','.cycstate')},
                   width=all(row['enabled'] and row['width']==854 for row in enabled['rows']))
            continue
        if args.viewport_only:
            extra=['--widescreen','32:9','--widescreen-enemies','viewport']
            r=run(out,'viewport',state,extra=extra)
            i=run(out,'viewport-interp',state,extra=extra,interp=True)
            record(f'round{n}/viewport', **{ext:same(r,i,ext) for ext in ('.hash','.png','.present.png','.cycstate')},
                   isolated=all(row['failures']==0 and row['mod_failures']==0 and row['overflow']==0 for row in r['rows']),
                   terrain=all(row['terrain_errors']==0 for row in r['rows']))
            print('viewport counters',r['rows'][-1],flush=True)
            first=mp_run.start_frame(state)
            middle=out/'viewport-middle.cycstate'
            ram_log=out/'viewport.ram'
            whole=run(out,'viewport-whole',state,extra=extra+['--save-state',f'{first+args.frames//2-1}:{middle}','--mp-ram-log',str(ram_log)])
            lines=route(first,args.frames).splitlines()
            cut=first+args.frames//2
            prior=[line for line in lines if int(line.split()[0])<cut][-1]
            suffix=f'{cut} {prior.split(" ",1)[1]}\n'+'\n'.join(line for line in lines if int(line.split()[0])>=cut)
            replay=run(out,'viewport-replay',middle,frames=args.frames-args.frames//2,extra=extra,text=suffix)
            tail=replay['stem'].with_suffix('.hash').read_bytes().splitlines()
            ram=ram_log.read_bytes()
            duplicates=[]
            for at in range(0,len(ram),2048):
                indices=[ram[at+0x408+k] for k in range(3) if ram[at+0x3c6+k]&128]
                if len(indices)!=len(set(indices)):duplicates.append(at//2048)
            record(f'round{n}/viewport-save',state=same(whole,replay,'.cycstate'),picture=same(whole,replay,'.present.png'),
                   hashes=whole['stem'].with_suffix('.hash').read_bytes().splitlines()[-len(tail):]==tail,
                   unique_spawn_columns=not duplicates)
            continue
        base = run(out, 'base', state, exe=args.base, report=False)
        for name, extra in [('disabled', ()), ('off', ('--widescreen', 'off'))]:
            r = run(out, name, state, extra=extra)
            record(f'round{n}/{name}', hash=same(base,r,'.hash'), picture=same(base,r,'.png'), state=same(base,r,'.cycstate'))
        catalog = out / 'catalog'
        catalog.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT/'build-wide'/'mods'/'packages',catalog/'packages',dirs_exist_ok=True)
        (catalog / 'state.toml').write_text('', newline='\n')
        r = run(out, 'catalog-default', state, extra=['--mods-root', str(catalog)])
        record(f'round{n}/catalog-default', hash=same(base,r,'.hash'), state=same(base,r,'.cycstate'))
        for aspect, width in [('16:9',426),('21:9',560),('32:9',854)]:
            name = aspect.replace(':','-')
            r = run(out, name, state, extra=['--widescreen',aspect])
            size = struct.unpack('>II', r['stem'].with_suffix('.present.png').read_bytes()[16:24])
            record(f'round{n}/{name}', hash=same(base,r,'.hash'), machine=machine(base['state']) == machine(r['state']),
                   size=size == (width,240), sampled=any(row['terrain_samples'] > 0 for row in r['rows']),
                   terrain=all(row['terrain_errors']==0 for row in r['rows']),
                   isolated=all(row['failures']==0 and row['mod_failures']==0 and row['overflow']==0 for row in r['rows']))
            if aspect == '32:9':
                i = run(out, name+'-interp', state, extra=['--widescreen',aspect], interp=True)
                record(f'round{n}/32-9-parity', **{ext:same(r,i,ext) for ext in ('.hash','.png','.present.png','.cycstate')})
        for drawable, width in [('1280x720',426),('3840x1080',854),('1024x960',256)]:
            r = run(out, 'fit-'+drawable, state, frames=120, extra=['--widescreen','fit','--present-size',drawable])
            size = struct.unpack('>II',r['stem'].with_suffix('.present.png').read_bytes()[16:24])
            record(f'round{n}/fit-{drawable}', size=size == (width,240), terrain=all(row['terrain_errors']==0 for row in r['rows']))
        # Save at a frame within the same route; replay its exact input suffix.
        first = mp_run.start_frame(state)
        middle = out / 'middle.cycstate'
        whole = run(out, 'save-whole', state, extra=['--widescreen','32:9','--save-state',f'{first+args.frames//2-1}:{middle}'])
        suffix = '\n'.join(line for line in route(first,args.frames).splitlines() if int(line.split()[0]) >= first+args.frames//2)
        # Establish the pad at reload too when the checkpoint splits a held input.
        prior = [line for line in route(first,args.frames).splitlines() if int(line.split()[0]) < first+args.frames//2][-1]
        suffix = f'{first+args.frames//2} {prior.split(" ",1)[1]}\n' + suffix
        replay = run(out, 'save-replay', middle, frames=args.frames-args.frames//2, extra=['--widescreen','32:9'], text=suffix)
        tail = replay['stem'].with_suffix('.hash').read_bytes().splitlines()
        record(f'round{n}/save-replay', state=same(whole,replay,'.cycstate'), picture=same(whole,replay,'.present.png'),
               hashes=whole['stem'].with_suffix('.hash').read_bytes().splitlines()[-len(tail):] == tail)


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--exe',type=Path,default=ROOT/'build-wide'/'MonsterPartyRecomp.exe')
    ap.add_argument('--base',type=Path,default=ROOT/'wide-evidence'/'base'/'MonsterPartyRecomp.exe')
    ap.add_argument('--rounds',type=int,nargs='+',default=list(range(1,9)))
    ap.add_argument('--frames',type=int,default=900)
    ap.add_argument('--viewport-only',action='store_true')
    ap.add_argument('--catalog-only',action='store_true')
    validate(ap.parse_args())
