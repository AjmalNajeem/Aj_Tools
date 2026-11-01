"""Install a trusted AJ Tools ZIP; preserve user startup configuration."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil
import tempfile
import zipfile

FILES = ('menu.py', 'aj_tools.py', 'AJ_Hotbox.py', 'aj_crop.py', 'install.py', 'VERSION')


def install_archive(archive, nuke_dir=None):
    home = Path(nuke_dir) if nuke_dir else Path.home() / '.nuke'
    target = home / 'Aj_Tools'
    with zipfile.ZipFile(archive) as bundle, tempfile.TemporaryDirectory() as temporary:
        members = bundle.infolist()
        if len(members) > 500 or sum(m.file_size for m in members) > 20 * 1024 * 1024:
            raise ValueError('Archive exceeds release limits.')
        candidates = [m for m in members if m.filename.endswith('aj_tools.py')]
        if len(candidates) != 1:
            raise ValueError('Expected one AJ Tools release.')
        prefix = candidates[0].filename[:-len('aj_tools.py')]
        staged = Path(temporary)
        for name in FILES:
            data = bundle.read(prefix + name)
            if name.endswith('.py'):
                compile(data, name, 'exec')
            (staged / name).write_bytes(data)
        # Never extract paths supplied by a ZIP. Copy only the explicit release files.
        home.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = home / ('Aj_Tools_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            shutil.copytree(target, backup, ignore=shutil.ignore_patterns('.git', '__pycache__', 'website', 'releases'))
        target.mkdir(exist_ok=True)
        for name in FILES:
            shutil.copy2(staged / name, target / name)
        startup = home / 'init.py'
        existing = startup.read_text(encoding='utf-8') if startup.exists() else ''
        line = "nuke.pluginAddPath('./Aj_Tools')"
        if line not in existing and 'nuke.pluginAddPath("./Aj_Tools")' not in existing:
            startup.write_text(existing + '\n# AJ Tools\nimport nuke\n' + line + '\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    parser.add_argument('--nuke-dir')
    args = parser.parse_args()
    print('Installed to {}'.format(install_archive(args.archive, args.nuke_dir)))
