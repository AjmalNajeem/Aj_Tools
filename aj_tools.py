"""AJ Tools plugin manager for Nuke 16+ / PySide6."""
import json
from pathlib import Path
import nuke
from PySide6 import QtCore, QtGui, QtWidgets

ROOT = Path(__file__).resolve().parent
CONFIG = Path.home() / '.nuke' / 'aj_tools_settings.json'
_dialog = None


def settings():
    try:
        value = json.loads(CONFIG.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


class Manager(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('AJ Tools')
        self.resize(560, 360)
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel('AJ Tools')
        title.setStyleSheet('font-size:28px;font-weight:bold;color:#e9b75d')
        layout.addWidget(title)
        layout.addWidget(QtWidgets.QLabel('Plugin manager  /  v1.0.0  /  Nuke 16+'))
        self.checks = {}
        current = settings()
        for key, name, description in (
            ('hotbox', 'Roto / RotoPaint Hotbox', 'Context-aware spline and paint tools. Shortcut: backtick.'),
            ('crop', 'Crop from Viewer', 'Create a Crop from the Viewer sample rectangle.'),
        ):
            group = QtWidgets.QGroupBox(name)
            row = QtWidgets.QVBoxLayout(group)
            check = QtWidgets.QCheckBox('Enable plugin')
            check.setChecked(current.get(key, True))
            self.checks[key] = check
            row.addWidget(check)
            row.addWidget(QtWidgets.QLabel(description))
            layout.addWidget(group)
        self.status = QtWidgets.QLabel('Restart Nuke after saving preferences or installing an update.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QtWidgets.QHBoxLayout()
        for name, callback in [('Save preferences', self.save), ('Install AJ Tools ZIP…', self.install), ('Open folder', self.open_folder)]:
            button = QtWidgets.QPushButton(name)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def save(self):
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temp = CONFIG.with_suffix('.tmp')
            temp.write_text(json.dumps({k: c.isChecked() for k, c in self.checks.items()}, indent=2), encoding='utf-8')
            temp.replace(CONFIG)
            self.status.setText('Saved. Restart Nuke to apply changes.')
        except OSError as exc:
            self.status.setText('Could not save: {}'.format(exc))

    def install(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Install AJ Tools', '', 'AJ Tools release (*.zip)')
        if not filename:
            return
        answer = QtWidgets.QMessageBox.question(self, 'Install AJ Tools', 'Install this trusted AJ Tools ZIP? Plugins execute Python code. Existing files will be backed up. Restart Nuke afterward.')
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            from install import install_archive
            target = install_archive(filename)
            self.status.setText('Installed to {}. Restart Nuke.'.format(target))
        except Exception as exc:
            self.status.setText('Installation failed: {}'.format(exc))

    def open_folder(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(ROOT)))


def show_manager():
    global _dialog
    if _dialog is None:
        _dialog = Manager(QtWidgets.QApplication.activeWindow())
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def register():
    main = nuke.menu('Nuke')
    if main.findItem('AjTools') is not None:
        main.removeItem('AjTools')
    menu = main.addMenu('AjTools')
    menu.addCommand('AJ Tools Manager…', show_manager)
    menu.addSeparator()
    enabled = settings()
    if enabled.get('crop', True):
        def crop():
            try:
                import aj_crop
                aj_crop.crop_from_sample_area()
            except Exception as exc:
                nuke.message('AJ Tools: {}'.format(exc))
        menu.addCommand('Crop/Create from Viewer sample', crop)
    if enabled.get('hotbox', True):
        try:
            import AJ_Hotbox
            AJ_Hotbox.register()
            menu.addCommand('Roto / RotoPaint Hotbox', AJ_Hotbox._trigger_hotbox)
        except Exception as exc:
            nuke.tprint('AJ Tools hotbox failed: {}'.format(exc))
