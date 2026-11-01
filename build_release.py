"""Build the public runtime ZIP from an explicit file allowlist."""
from pathlib import Path
import hashlib
import zipfile
from install import FILES

ROOT = Path(__file__).resolve().parent


def build():
    version = (ROOT / 'VERSION').read_text().strip()
    output = ROOT / 'website' / 'dist' / 'downloads'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'AJ_Tools.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for name in (*FILES, 'README.md'):
            bundle.write(ROOT / name, 'AJ_Tools/' + name)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(digest + '  AJ_Tools.zip\n')
    print('Built AJ Tools {}: {}'.format(version, archive))
    return archive


if __name__ == '__main__':
    build()
