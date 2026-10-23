"""Hidden launcher smoke checks using private software OpenGL DLLs.

--runtime must be an isolated extracted release. Nothing is installed globally;
the software GL DLLs and all settings/caches stay in the supplied non-C: paths.
"""
import argparse
import ctypes
from ctypes import wintypes as wt
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def main(args):
    root=args.output.resolve()
    runtime=args.runtime.resolve()
    if root.drive.upper()=='C:' or runtime.drive.upper()=='C:':
        raise ValueError('Runtime and evidence must be on non-C: storage')
    root.mkdir(parents=True,exist_ok=True)
    for name in ('opengl32.dll','libgallium_wgl.dll'):
        shutil.copyfile(args.software_gl/name,runtime/name)
    user32=ctypes.WinDLL('user32',use_last_error=True)
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(wt.BOOL,wt.HWND,wt.LPARAM)
    user32.EnumWindows.argtypes=[callback_type,wt.LPARAM]
    user32.GetWindowThreadProcessId.argtypes=[wt.HWND,ctypes.POINTER(wt.DWORD)]
    user32.IsWindowVisible.argtypes=[wt.HWND]
    user32.IsWindowVisible.restype=wt.BOOL
    psapi.EnumProcessModulesEx.argtypes=[wt.HANDLE,ctypes.POINTER(wt.HMODULE),wt.DWORD,ctypes.POINTER(wt.DWORD),wt.DWORD]
    psapi.GetModuleFileNameExW.argtypes=[wt.HANDLE,wt.HMODULE,wt.LPWSTR,wt.DWORD]
    records=[]
    for name,rom,script in [('first-run',None,f'wait:5;shot:{root}/first-run.png;quit'),
                            ('configured',args.rom,f'wait:5;shot:{root}/dashboard.png;view:settings;wait:5;shot:{root}/settings.png;view:controller;wait:5;shot:{root}/controller.png;quit')]:
        scratch=root/name
        scratch.mkdir(exist_ok=True)
        env=dict(os.environ,TEMP=str(scratch),TMP=str(scratch),APPDATA=str(scratch/'roaming'),LOCALAPPDATA=str(scratch/'local'),
                 XDG_CACHE_HOME=str(scratch/'cache'),XDG_DATA_HOME=str(scratch/'data'),MESA_SHADER_CACHE_DISABLE='true',
                 MESA_SHADER_CACHE_DIR=str(scratch/'shader-cache'),GALLIUM_DRIVER='llvmpipe',LP_NUM_THREADS='2',
                 SDL_OPENGL_LIBRARY=str(runtime/'opengl32.dll'),SDL_VIDEODRIVER='windows',SDL_AUDIODRIVER='dummy',
                 LNG_TEST_HIDDEN='1',LNG_SCRIPT=script,LNG_SMOKE_FRAMES='200')
        env.pop('NESRECOMP_NO_LAUNCHER',None)
        cmd=[str(runtime/'MonsterPartyRecomp.exe'),'--hidden','--no-save','--config',str(scratch/'config.ini')]
        if rom:cmd.append(str(rom.resolve()))
        visible=[]
        modules=set()
        def inspect(hwnd,unused):
            pid=wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==proc.pid and user32.IsWindowVisible(hwnd):visible.append(int(hwnd))
            return True
        with (root/f'{name}.log').open('w',newline='\n') as log:
            proc=subprocess.Popen(cmd,cwd=runtime,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            start=time.monotonic()
            while proc.poll() is None:
                user32.EnumWindows(callback_type(inspect),0)
                if visible or time.monotonic()-start>60:
                    proc.terminate()
                    proc.wait(timeout=10)
                    raise AssertionError('Launcher became visible or failed to exit')
                array=(wt.HMODULE*512)()
                needed=wt.DWORD()
                if psapi.EnumProcessModulesEx(wt.HANDLE(int(proc._handle)),array,ctypes.sizeof(array),ctypes.byref(needed),3):
                    for module in array[:min(512,needed.value//ctypes.sizeof(wt.HMODULE))]:
                        text=ctypes.create_unicode_buffer(2048)
                        if psapi.GetModuleFileNameExW(wt.HANDLE(int(proc._handle)),module,text,len(text)):
                            if 'opengl32' in text.value.lower() or 'libgallium' in text.value.lower():modules.add(text.value)
                time.sleep(.02)
        private_gl=all(str(runtime).lower() in p.lower() for p in modules) and len(modules)>=2
        checks=dict(hidden=not visible,private_software_gl=private_gl,config_created=(scratch/'config.ini').exists(),clean_exit=proc.returncode==0)
        records.append(dict(case=name,checks=checks,modules=sorted(modules),passed=all(checks.values()),command=cmd))
        (root/'results.json').write_text(json.dumps(records,indent=1)+'\n',newline='\n')
        print(name,checks,flush=True)
        if not all(checks.values()):raise AssertionError(name)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime',type=Path,required=True)
    ap.add_argument('--software-gl',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--rom',type=Path,required=True)
    main(ap.parse_args())
