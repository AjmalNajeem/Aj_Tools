# AJ Tools

Nuke tools by Ajmal Najeem. Initial release: 1.0.0.

## Requirements

Nuke 16+ with PySide6. Interactive Nuke only. W_Hotbox is optional.
Runtime testing inside Nuke is still required before production use.

## Install

1. Download and unzip `AJ_Tools.zip`.
2. Copy the enclosed `AJ_Tools` folder to your user `.nuke` directory and name it `Aj_Tools`.
3. Add this line to your existing `.nuke/init.py` (do not replace its contents):

```python
import nuke
nuke.pluginAddPath('./Aj_Tools')
```

Restart Nuke. Open **AjTools → AJ Tools Manager…**.

Alternatively run `python install.py /path/to/AJ_Tools.zip` using the installer
from the release. It backs up existing files and appends the startup hook.
Use only trusted release ZIPs: plugins execute Python code.

## Tools

- **Roto / RotoPaint Hotbox:** backtick opens contextual spline/paint tools.
  Hold Shift to apply multiple choices. Integrates with W_Hotbox when present.
- **Crop from Viewer:** draw a sample rectangle with Ctrl+Shift in the Viewer,
  then choose AjTools → Crop → Create from Viewer sample.
- **Manager:** enable/disable bundled plugins and install AJ Tools ZIP updates.
  Restart Nuke for changes to take effect. Preferences live in
  `.nuke/aj_tools_settings.json`, outside the installation folder.

## Development and release

Run `python build_release.py` to create the runtime download and SHA-256 checksum
in `website/dist/downloads`. The ZIP uses an explicit allowlist and excludes
backups, caches, settings, and Git metadata.

The static website is in `website/dist`. GitHub Pages deployment is configured
in `.github/workflows/pages.yml`. In repository settings, select GitHub Actions
as the Pages source. A custom domain can be configured after you purchase one.

## Review notes

The original menu had empty commands and removed AjTools unconditionally.
Those placeholders were replaced by the manager and implemented tools.
`Crop.txt` remains as the original reference; its executable version is `aj_crop.py`.
The original hotbox is preserved; its Nuke-specific callbacks and Viewer behavior
need an interactive Nuke check. The backup script is excluded from releases.
No license has been selected; choose a license before advertising the project
as open source. Publicly downloadable does not itself grant reuse rights.
