"""Install the inspected test save with verified backups; restore without deleting saves."""
from pathlib import Path
import argparse, ctypes, hashlib, json, shutil, subprocess
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
TARGET=Path.home()/'AppData/Local/NINJAGAIDEN4'
SOURCE=ROOT/'test-save/extracted/100% WITH DLC'
STATE=ROOT/'test-save/installed.json'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stopped():
    result=subprocess.run(['tasklist','/FI','IMAGENAME eq NINJAGAIDEN4-Steam.exe','/FO','CSV','/NH'],capture_output=True,text=True)
    if result.returncode or 'NINJAGAIDEN4-Steam.exe' in result.stdout:
        raise RuntimeError('Exit Ninja Gaiden 4 normally before changing saves.')
def snapshot(label):
    dest=ROOT/'backups'/(label+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    shutil.copytree(TARGET,dest/'NINJAGAIDEN4')
    hashes={p.name:digest(p) for p in TARGET.iterdir() if p.is_file()}
    for name,h in hashes.items():
        if digest(dest/'NINJAGAIDEN4'/name)!=h:raise RuntimeError('Backup verification failed: '+name)
    (dest/'manifest.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
    return dest
def install():
    stopped()
    if STATE.exists():raise RuntimeError('Test save already installed; restore first.')
    files=[p for p in SOURCE.iterdir() if p.name=='GameData.dat' or p.name=='SystemData.vdf' or (p.name.startswith('SlotData_') and p.suffix=='.dat')]
    if len(files)!=17:raise RuntimeError('Unexpected inspected archive contents.')
    for p in files:
        expected=266992 if p.name=='GameData.dat' else 265704 if p.name=='SystemData.vdf' else 110600
        if p.stat().st_size!=expected:raise RuntimeError('Unexpected file size: '+p.name)
    backup=snapshot('before-test-import')
    state={'backup':str(backup),'target':str(TARGET),'files':{p.name:digest(p) for p in files},'status':'installing'}
    STATE.write_text(json.dumps(state,indent=2),encoding='utf-8')
    for p in files:shutil.copy2(p,TARGET/p.name)
    for name,h in state['files'].items():
        if digest(TARGET/name)!=h:raise RuntimeError('Installed checksum mismatch: '+name)
    state['status']='installed';STATE.write_text(json.dumps(state,indent=2),encoding='utf-8')
    print(json.dumps(state,indent=2))
def restore():
    stopped();state=json.loads(STATE.read_text(encoding='utf-8'))
    original=Path(state['backup']).resolve()
    if not original.is_relative_to((ROOT/'backups').resolve()):raise RuntimeError('Invalid backup location')
    hashes=json.loads((original/'manifest.json').read_text(encoding='utf-8'))
    for name,h in hashes.items():
        if Path(name).name!=name or digest(original/'NINJAGAIDEN4'/name)!=h:raise RuntimeError('Backup validation failed')
    snapshot('test-progress-before-restore')
    # Preserve the complete current directory; no recursive delete.
    archived=ROOT/'backups'/('displaced-test-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    shutil.move(str(TARGET),str(archived))
    shutil.copytree(original/'NINJAGAIDEN4',TARGET)
    for name,h in hashes.items():
        if digest(TARGET/name)!=h:raise RuntimeError('Restore validation failed')
    shutil.move(str(STATE),str(archived/'test-install-record.json'))
    print('Original saves restored. Test progress preserved at',archived)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['install','restore']);args=parser.parse_args()
    install() if args.action=='install' else restore()
