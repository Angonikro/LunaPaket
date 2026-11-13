#!/usr/bin/python3
import os, sys, subprocess, re, pwd, json
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QSettings, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import *
VERSION="0.1.35"

def privileged(args):
    """Führt Systembefehle direkt aus, wenn LunaPaket als root läuft."""
    return list(args) if os.geteuid() == 0 else ["pkexec", *args]

def relaunch_as_root():
    """Startet die GUI mit Root-Rechten und erhält den Zugriff auf die Desktop-Sitzung."""
    if os.geteuid() == 0:
        return
    env = os.environ.copy()
    # pkexec entfernt absichtlich fast alle Umgebungsvariablen. Nur die für
    # die bestehende grafische Sitzung notwendigen Werte explizit übergeben.
    keep = ["DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS", "QT_QPA_PLATFORM", "QT_QPA_PLATFORM_PLUGIN_PATH"]
    command = ["pkexec", "/usr/bin/env"]
    for key in keep:
        value = env.get(key)
        if value:
            command.append(f"{key}={value}")
    command += ["/usr/bin/python3", os.path.abspath(__file__), *sys.argv[1:]]
    os.execvp(command[0], command)
def cmd(args):
    p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=1800)
    return p.returncode,p.stdout
class Job(QThread):
    finished_text=Signal(int,str)
    def __init__(self,args): super().__init__(); self.args=args
    def run(self):
        try: r,o=cmd(self.args)
        except Exception as e: r,o=1,str(e)
        self.finished_text.emit(r,o)

class StreamJob(QThread):
    output = Signal(str)
    finished_text = Signal(int, str)
    def __init__(self, args):
        super().__init__(); self.args = args
    def run(self):
        chunks = []
        try:
            proc = subprocess.Popen(self.args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, universal_newlines=True,
                                    env={**os.environ, "LC_ALL": "C", "LANG": "C"})
            for line in iter(proc.stdout.readline, ''):
                chunks.append(line); self.output.emit(line.rstrip())
            proc.stdout.close(); rc = proc.wait()
            self.finished_text.emit(rc, ''.join(chunks))
        except Exception as exc:
            self.finished_text.emit(1, str(exc))

class FunctionJob(QThread):
    result=Signal(object)
    failed=Signal(str)
    def __init__(self, fn):
        super().__init__(); self.fn=fn
    def run(self):
        try: self.result.emit(self.fn())
        except Exception as e: self.failed.emit(str(e))

class ActionProgressDialog(QDialog):
    """Separates live action output from the normal protocol/details pane."""
    def __init__(self, parent, title, description):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 520)
        self.setWindowModality(Qt.WindowModal)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(description))
        self.current = QLabel("Vorgang wird gestartet …")
        layout.addWidget(self.current)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p %")
        layout.addWidget(self.progress)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)
        self.auto_close = QCheckBox("Fenster nach erfolgreicher Aktion schließen")
        self.auto_close.setChecked(True)
        layout.addWidget(self.auto_close)
        self.close_button = QPushButton("Vorgang läuft …")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)

    def append_output(self, line):
        if line:
            self.output.append(line)

    def set_progress(self, percent, message):
        if percent is not None:
            self.progress.setValue(max(0, min(100, int(percent))))
        if message:
            self.current.setText("Aktuell: " + message)

    def finish(self, code):
        if code == 0:
            self.progress.setValue(100)
            self.current.setText("Aktion erfolgreich abgeschlossen.")
            self.close_button.setText("Schließen")
        else:
            self.current.setText(f"Aktion fehlgeschlagen (Fehlercode {code}).")
            self.close_button.setText("Schließen")
        self.close_button.setEnabled(True)
        # Nur bei erfolgreichem Abschluss automatisch schließen. Bei Fehlern
        # bleibt das Protokoll sichtbar, damit die Ursache gelesen werden kann.
        if code == 0 and self.auto_close.isChecked():
            QTimer.singleShot(1200, self.accept)
class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("LunaPaket – Paketverwaltung · "+VERSION); self.resize(1100,720); self.queue={}
        self.catalog_cache = None
        self._catalog_loading = False
        self._table_catalog_ready = False
        self._theme_placeholder = True
        # Auch bei pkexec muss LunaPaket die Einstellungen des angemeldeten
        # Desktop-Benutzers verwenden und nicht /root/.config.
        desktop_uid = int(os.environ.get("PKEXEC_UID", os.environ.get("SUDO_UID", os.getuid())))
        desktop_user = pwd.getpwuid(desktop_uid)
        config_home = os.environ.get("XDG_CONFIG_HOME") if desktop_uid == os.getuid() else None
        if not config_home:
            config_home = os.path.join(desktop_user.pw_dir, ".config")
        settings_dir = os.path.join(config_home, "LunaPaket")
        os.makedirs(settings_dir, mode=0o700, exist_ok=True)
        self.settings = QSettings(os.path.join(settings_dir, "LunaPaket.conf"), QSettings.IniFormat)
        self.language = str(self.settings.value("language", "de"))
        self.theme = str(self.settings.value("theme", "dark"))
        self.apply_theme()
        self.font_size = int(self.settings.value("font_size", 11))
        app_font = QApplication.font(); app_font.setPointSize(self.font_size); QApplication.setFont(app_font)
        w=QWidget(); self.setCentralWidget(w); outer=QHBoxLayout(w)
        self.sidebar=QListWidget(); self.sidebar.setObjectName("packageSidebar"); self.sidebar.setFixedWidth(205)
        self.sidebar.addItems(["Alle Pakete", "Installiert", "Nicht installiert", "Aufräumen", "Vorgemerkt"])
        self.sidebar.setCurrentRow(0); self.sidebar.currentRowChanged.connect(self.sidebar_changed)
        outer.addWidget(self.sidebar)
        content=QWidget(); outer.addWidget(content,1); l=QVBoxLayout(content)
        h=QHBoxLayout(); title=QLabel("<span style='font-size:22pt;color:#b99aff;font-weight:bold'>LunaPaket</span><br>" + ("Debian package manager" if self.language == "en" else "Debian-Paketverwaltung")); self._main_subtitle_label = title; h.addWidget(title); h.addStretch()
        self.repo_btn=QPushButton("Paketquellen verwalten")
        self.repo_btn.setToolTip("APT-Repositories hinzufügen, bearbeiten, aktivieren oder deaktivieren")
        self.repo_btn.clicked.connect(self.manage_sources)
        h.addWidget(self.repo_btn)
        self.update_btn=QPushButton("Paketlisten aktualisieren"); self.update_btn.clicked.connect(self.update_lists); h.addWidget(self.update_btn)
        up=QPushButton("System aktualisieren"); up.clicked.connect(self.upgrade); h.addWidget(up)
        sec=QPushButton("Sicherheitsupdates verwalten"); sec.clicked.connect(self.manage_security_updates); h.addWidget(sec); l.addLayout(h)
        self.security_auto_timer = QTimer(self)
        self.security_auto_timer.timeout.connect(self.check_security_updates_silently)
        self.configure_security_timer()
        bar=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Pakete suchen …"); self.search.returnPressed.connect(self.search_pkgs); bar.addWidget(self.search,1)
        self.filter=QComboBox(); self.filter.addItems(["Suchergebnisse","Installierte Pakete"]); self.filter.currentIndexChanged.connect(self.search_pkgs); bar.addWidget(self.filter)
        b=QPushButton("Suchen"); b.clicked.connect(self.search_pkgs); bar.addWidget(b); l.addLayout(bar)
        self.cleanup_select_all = QCheckBox("Alle Pakete vormerken")
        self.cleanup_select_all.setToolTip("Alle von APT als entbehrlich erkannten Pakete zur Entfernung vormerken")
        self.cleanup_select_all.setVisible(False)
        self.cleanup_select_all.toggled.connect(self.toggle_all_cleanup_packages)
        l.addWidget(self.cleanup_select_all)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["","Paket","Version","Status","Beschreibung"]); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QAbstractItemView.AllEditTriggers); self.table.setSortingEnabled(False); self.table.horizontalHeader().setSortIndicatorShown(True); self.table.sortItems(1, Qt.AscendingOrder); self.table.horizontalHeader().setStretchLastSection(True); self.table.setColumnWidth(0,34); self.table.setColumnWidth(1,270); self.table.setColumnWidth(2,135); self.table.setColumnWidth(3,145); self.table.itemSelectionChanged.connect(self.details_for_selected); self.table.itemChanged.connect(self.checkbox_changed); self.table.setContextMenuPolicy(Qt.CustomContextMenu); self.table.customContextMenuRequested.connect(self.package_context_menu); l.addWidget(self.table,4)
        row=QHBoxLayout()
        clear_queue_btn=QPushButton("Vormerkung löschen")
        clear_queue_btn.clicked.connect(self.clear_queue)
        row.addWidget(clear_queue_btn)
        apply_queue_btn=QPushButton("Vorgemerkte Änderungen anwenden")
        apply_queue_btn.clicked.connect(self.apply_queued_changes)
        row.addWidget(apply_queue_btn)
        l.addLayout(row); self.details=QTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(170); l.addWidget(self.details,1)
        self.queue_label=QLabel("Keine vorgemerkten Änderungen"); l.addWidget(self.queue_label); self.status=QLabel("Bereit"); l.addWidget(self.status)
        # Hauptmenü „Datei“ mit den wichtigsten Datei- und Programmaktionen.
        file_menu = self.menuBar().addMenu("Datei")

        open_deb_action = QAction("DEB-Pakete öffnen …", self)
        open_deb_action.setShortcut("Ctrl+O")
        open_deb_action.setToolTip("Eine oder mehrere lokale Debian-Paketdateien auswählen und installieren")
        open_deb_action.triggered.connect(lambda checked=False: self.install_local_deb())
        file_menu.addAction(open_deb_action)

        apply_queue_action = QAction("Vorgemerkte Änderungen anwenden", self)
        apply_queue_action.setShortcut("Ctrl+Return")
        apply_queue_action.setToolTip("Vorgemerkte Paketinstallationen und -entfernungen ausführen")
        apply_queue_action.triggered.connect(self.apply_queued_changes)
        file_menu.addAction(apply_queue_action)

        refresh_action = QAction("Paketlisten aktualisieren", self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self.update_lists)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()
        exit_action = QAction("Beenden", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        m=self.menuBar().addMenu("Paketquellen")
        manage_sources_action=QAction("Paketquellen verwalten …",self)
        manage_sources_action.triggered.connect(self.manage_sources)
        m.addAction(manage_sources_action)
        m.addSeparator()
        check_sources_action=QAction("Paketquellen prüfen / Paketlisten aktualisieren",self)
        check_sources_action.triggered.connect(self.check_sources)
        m.addAction(check_sources_action)
        view_sources_action=QAction("Paketquellen anzeigen",self)
        view_sources_action.triggered.connect(self.sources)
        m.addAction(view_sources_action)
        settings_menu=self.menuBar().addMenu("Einstellungen")
        distribution_action = QAction("Distribution …", self)
        distribution_action.triggered.connect(self.distribution_settings)
        settings_menu.addAction(distribution_action)
        font_action=QAction("Schriftgröße …",self); font_action.triggered.connect(self.choose_font_size); settings_menu.addAction(font_action)
        settings_menu.addSeparator()
        settings_action = QAction("Allgemeine Einstellungen …", self)
        settings_action.triggered.connect(self.show_settings)
        settings_menu.addAction(settings_action)
        self.remember_window_enabled = self.settings.value("window/remember", True, type=bool)
        self.clean_cache_enabled = self.settings.value("package/clean_cache_after_install", True, type=bool)
        help_menu = self.menuBar().addMenu("Hilfe")
        def show_about():
            title = "Über LunaPaket" if self.language == "de" else "About LunaPaket"
            description = ("Grafische Paketverwaltung für Debian." if self.language == "de"
                           else "Graphical package manager for Debian.")
            about_html = (
                "<div style='min-width:300px;'>"
                "<div style='font-size:20pt;font-weight:700;color:#a98bff;'>LunaPaket</div>"
                f"<div style='font-size:10pt;margin-top:3px;'>Version {VERSION}</div>"
                "<hr style='border:0;border-top:1px solid #666;margin:12px 0;'>"
                "<div style='font-size:12pt;font-weight:600;'>Goldisoft 2026</div>"
                f"<div style='font-size:10pt;margin-top:7px;'>{description}</div>"
                "</div>"
            )
            QMessageBox.about(self, title, about_html)

        help_menu.addAction("Über LunaPaket", show_about)
        self.translate_main_window()
        self.load_installed()
        if self.remember_window_enabled and self.settings.contains("window/geometry"):
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
        self._settings_uid = desktop_uid
        self._settings_gid = desktop_user.pw_gid
        self._settings_dir = settings_dir
        self._settings_file = os.path.join(settings_dir, "LunaPaket.conf")
        self._sync_settings_permissions()

    def apply_theme(self):
        if self.theme == "light":
            self.setStyleSheet("QMainWindow,QWidget{background:#f3f4f8;color:#252638;font-size:11pt} QLineEdit,QComboBox,QTextEdit,QTableWidget{background:#ffffff;color:#252638;border:1px solid #c9cbd8;padding:6px} QPushButton{background:#6746b8;color:white;border:0;border-radius:6px;padding:8px 13px} QPushButton:hover{background:#7959cb} QHeaderView::section{background:#e4e2ee;color:#37334b;padding:7px} QListWidget#packageSidebar{background:#e9e8f0;border:1px solid #c9c6d6;padding:5px} QListWidget#packageSidebar::item{padding:11px 8px;border-radius:5px} QListWidget#packageSidebar::item:selected{background:#6746b8;color:white} QTableWidget::indicator{width:18px;height:18px} QTableWidget::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QTableWidget::indicator:unchecked{background:#ffffff;border:2px solid #8d899e;border-radius:3px} QCheckBox::indicator{width:18px;height:18px} QCheckBox::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QCheckBox::indicator:unchecked{background:#ffffff;border:2px solid #8d899e;border-radius:3px}")
        else:
            self.setStyleSheet("QMainWindow,QWidget{background:#20212a;color:#eeeef5;font-size:11pt} QLineEdit,QComboBox,QTextEdit,QTableWidget{background:#292b37;color:#f2f1fa;border:1px solid #48495d;padding:6px} QPushButton{background:#6746b8;color:white;border:0;border-radius:6px;padding:8px 13px} QPushButton:hover{background:#7959cb} QHeaderView::section{background:#343545;color:#ddd9f4;padding:7px} QListWidget#packageSidebar{background:#252633;border:1px solid #414253;padding:5px} QListWidget#packageSidebar::item{padding:11px 8px;border-radius:5px} QListWidget#packageSidebar::item:selected{background:#6746b8;color:white} QTableWidget::indicator{width:18px;height:18px} QTableWidget::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QTableWidget::indicator:unchecked{background:#171821;border:2px solid #aaa3bd;border-radius:3px} QCheckBox::indicator{width:18px;height:18px} QCheckBox::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QCheckBox::indicator:unchecked{background:#ffffff;border:2px solid #c9b5ff;border-radius:3px}")
    def translate_main_window(self):
        translations = {
            "LunaPaket – Paketverwaltung":"LunaPaket – Package Manager",
            "Alle Pakete":"All packages","Installiert":"Installed","Nicht installiert":"Not installed",
            "Aufräumen":"Cleanup","Vorgemerkt":"Queued","Paketquellen verwalten":"Manage repositories",
            "APT-Repositories hinzufügen, bearbeiten, aktivieren oder deaktivieren":"Add, edit, enable or disable APT repositories",
            "Paketlisten aktualisieren":"Refresh package lists","System aktualisieren":"Upgrade system",
            "Sicherheitsupdates verwalten":"Manage security updates","Pakete suchen …":"Search packages …",
            "Suchergebnisse":"Search results","Installierte Pakete":"Installed packages","Suchen":"Search",
            "Paket":"Package","Version":"Version","Status":"Status","Beschreibung":"Description",
            "Vormerkung löschen":"Clear queue","Vorgemerkte Änderungen anwenden":"Apply queued changes",
            "Keine vorgemerkten Änderungen":"No queued changes","Alle Pakete vormerken":"Mark all packages","Bereit":"Ready","Datei":"File",
            "DEB-Pakete öffnen …":"Open DEB packages …",
            "Eine oder mehrere lokale Debian-Paketdateien auswählen und installieren":"Select and install one or more local Debian package files",
            "Vorgemerkte Paketinstallationen und -entfernungen ausführen":"Execute queued package installations and removals",
            "Beenden":"Quit","Paketquellen":"Repositories","Paketquellen verwalten …":"Manage repositories …",
            "Paketquellen prüfen / Paketlisten aktualisieren":"Check repositories / refresh package lists",
            "Paketquellen anzeigen":"Show repositories","Einstellungen":"Settings",
            "Distribution …":"Distribution …","Schriftgröße …":"Font size …",
            "Allgemeine Einstellungen …":"General settings …","Hilfe":"Help","Über LunaPaket":"About LunaPaket",
            "Debian-Paketverwaltung":"Debian package manager",
            "Fenstergröße und Fensterposition merken":"Remember window size and position",
            "Heruntergeladene Paketdateien nach erfolgreicher Installation löschen":"Delete downloaded package files after successful installation",
            "Schließen":"Close"
        }
        mapping = translations if self.language == "en" else {v: k for k, v in translations.items()}

        current_title = self.windowTitle()
        german_prefix = "LunaPaket – Paketverwaltung"
        english_prefix = "LunaPaket – Package Manager"
        if self.language == "en" and current_title.startswith(german_prefix):
            current_title = current_title.replace(german_prefix, english_prefix, 1)
        elif self.language == "de" and current_title.startswith(english_prefix):
            current_title = current_title.replace(english_prefix, german_prefix, 1)
        self.setWindowTitle(current_title)

        for obj in self.findChildren(QWidget):
            if isinstance(obj, (QPushButton, QLabel, QCheckBox, QRadioButton, QGroupBox)):
                value = obj.text()
                # The main subtitle is rich text, so translate its embedded phrase.
                if obj is getattr(self, "_main_subtitle_label", None):
                    obj.setText(value.replace("Debian-Paketverwaltung", mapping.get("Debian-Paketverwaltung", "Debian-Paketverwaltung"))
                                    .replace("Debian package manager", mapping.get("Debian package manager", "Debian package manager")))
                elif value in mapping:
                    obj.setText(mapping[value])
            if isinstance(obj, QLineEdit):
                value = obj.placeholderText()
                if value in mapping: obj.setPlaceholderText(mapping[value])
            if isinstance(obj, QListWidget):
                for i in range(obj.count()):
                    item = obj.item(i)
                    item.setText(mapping.get(item.text(), item.text()))
            if isinstance(obj, QComboBox):
                for i in range(obj.count()):
                    value = obj.itemText(i)
                    obj.setItemText(i, mapping.get(value, value))
            if isinstance(obj, QTableWidget):
                for i in range(obj.columnCount()):
                    item = obj.horizontalHeaderItem(i)
                    if item: item.setText(mapping.get(item.text(), item.text()))
                for row in range(obj.rowCount()):
                    status_item = obj.item(row, 3)
                    if status_item:
                        status_item.setText(mapping.get(status_item.text(), status_item.text()))
        for action in self.findChildren(QAction):
            action.setText(mapping.get(action.text(), action.text()))
        for menu in self.findChildren(QMenu):
            menu.setTitle(mapping.get(menu.title(), menu.title()))

    def _sync_settings_permissions(self):
        # Settings belong to the logged-in desktop user even when the GUI
        # itself was started with pkexec.
        try:
            self.settings.sync()
            os.chown(self._settings_dir, self._settings_uid, self._settings_gid)
            os.chmod(self._settings_dir, 0o700)
            if os.path.exists(self._settings_file):
                os.chown(self._settings_file, self._settings_uid, self._settings_gid)
                os.chmod(self._settings_file, 0o600)
        except OSError:
            pass

    def set_remember_window(self, enabled):
        self.remember_window_enabled = bool(enabled)
        self.settings.setValue("window/remember", self.remember_window_enabled)
        if self.remember_window_enabled:
            self.settings.setValue("window/geometry", self.saveGeometry())
        else:
            self.settings.remove("window/geometry")
        self._sync_settings_permissions()

    def distribution_settings(self):
        d = QDialog(self)
        d.setWindowTitle("Einstellungen – Distribution")
        d.resize(760, 390)
        layout = QVBoxLayout(d)
        # Eigenständiger Dialog: nur die Distribution-Einstellungen anzeigen.
        page = QWidget()
        page_layout = QVBoxLayout(page)
        warning = QLabel("⚠  Diese Einstellungen betreffen die elementaren Bestandteile Ihres Systems. Überdenken Sie solche Änderungen daher eingehend.")
        warning.setWordWrap(True); warning.setStyleSheet("font-weight:bold;padding:12px;color:#e4dce9")
        page_layout.addWidget(warning)
        page_layout.addWidget(QLabel("Paketaktualisierungsverhalten (vorgegebene Distribution)"))
        highest = QRadioButton("Immer die höchste Version bevorzugen")
        installed = QRadioButton("Immer die installierte Version bevorzugen")
        selected = QRadioButton("Version bevorzugen von:")
        release = QComboBox(); release.setEditable(True)
        releases = set()
        for path in self._source_files():
            try:
                raw = Path(path).read_text(encoding="utf-8", errors="replace")
                for line in raw.splitlines():
                    if line.strip() and not line.lstrip().startswith('#'):
                        parts=line.split()
                        if len(parts) >= 3 and parts[0] in ("deb", "deb-src"):
                            releases.add(parts[2])
                for match in re.finditer(r"(?im)^Suites?:\s*(.+)$", raw):
                    releases.update(match.group(1).split())
            except OSError: pass
        release.addItems(sorted(releases) or ["stable", "testing", "trixie"])
        saved_mode = self.settings.value("distribution/mode", "highest")
        saved_release = self.settings.value("distribution/release", "stable")
        if release.findText(str(saved_release)) < 0: release.addItem(str(saved_release))
        release.setCurrentText(str(saved_release))
        {"highest": highest, "installed": installed, "release": selected}.get(str(saved_mode), highest).setChecked(True)
        page_layout.addWidget(highest); page_layout.addWidget(installed)
        release_row = QHBoxLayout(); release_row.addWidget(selected); release_row.addWidget(release, 1); page_layout.addLayout(release_row)
        page_layout.addStretch(1); layout.addWidget(page, 1)
        buttons = QDialogButtonBox()
        apply_btn = buttons.addButton("Anwenden", QDialogButtonBox.ApplyRole)
        cancel_btn = buttons.addButton("Abbrechen", QDialogButtonBox.RejectRole)
        ok_btn = buttons.addButton("OK", QDialogButtonBox.AcceptRole)
        layout.addWidget(buttons)
        def save():
            mode = "highest" if highest.isChecked() else "installed" if installed.isChecked() else "release"
            self.settings.setValue("distribution/mode", mode)
            self.settings.setValue("distribution/release", release.currentText().strip() or "stable")
            self._sync_settings_permissions()
        apply_btn.clicked.connect(save)
        cancel_btn.clicked.connect(d.reject)
        ok_btn.clicked.connect(lambda: (save(), d.accept()))
        d.exec()

    def show_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("LunaPaket – Einstellungen" if self.language == "de" else "LunaPaket – Settings")
        dlg.setMinimumWidth(520)
        layout = QVBoxLayout(dlg)
        language_row = QHBoxLayout()
        language_label = QLabel("Sprache / Language")
        language_combo = QComboBox()
        language_combo.addItem("Deutsch", "de")
        language_combo.addItem("English", "en")
        language_combo.setCurrentIndex(0 if self.language == "de" else 1)
        language_row.addWidget(language_label); language_row.addWidget(language_combo, 1)
        layout.addLayout(language_row)
        theme_row = QHBoxLayout()
        theme_label = QLabel("Farbschema / Theme")
        theme_combo = QComboBox()
        theme_combo.addItem("Dunkel / Dark", "dark")
        theme_combo.addItem("Hell / Light", "light")
        theme_combo.setCurrentIndex(0 if self.theme == "dark" else 1)
        theme_row.addWidget(theme_label); theme_row.addWidget(theme_combo, 1)
        layout.addLayout(theme_row)
        remember = QCheckBox()
        remember.setChecked(self.remember_window_enabled)
        cache = QCheckBox()
        def update_settings_language():
            english = self.language == "en"
            dlg.setWindowTitle("LunaPaket – Settings" if english else "LunaPaket – Einstellungen")
            remember.setText("Remember window size and position" if english else "Fenstergröße und Fensterposition merken")
            remember.setToolTip("Saves the window size and position on exit and restores them next time." if english else "Speichert Größe und Position beim Schließen und stellt sie beim nächsten Start wieder her.")
            cache.setText("Delete downloaded package files after successful installation" if english else "Heruntergeladene Paketdateien nach erfolgreicher Installation löschen")
            buttons.button(QDialogButtonBox.Close).setText("Close" if english else "Schließen")
        cache.setChecked(self.clean_cache_enabled)
        cache.setChecked(self.clean_cache_enabled)
        layout.addWidget(remember)
        layout.addWidget(cache)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        update_settings_language()
        remember.toggled.connect(self.set_remember_window)
        def language_changed(index):
            self.language = language_combo.currentData()
            self.settings.setValue("language", self.language)
            self.translate_main_window()
            update_settings_language()
            self._sync_settings_permissions()
        def theme_changed(index):
            self.theme = theme_combo.currentData()
            self.settings.setValue("theme", self.theme)
            self.apply_theme()
            self._sync_settings_permissions()
        language_combo.currentIndexChanged.connect(language_changed)
        theme_combo.currentIndexChanged.connect(theme_changed)
        def cache_changed(enabled):
            self.clean_cache_enabled = bool(enabled)
            self.settings.setValue("package/clean_cache_after_install", self.clean_cache_enabled)
            self._sync_settings_permissions()
        cache.toggled.connect(cache_changed)
        dlg.exec()

    def closeEvent(self, event):
        if self.remember_window_enabled:
            self.settings.setValue("window/geometry", self.saveGeometry())
        self._sync_settings_permissions()
        super().closeEvent(event)
    def rows(self, data):
        # Vollständige Paketliste ohne Seitenlimit. Die Qt-Items werden in
        # kleinen automatischen Portionen erzeugt, damit die GUI Ereignisse
        # weiter verarbeitet und nicht einfriert.
        self._rows_generation = getattr(self, "_rows_generation", 0) + 1
        generation = self._rows_generation
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        self.table.clearContents()
        self._rows_pending = data
        self._rows_offset = 0
        self._rows_chunk_size = 300
        self.table.setRowCount(len(data))
        self.status.setText((f"0 of {len(data)} packages displayed …" if self.language == "en" else f"0 von {len(data)} Paketen werden angezeigt …"))
        self.table.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda g=generation: self._fill_rows_chunk(g))

    def _fill_rows_chunk(self, generation=None):
        if generation is None:
            generation = getattr(self, "_rows_generation", 0)
        if generation != getattr(self, "_rows_generation", 0):
            return
        data = self._rows_pending
        start = self._rows_offset
        end = min(start + self._rows_chunk_size, len(data))
        self.table.setUpdatesEnabled(False)
        for i in range(start, end):
            r = data[i]
            name = r[0]
            installed = len(r) > 2 and str(r[2]) == "Installiert"
            action = self.queue.get(name, "")
            checked = installed
            if action in ("install", "reinstall") or action.startswith("version:"):
                checked = True
            elif action in ("remove", "purge"):
                checked = False
            check = QTableWidgetItem("")
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            check.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            check.setData(Qt.UserRole, name)
            check.setData(Qt.UserRole + 1, installed)
            self.table.setItem(i, 0, check)
            for c, v in enumerate(r):
                display_value = str(v)
                if self.language == "en":
                    display_value = {"Installiert": "Installed", "Nicht installiert": "Not installed",
                                     "Vorgemerkt": "Queued"}.get(display_value, display_value)
                it = QTableWidgetItem(display_value)
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                it.setData(Qt.UserRole, name)
                self.table.setItem(i, c + 1, it)
        self._rows_offset = end
        self.table.setUpdatesEnabled(True)
        if end < len(data):
            self.status.setText((f"{end} of {len(data)} packages displayed …" if self.language == "en" else f"{end} von {len(data)} Paketen werden angezeigt …"))
            QTimer.singleShot(1, lambda g=generation: self._fill_rows_chunk(g))
        else:
            self.table.blockSignals(False)
            self._table_catalog_ready = True
            self.apply_table_filters()
            self.status.setText((f"{len(data)} packages loaded · Categories are filtered without reloading" if self.language == "en" else f"{len(data)} Pakete vollständig geladen · Kategorien werden ohne Neuladen gefiltert"))

    def checkbox_changed(self, item):
        if item.column() != 0 or self.table.signalsBlocked():
            return
        name=item.data(Qt.UserRole)
        if not name:
            return
        installed = bool(item.data(Qt.UserRole + 1))
        checked = item.checkState() == Qt.Checked
        # Checked means installed / installation requested; unchecked means absent / removal requested.
        if checked and not installed:
            self.queue[name] = "install"
        elif not checked and installed:
            self.queue[name] = "remove"
        else:
            self.queue.pop(name, None)
        self.update_queue_label()
        if getattr(self, "_table_catalog_ready", False):
            self.apply_row_filter(item.row())

    def installed(self):
        _,o=cmd(["dpkg-query","-W","-f=${binary:Package}\t${Version}\t${db:Status-Status}\t${binary:Summary}\n"])
        out=[]
        for x in o.splitlines():
            p=x.split("\t",3)
            if len(p)>=3 and p[2]=="installed": out.append((p[0],p[1],"Installiert",p[3] if len(p)>3 else ""))
        return out
    def load_installed(self):
        self.search_pkgs()
    def sidebar_changed(self, _row):
        # Das Sammelkästchen ist ausschließlich im Bereich „Aufräumen“ sichtbar.
        self.cleanup_select_all.blockSignals(True)
        self.cleanup_select_all.setChecked(False)
        self.cleanup_select_all.blockSignals(False)
        self.cleanup_select_all.setVisible(_row == 3)
        # Kategorien werden direkt in der bereits geladenen Tabelle gefiltert.
        # Kein erneuter APT-/DPKG-Aufruf und kein erneuter Tabellenaufbau.
        if getattr(self, "_table_catalog_ready", False):
            self.apply_table_filters()
        else:
            self.search_pkgs()

    def toggle_all_cleanup_packages(self, checked):
        """Merkt alle APT-Autoremove-Kandidaten gesammelt zur Entfernung vor."""
        if self.catalog_cache is None:
            return
        candidates = set(self.catalog_cache.get("autoremove", set()))
        if not candidates:
            self.status.setText("Keine entbehrlichen Pakete gefunden.")
            return
        self.table.blockSignals(True)
        changed = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            name = str(item.data(Qt.UserRole) or "")
            if name.split(":", 1)[0] not in candidates:
                continue
            installed = bool(item.data(Qt.UserRole + 1))
            if not installed:
                continue
            if checked:
                item.setCheckState(Qt.Unchecked)
                self.queue[name] = "remove"
            else:
                item.setCheckState(Qt.Checked)
                if self.queue.get(name) == "remove":
                    self.queue.pop(name, None)
            changed += 1
        self.table.blockSignals(False)
        self.update_queue_label()
        self.status.setText(f"{changed} Aufräum-Pakete {'zur Entfernung vorgemerkt' if checked else 'aus der Vormerkung entfernt'}.")
    def choose_font_size(self):
        size, ok = QInputDialog.getInt(self, "Schriftgröße", "Schriftgröße in Punkt:", self.font_size, 8, 24, 1)
        if ok:
            self.font_size = size
            self.settings.setValue("font_size", size)
            font = QApplication.font(); font.setPointSize(size); QApplication.setFont(font)
            self.status.setText(f"Schriftgröße auf {size} pt gesetzt")
    def search_pkgs(self):
        # Der Katalog wird genau einmal aufgebaut. Solange die erste
        # Tabellenbefüllung läuft, dürfen Filter-/Sidebar-Klicks keinen
        # weiteren APT-Lesejob starten.
        if self.catalog_cache is not None:
            if getattr(self, "_table_catalog_ready", False):
                self.apply_table_filters()
            # Während der initialen Tabellenbefüllung nur den aktuellen
            # Filterzustand merken; _fill_rows_chunk wendet ihn am Ende an.
            return
        if getattr(self, "_catalog_loading", False):
            return
        self._catalog_loading = True
        self.status.setText("Paketkatalog wird einmalig im Hintergrund geladen …")
        self.search_job = FunctionJob(self.collect_catalog)
        self.search_job.result.connect(self.catalog_loaded)
        self.search_job.failed.connect(self.catalog_load_failed)
        self.search_job.start()

    def apply_row_filter(self, row):
        """Aktualisiert nur die Sichtbarkeit einer geänderten Tabellenzeile."""
        if self.catalog_cache is None or not getattr(self, "_table_catalog_ready", False):
            return
        if row < 0 or row >= self.table.rowCount():
            return
        check = self.table.item(row, 0)
        name_item = self.table.item(row, 1)
        if check is None or name_item is None:
            self.table.setRowHidden(row, True)
            return
        name = str(check.data(Qt.UserRole) or name_item.text())
        installed = bool(check.data(Qt.UserRole + 1))
        action = self.queue.get(name)
        category = self.sidebar.currentRow()
        autoremove = self.catalog_cache.get("autoremove", set())
        show = not (category == 1 and not installed or category == 2 and installed or category == 3 and name.split(":", 1)[0] not in autoremove or category == 4 and not action)
        term = self.search.text().strip().casefold()
        if show and term:
            searchable = " ".join(self.table.item(row, col).text() for col in range(1, 5) if self.table.item(row, col))
            show = term in searchable.casefold()
        self.table.setRowHidden(row, not show)

    def apply_table_filters(self):
        if self.catalog_cache is None or not getattr(self, "_table_catalog_ready", False):
            return
        term = self.search.text().strip().casefold()
        category = self.sidebar.currentRow()
        upgradable = self.catalog_cache["upgradable"]
        held = self.catalog_cache["held"]
        autoremove = self.catalog_cache.get("autoremove", set())
        visible = 0
        self.table.setUpdatesEnabled(False)
        for row in range(self.table.rowCount()):
            check = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            if check is None or name_item is None:
                self.table.setRowHidden(row, True)
                continue
            name = str(check.data(Qt.UserRole) or name_item.text())
            installed = bool(check.data(Qt.UserRole + 1))
            key = name.split(":", 1)[0]
            action = self.queue.get(name)
            show = True
            if category == 1 and not installed: show = False
            elif category == 2 and installed: show = False
            elif category == 3 and key not in autoremove: show = False
            elif category == 4 and not action: show = False
            if show and term:
                searchable = " ".join(self.table.item(row, col).text() for col in range(1, 5) if self.table.item(row, col))
                if term not in searchable.casefold(): show = False
            self.table.setRowHidden(row, not show)
            if show: visible += 1
        self.table.setUpdatesEnabled(True)
        self.status.setText((f"{visible} packages shown · Full list remains in memory" if self.language == "en" else f"{visible} Pakete angezeigt · Gesamtliste bleibt im Speicher"))

    @staticmethod
    def collect_catalog():
        """
        Nutzt apt-cache pkgnames als maßgebliche Paketnamensliste (wie die
        bisherige vollständige LunaPaket-Liste) und python-apt für Details.
        So bleiben Paketanzahl und Namensbestand konsistent, während Version,
        Installationsstatus und Beschreibung direkt aus libapt-pkg kommen.
        """
        import apt
        import apt_pkg

        cache = apt.Cache()
        native_arch = apt_pkg.config.find("APT::Architecture") or os.uname().machine

        # Exakt dieselbe eindeutige Namensbasis wie apt-cache pkgnames.
        rc, names_out = cmd(["apt-cache", "pkgnames"])
        if rc != 0:
            raise RuntimeError("Paketnamen konnten nicht aus APT gelesen werden.\\n" + names_out)
        names = sorted({line.strip() for line in names_out.splitlines() if line.strip()},
                       key=str.casefold)

        # Cache-Einträge nach unqualifiziertem Paketnamen gruppieren. Bei
        # Multiarch-Paketen wird der native Eintrag bevorzugt; "all" ist
        # ebenfalls zulässig. Fremdarchitekturvarianten erzeugen keine Extras.
        candidates = {}
        for package in cache:
            installed = package.installed
            candidate = package.candidate
            selected = installed if installed is not None else candidate
            arch = getattr(selected, "architecture", "") if selected else ""
            base_name = package.name.split(":", 1)[0]
            rank = 0 if arch == native_arch else (1 if arch == "all" else 2)
            current = candidates.get(base_name)
            if current is None or rank < current[0]:
                candidates[base_name] = (rank, package)

        rows = []
        upgradable = set()
        autoremove = set()
        for name in names:
            entry = candidates.get(name.split(":", 1)[0])
            if entry is None:
                rows.append((name, "", "Nicht installiert", ""))
                continue
            package = entry[1]
            installed = package.installed
            candidate = package.candidate
            is_installed = installed is not None
            selected = installed if is_installed else candidate
            version = selected.version if selected is not None else ""
            summary = (selected.summary or "") if selected is not None else ""
            rows.append((name, version,
                         "Installiert" if is_installed else "Nicht installiert",
                         summary))
            if package.is_upgradable:
                upgradable.add(name.split(":", 1)[0])
            if package.is_auto_removable:
                autoremove.add(name.split(":", 1)[0])

        _, hold_out = cmd(["apt-mark", "showhold"])
        held = set(x.strip().split(":", 1)[0]
                   for x in hold_out.splitlines() if x.strip())

        return {"rows": rows, "upgradable": upgradable,
                "held": held, "autoremove": autoremove}

    @staticmethod
    def filter_catalog(catalog, term, category, queue):
        needle = term.casefold()
        result = []
        for original in catalog["rows"]:
            row = original
            name = row[0]
            key = name.split(":", 1)[0]
            installed = row[2] == "Installiert"
            if category == 1 and not installed:
                continue
            if category == 2 and installed:
                continue
            if category == 3 and key not in catalog.get("autoremove", set()):
                continue
            if category == 4:
                if name not in queue:
                    continue
                action = queue[name]
                row = (name, action.split(":", 1)[1] if action.startswith("version:") else row[1], "Vorgemerkt", action)
            if needle and needle not in " ".join(str(v) for v in row).casefold():
                continue
            result.append(row)
        return result

    def catalog_loaded(self, catalog):
        self._catalog_loading = False
        self.catalog_cache = catalog
        self._table_catalog_ready = False
        self.rows(catalog["rows"])

    def catalog_load_failed(self, error):
        self._catalog_loading = False
        self.status.setText("Fehler beim Laden: " + str(error))

    def search_done(self, rows):
        self.rows(rows)
        if getattr(self, "search_again", False): self.search_pkgs()
    def selected(self):
        x=self.table.selectedItems(); return x[0].data(Qt.UserRole) if x else None
    def details_for_selected(self):
        n=self.selected()
        if not n or self.table.currentColumn() == 0:
            return
        cache = getattr(self, "_details_cache", None)
        if cache is None:
            self._details_cache = {}; cache = self._details_cache
        if n in cache:
            self.details.setPlainText(cache[n]); return
        self.details.setPlainText("Paketinformationen werden geladen …")
        self.details_job=FunctionJob(lambda: cmd(["apt-cache","show",n])[1])
        def show_details(out, name=n):
            self._details_cache[name] = out[:16000] or "Keine Paketdetails verfügbar."
            if self.selected() == name:
                self.details.setPlainText(self._details_cache[name])
        self.details_job.result.connect(show_details)
        self.details_job.failed.connect(lambda e: self.details.setPlainText("Fehler: "+e))
        self.details_job.start()
    def package_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return
        self.table.selectRow(item.row())
        name = self.selected()
        if not name:
            return
        menu = QMenu(self)
        menu.addAction("Installieren vormerken", lambda: self.mark("install"))
        menu.addAction("Neu installieren vormerken", lambda: self.mark("reinstall"))
        menu.addAction("Entfernen vormerken", lambda: self.mark("remove"))
        menu.addAction("Vollständig entfernen (Purge) vormerken", lambda: self.mark("purge"))
        menu.addSeparator()
        menu.addAction("Version auswählen …", self.choose_version)
        held = self.package_is_held(name)
        menu.addAction("Versionssperre aufheben vormerken" if held else "Version sperren vormerken",
                       lambda: self.mark("unhold" if held else "hold"))
        menu.addSeparator()
        menu.addAction("Abhängigkeiten und Konflikte …", self.show_dependency_analysis)
        menu.addAction("Eigenschaften …", self.show_properties)
        menu.addAction("Installierte Dateien anzeigen …", self.show_package_files)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def package_is_held(self, name):
        r, out = cmd(["apt-mark", "showhold"])
        return name in out.splitlines()

    def choose_version(self):
        name = self.selected()
        if not name:
            return
        _, out = cmd(["apt-cache", "madison", name])
        versions = []
        for line in out.splitlines():
            parts = [x.strip() for x in line.split("|")]
            if len(parts) >= 2 and parts[1] and parts[1] not in versions:
                versions.append(parts[1])
        if not versions:
            QMessageBox.information(self, "Version auswählen", "Für dieses Paket wurden keine verfügbaren Versionen gefunden.")
            return
        version, ok = QInputDialog.getItem(self, "Version auswählen", f"Version für {name}:", versions, 0, False)
        if ok and version:
            self.queue[name] = "version:" + version
            self.update_queue_label()
            self.refresh_checkbox(name)

    def update_queue_label(self):
        if not self.queue:
            self.queue_label.setText("Keine vorgemerkten Änderungen")
        else:
            labels = {"install":"Installieren", "reinstall":"Neu installieren", "remove":"Entfernen", "purge":"Vollständig entfernen", "hold":"Version sperren", "unhold":"Versionssperre aufheben"}
            self.queue_label.setText("Vorgemerkt: " + ", ".join(f"{k} ({labels.get(v, v)})" for k, v in self.queue.items()))

    def show_properties(self):
        name = self.selected()
        if not name:
            return
        _, out = cmd(["apt-cache", "show", name])
        d = QDialog(self); d.setWindowTitle("Paketeigenschaften – " + name); d.resize(820, 560)
        lay = QVBoxLayout(d); t = QTextEdit(); t.setReadOnly(True); t.setPlainText(out or "Keine Eigenschaften verfügbar."); lay.addWidget(t)
        bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(d.reject); bb.accepted.connect(d.accept); lay.addWidget(bb); d.exec()

    def show_package_files(self):
        name = self.selected()
        if not name:
            return
        r, out = cmd(["dpkg", "-L", name])
        if r != 0:
            QMessageBox.information(self, "Installierte Dateien", "Das Paket ist nicht installiert oder dpkg konnte die Dateiliste nicht lesen.\n\n" + out)
            return
        d = QDialog(self); d.setWindowTitle("Installierte Dateien – " + name); d.resize(760, 520)
        lay = QVBoxLayout(d); t = QTextEdit(); t.setReadOnly(True); t.setPlainText(out); lay.addWidget(t)
        bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(d.reject); lay.addWidget(bb); d.exec()

    def sync_queue_from_checkboxes(self):
        """Gleicht die interne Vormerkliste vor dem Anwenden mit allen Checkboxen ab.

        Dadurch gehen Klicks nicht verloren, falls Qt ein itemChanged-Signal
        während eines Tabellen-Updates unterdrückt oder verzögert hat.
        Spezielle Vormerkungen wie Purge, Neuinstallation, Versionswahl und
        Versionssperren bleiben unverändert erhalten.
        """
        special_actions = {"reinstall", "purge", "hold", "unhold"}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            name = item.data(Qt.UserRole)
            if not name:
                continue
            current = self.queue.get(name)
            if current in special_actions or (isinstance(current, str) and current.startswith("version:")):
                continue

            installed = bool(item.data(Qt.UserRole + 1))
            checked = item.checkState() == Qt.Checked
            if checked and not installed:
                self.queue[name] = "install"
            elif not checked and installed:
                self.queue[name] = "remove"
            else:
                self.queue.pop(name, None)

        self.update_queue_label()

    def apply_queued_changes(self):
        """Führt ausschließlich die ausdrücklich vorgemerkten Paketaktionen aus."""
        self.sync_queue_from_checkboxes()
        if not self.queue:
            QMessageBox.information(
                self,
                "Vorgemerkte Änderungen",
                "Es sind keine Änderungen vorgemerkt. Bitte Pakete zuerst über die Kontrollkästchen auswählen."
            )
            return
        self.commit()

    def install_action(self):
        # Kompatible interne Einzelaktion; die Hauptoberfläche verwendet
        # ausschließlich apply_queued_changes().
        name = self.selected()
        if not self.queue and name:
            self.queue[name] = "install"
            self.update_queue_label()
            self.refresh_checkbox(name)
        if not self.queue:
            QMessageBox.information(self, "Installieren", "Bitte zuerst Pakete auswählen oder vormerken.")
            return
        self.commit()

    def remove_action(self):
        # In der Kategorie „Aufräumen“ bleibt APTs bestehende Autoremove-Erkennung erhalten.
        if self.sidebar.currentRow() == 3:
            self.show_autoremove_dialog()
            return
        name = self.selected()
        if not self.queue and name:
            self.queue[name] = "remove"
            self.update_queue_label()
            self.refresh_checkbox(name)
        if not self.queue:
            QMessageBox.information(self, "Entfernen", "Bitte zuerst Pakete auswählen oder vormerken.")
            return
        self.commit()

    def show_autoremove_dialog(self):
        if self.catalog_cache is None:
            QMessageBox.information(self, "Aufräumen", "Der Paketkatalog wird noch geladen.")
            return
        candidates = sorted(self.catalog_cache.get("autoremove", set()), key=str.casefold)
        if not candidates:
            QMessageBox.information(self, "Aufräumen", "Es werden keine nicht mehr benötigten Pakete gefunden.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Aufräumen bestätigen – {len(candidates)} Pakete")
        dlg.resize(720, 480)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Diese Pakete hat APT als nicht mehr benötigt erkannt. Sollen sie entfernt werden?"))
        listing = QListWidget()
        listing.addItems(candidates)
        listing.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(listing, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Jetzt aufräumen")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            self.status.setText("Aufräumen abgebrochen – keine Pakete entfernt")
            return
        # Beibehalten: die tatsächlich funktionierende APT-Autoremove-Ausführung.
        self.run_action_job(privileged(["apt-get", "-o", "APT::Status-Fd=2", "-y", "autoremove"]),
                            "Aufräumen", f"APT entfernt nicht mehr benötigte Pakete ({len(candidates)} gefunden).",
                            len(candidates))

    def mark(self,action):
        n=self.selected()
        if not n: QMessageBox.information(self,"LunaPaket","Bitte zuerst ein Paket auswählen."); return
        self.queue[n]=action; self.update_queue_label(); self.refresh_checkbox(n)
    def refresh_checkbox(self, name):
        for row in range(self.table.rowCount()):
            item=self.table.item(row,0)
            if item and item.data(Qt.UserRole)==name:
                self.table.blockSignals(True)
                installed = bool(item.data(Qt.UserRole + 1))
                action = self.queue.get(name, "")
                checked = installed
                if action in ("install", "reinstall") or action.startswith("version:"):
                    checked = True
                elif action in ("remove", "purge"):
                    checked = False
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                self.table.blockSignals(False)
                break
    def clear_queue(self):
        self.queue.clear(); self.update_queue_label()
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item=self.table.item(row,0)
            if item:
                item.setCheckState(Qt.Checked if bool(item.data(Qt.UserRole + 1)) else Qt.Unchecked)
        self.table.blockSignals(False)
    def commit(self):
        if not self.queue:
            return
        actions = dict(self.queue)
        self.status.setText("Änderungen werden im Hintergrund geprüft …")
        self.set_busy(True)
        self.preview_job = FunctionJob(lambda: self.build_preview(actions))
        self.preview_job.result.connect(lambda result: self.show_commit_preview(actions, result))
        self.preview_job.failed.connect(self.preview_failed)
        self.preview_job.start()

    @staticmethod
    def build_preview(actions):
        apt_commands = []
        groups = [("install", ["install"]), ("reinstall", ["install", "--reinstall"]), ("remove", ["remove"]), ("purge", ["purge"])]
        for action, apt_args in groups:
            names = [n for n, a in actions.items() if a == action]
            if names:
                apt_commands.append(["apt-get", "-s"] + apt_args + names)
        versions = [(n, a.split(":", 1)[1]) for n, a in actions.items() if a.startswith("version:")]
        for n, version in versions:
            apt_commands.append(["apt-get", "-s", "install", f"{n}={version}"])
        previews = []
        for command in apt_commands:
            rc, output = cmd(command)
            previews.append("$ " + " ".join(command) + "\n" + output)
            if rc != 0:
                raise RuntimeError(output or "APT-Simulation fehlgeschlagen")
        for n, a in actions.items():
            if a in ("hold", "unhold"):
                previews.append(f"$ apt-mark {a} {n}\nVersionssperre {'aktivieren' if a == 'hold' else 'aufheben'}")
        return "\n\n".join(previews) or "Keine APT-Änderungen."

    def preview_failed(self, error):
        self.set_busy(False)
        self.status.setText("Prüfung fehlgeschlagen")
        QMessageBox.critical(self, "APT-Prüfung fehlgeschlagen", str(error))

    def show_commit_preview(self, actions, preview):
        self.set_busy(False)
        dlg = QDialog(self)
        dlg.setWindowTitle("Paketaktionen bestätigen")
        dlg.resize(800, 560)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Prüfe die geplanten Aktionen. Entferne Häkchen, um einzelne Aktionen abzuwählen."))
        listing = QListWidget()
        labels = {"install":"Installieren", "reinstall":"Neu installieren", "remove":"Entfernen",
                  "purge":"Vollständig entfernen", "hold":"Version sperren", "unhold":"Versionssperre aufheben"}
        for name, action in actions.items():
            label = f"{labels.get(action, action)}: {name}"
            if action.startswith("version:"):
                label = f"Version {action.split(':', 1)[1]} installieren: {name}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            listing.addItem(item)
        layout.addWidget(listing, 2)
        layout.addWidget(QLabel("APT-Prüfung (Simulation, noch keine Änderungen ausgeführt):"))
        details = QTextEdit()
        details.setReadOnly(True)
        details.setPlainText(preview)
        layout.addWidget(details, 1)
        auto_close = QCheckBox("Fenster nach erfolgreicher Aktion schließen")
        auto_close.setChecked(True)
        layout.addWidget(auto_close)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Jetzt ausführen")
        buttons.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            self.status.setText("Vorgemerkte Änderungen bleiben erhalten")
            return
        actions = {listing.item(i).data(Qt.UserRole): actions[listing.item(i).data(Qt.UserRole)]
                   for i in range(listing.count()) if listing.item(i).checkState() == Qt.Checked}
        if not actions:
            self.status.setText("Keine Paketaktionen ausgewählt")
            return
        commands = []
        groups = [("install", ["install"]), ("reinstall", ["install", "--reinstall"]),
                  ("remove", ["remove"]), ("purge", ["purge"])]
        versions = [(n, a.split(":", 1)[1]) for n, a in actions.items() if a.startswith("version:")]
        for action, apt_args in groups:
            names = [n for n, a in actions.items() if a == action]
            if names:
                commands.append(["apt-get", "-o", "APT::Status-Fd=2", "-y"] + apt_args + names)
        commands.extend([["apt-get", "-o", "APT::Status-Fd=2", "-y", "install", f"{n}={version}"] for n, version in versions])
        commands.extend([["apt-mark", a, n] for n, a in actions.items() if a in ("hold", "unhold")])
        if not commands:
            return
        has_installation = any(a in ("install", "reinstall") or a.startswith("version:") for a in actions.values())
        if has_installation and self.clean_cache_enabled:
            commands.append(["apt-get", "clean"])
        self.queue.clear()
        self.update_queue_label()
        shell = "set -e; " + " && ".join(" ".join("'" + x.replace("'", "'\\''") + "'" for x in c) for c in commands)
        expected = sum(1 for action in actions.values()
                       if action in ("install", "reinstall", "remove", "purge") or action.startswith("version:"))
        self.run_action_job(privileged(["/bin/sh", "-c", shell]), "Paketaktionen",
                            f"{len(actions)} ausgewählte Paketaktion(en) werden ausgeführt.", expected,
                            auto_close=auto_close.isChecked())

    def set_busy(self, busy):
        self._busy = bool(busy)
        self.update_btn.setEnabled(not busy)

    @staticmethod
    def apt_status_progress(line):
        """Liest APTs maschinenlesbares dlstatus-/pmstatus-Protokoll."""
        clean = line.strip().lstrip("\\x1b")
        fields = clean.split(":", 3)
        if len(fields) < 4:
            return None, None
        kind = fields[0].strip().lower()
        if kind == "dlstatus":
            # Format: dlstatus:AlreadyDownloaded:TotalPercentage:description
            try:
                percent = float(fields[2].strip())
            except (TypeError, ValueError):
                return None, None
            message = fields[3].strip() or "Pakete werden heruntergeladen"
            return max(0, min(99, round(percent))), message
        if kind == "pmstatus":
            # Format: pmstatus:package:TotalPercentage:description
            package = fields[1].strip()
            try:
                percent = float(fields[2].strip())
            except (TypeError, ValueError):
                return None, None
            message = fields[3].strip() or "Paket wird verarbeitet"
            label = f"{package} – {message}" if package else message
            return max(0, min(99, round(percent))), label
        return None, None

    def run_action_job(self, args, title, description, expected=0, auto_close=True):
        self.status.setText("Paketaktion läuft …")
        self.set_busy(True)
        dialog = ActionProgressDialog(self, title, description)
        dialog.auto_close.setChecked(bool(auto_close))
        self.action_stream = StreamJob(args)
        completed = set()
        def output_line(line):
            dialog.append_output(line)
            apt_percent, apt_message = self.apt_status_progress(line)
            if apt_percent is not None:
                dialog.set_progress(apt_percent, apt_message)
                return
            # Fallback for APT versions without status-fd progress.
            match = re.match(r"^(?:Setting up|Removing|Purging|Unpacking)\\s+([^ :]+)", line)
            if match:
                package = match.group(1)
                completed.add(package)
                percent = min(99, int(len(completed) * 100 / max(1, expected))) if expected else None
                dialog.set_progress(percent, package)
            elif line:
                dialog.set_progress(None, line[:180])
        self.action_stream.output.connect(output_line)
        def finished(code, output):
            dialog.finish(code)
            self.set_busy(False)
            self.details.setPlainText(output[-18000:])
            self.status.setText("Paketaktion abgeschlossen" if code == 0 else f"Paketaktion fehlgeschlagen (APT-Code {code})")
            if code == 0:
                self.catalog_cache = None
                self._table_catalog_ready = False
                self.search_pkgs()
        self.action_stream.finished_text.connect(finished)
        self.action_stream.start()
        dialog.exec()

    def run_job(self,args):
        self.status.setText("APT arbeitet im Hintergrund …"); self.set_busy(True)
        self.job=Job(args); self.job.finished_text.connect(self.job_done); self.job.start()
    def job_done(self,r,o):
        self.set_busy(False)
        self.details.setPlainText(o[-18000:])
        self.status.setText("Abgeschlossen" if r==0 else "Fehler – Details unten")
        if r == 0:
            self.catalog_cache = None
            self._table_catalog_ready = False
        self.search_pkgs()
    def update_lists(self):
        self.catalog_cache = None
        self._table_catalog_ready = False
        self.run_job(privileged(["apt-get","update"]))
    def upgrade(self):
        self.catalog_cache = None
        self._table_catalog_ready = False
        # Erst Paketlisten aktualisieren und Upgrade-Kandidaten ermitteln.
        self.status.setText("Paketquellen werden aktualisiert …")
        self.set_busy(True)
        self.upgrade_check_job = FunctionJob(self.check_upgrades)
        self.upgrade_check_job.result.connect(self.upgrade_check_done)
        self.upgrade_check_job.failed.connect(self.upgrade_check_failed)
        self.upgrade_check_job.start()

    @staticmethod
    def check_upgrades():
        rc, update_output = cmd(privileged(["apt-get", "update"]))
        if rc != 0:
            raise RuntimeError("Paketlisten konnten nicht aktualisiert werden.\n\n" + update_output)
        rc, listing = cmd(["apt", "list", "--upgradable"])
        if rc != 0:
            raise RuntimeError(listing or "Aktualisierungen konnten nicht ermittelt werden.")
        packages = [line.strip() for line in listing.splitlines()[1:] if line.strip() and "/" in line]
        # APT nennt bei der Upgrade-Simulation die Herkunft der Zielversion.
        # Debian-Sicherheitsquellen sind an security.debian.org bzw.
        # trixie-security/bookworm-security und Debian-Security erkennbar.
        rc, simulation = cmd(["apt-get", "-s", "upgrade"])
        if rc != 0:
            raise RuntimeError(simulation or "Sicherheitsaktualisierungen konnten nicht erkannt werden.")
        security_names = set()
        for line in simulation.splitlines():
            match = re.match(r"^Inst\s+(\S+).*\(([^)]*)\)", line)
            if not match:
                continue
            origin = match.group(2).lower()
            if ("security.debian.org" in origin or "debian-security" in origin or
                    "trixie-security" in origin or "bookworm-security" in origin or
                    "bullseye-security" in origin):
                security_names.add(match.group(1).split(":", 1)[0])
        security_packages = []
        for line in packages:
            name_arch = line.split()[0].split("/", 1)[0]
            if name_arch.split(":", 1)[0] in security_names:
                security_packages.append(line)
        return update_output, packages, security_packages

    def upgrade_check_failed(self, error):
        self.set_busy(False)
        self.status.setText("Aktualisierungsprüfung fehlgeschlagen")
        QMessageBox.critical(self, "System aktualisieren", str(error))

    def upgrade_check_done(self, result):
        update_output, packages, security_packages = result
        self.set_busy(False)
        if not packages:
            self.status.setText("System ist auf dem neuesten Stand")
            QMessageBox.information(self, "System aktualisieren",
                                    "Es sind keine Paketaktualisierungen verfügbar.\n\nDas System ist aktuell.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Verfügbare Aktualisierungen – {len(packages)} Pakete")
        dlg.resize(900, 590)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(
            f"{len(packages)} Aktualisierung(en) gefunden, davon {len(security_packages)} Sicherheitsaktualisierung(en).\n"
            "Noch wurde nichts installiert."
        ))
        table = QTableWidget(len(packages), 4)
        table.setHorizontalHeaderLabels(["Paket", "Neue Version", "Quelle / Architektur", "Art"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        security_set = {line.split()[0].split("/", 1)[0].split(":", 1)[0] for line in security_packages}
        for row, line in enumerate(packages):
            fields = line.split()
            name_arch = fields[0] if fields else line
            name = name_arch.split("/", 1)[0]
            version = fields[1] if len(fields) > 1 else ""
            source = fields[2].strip("[]") if len(fields) > 2 else ""
            kind = "Sicherheitsupdate" if name.split(":", 1)[0] in security_set else "Normales Update"
            for col, value in enumerate((name, version, source, kind)):
                table.setItem(row, col, QTableWidgetItem(value))
        lay.addWidget(table, 3)
        lay.addWidget(QLabel("APT-Prüfung und verfügbare Pakete:"))
        log = QTextEdit(); log.setReadOnly(True); log.setMaximumHeight(110)
        log.setPlainText("Paketlisten erfolgreich aktualisiert.\n" + "\n".join(packages))
        lay.addWidget(log, 1)
        auto_close = QCheckBox("Fenster nach erfolgreicher Aktion schließen")
        auto_close.setChecked(True)
        lay.addWidget(auto_close)
        buttons = QDialogButtonBox()
        cancel = buttons.addButton("Abbrechen", QDialogButtonBox.RejectRole)
        security_btn = None
        if security_packages:
            security_btn = buttons.addButton("Nur Sicherheitsupdates installieren", QDialogButtonBox.ActionRole)
        all_btn = buttons.addButton("Alle Aktualisierungen installieren", QDialogButtonBox.AcceptRole)
        lay.addWidget(buttons)
        choice = {"mode": None}
        cancel.clicked.connect(dlg.reject)
        all_btn.clicked.connect(lambda: (choice.update(mode="all"), dlg.accept()))
        if security_btn:
            security_btn.clicked.connect(lambda: (choice.update(mode="security"), dlg.accept()))
        if dlg.exec() != QDialog.Accepted or not choice["mode"]:
            self.status.setText("Aktualisierung abgebrochen – nichts installiert")
            return
        selected = security_packages if choice["mode"] == "security" else packages
        self.start_upgrade_install(selected, security_only=(choice["mode"] == "security"),
                                   auto_close=auto_close.isChecked())

    def start_upgrade_install(self, packages, security_only=False, auto_close=True):
        title = "Sicherheitsaktualisierungen installieren" if security_only else "System wird aktualisiert"
        description = f"{len(packages)} Paketaktualisierung(en) werden installiert."
        progress = ActionProgressDialog(self, title, description)
        progress.auto_close.setChecked(bool(auto_close))
        self.set_busy(True)
        if security_only:
            names = [line.split()[0].split("/", 1)[0] for line in packages]
            args = privileged(["apt-get", "-o", "APT::Status-Fd=2", "-y", "--only-upgrade", "install", *names])
        else:
            args = privileged(["apt-get", "-o", "APT::Status-Fd=2", "-y", "upgrade"])
        self.upgrade_stream = StreamJob(args)
        unpacked = set()
        configured = set()

        def upgrade_output_line(line):
            progress.append_output(line)
            apt_percent, apt_message = self.apt_status_progress(line)
            if apt_percent is not None:
                progress.set_progress(apt_percent, apt_message)
                return
            unpack_match = re.match(r"^(?:Unpacking|Preparing to unpack)\s+([^ :]+)", line)
            setup_match = re.match(r"^Setting up\s+([^ :]+)", line)
            if unpack_match:
                package = unpack_match.group(1)
                unpacked.add(package)
                percent = min(50, int(len(unpacked) * 50 / max(1, len(packages))))
                progress.set_progress(percent, package + " (Entpacken)")
            elif setup_match:
                package = setup_match.group(1)
                configured.add(package)
                percent = 50 + min(49, int(len(configured) * 49 / max(1, len(packages))))
                progress.set_progress(percent, package + " (Einrichten)")
            elif line:
                progress.set_progress(None, line[:180])

        self.upgrade_stream.output.connect(upgrade_output_line)
        def finished(rc, output):
            progress.finish(rc)
            self.set_busy(False)
            if rc == 0:
                self.status.setText("Sicherheitsaktualisierungen abgeschlossen" if security_only else "Systemaktualisierung abgeschlossen")
                self.catalog_cache = None
                self._table_catalog_ready = False
            else:
                self.status.setText("Fehler bei der Aktualisierung")
            self.search_pkgs()
        self.upgrade_stream.finished_text.connect(finished)
        self.upgrade_stream.start()
        progress.exec()


    def _security_deferred(self):
        raw = self.settings.value("security/deferred", "{}")
        try:
            value = json.loads(raw) if isinstance(raw, str) else dict(raw)
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _security_history(self):
        raw = self.settings.value("security/history", "[]")
        try:
            value = json.loads(raw) if isinstance(raw, str) else list(raw)
            return value if isinstance(value, list) else []
        except Exception:
            return []

    def _save_security_history(self, action, package, version, result):
        from datetime import datetime
        history = self._security_history()
        history.insert(0, {"time": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"),
                           "action": action, "package": package, "version": version, "result": result})
        self.settings.setValue("security/history", json.dumps(history[:250], ensure_ascii=False))
        self.settings.sync()

    def configure_security_timer(self):
        enabled = self.settings.value("security/auto_check", False, type=bool)
        minutes = max(15, self.settings.value("security/check_interval_minutes", 360, type=int))
        self.security_auto_timer.stop()
        if enabled:
            self.security_auto_timer.start(minutes * 60 * 1000)

    def check_security_updates_silently(self):
        if getattr(self, "_security_check_running", False) or getattr(self, "_busy", False):
            return
        self._security_check_running = True
        self.security_silent_job = FunctionJob(self.find_security_updates)
        def done(items):
            self._security_check_running = False
            active = [x for x in items if not x["deferred"]]
            self.status.setText(f"Automatische Sicherheitsprüfung: {len(active)} offene Sicherheitsupdates")
            previous = self.settings.value("security/last_count", -1, type=int)
            self.settings.setValue("security/last_count", len(active))
            self.settings.setValue("security/last_check", __import__("datetime").datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"))
            if len(active) > max(0, previous):
                self.status.setText(f"Neue Sicherheitsupdates gefunden: {len(active)}")
        def failed(error):
            self._security_check_running = False
            self.status.setText("Automatische Sicherheitsprüfung fehlgeschlagen")
        self.security_silent_job.result.connect(done)
        self.security_silent_job.failed.connect(failed)
        self.security_silent_job.start()

    @staticmethod
    def find_security_updates():
        rc, update_out = cmd(privileged(["apt-get", "update"]))
        if rc:
            raise RuntimeError("Paketlisten konnten nicht aktualisiert werden:\n" + update_out)
        rc, listing = cmd(["apt", "list", "--upgradable"])
        if rc:
            raise RuntimeError(listing)
        items = []
        for line in listing.splitlines()[1:]:
            fields = line.strip().split()
            if len(fields) < 2 or "/" not in fields[0]:
                continue
            package_arch = fields[0].split("/", 1)[0]
            package = package_arch.split(":", 1)[0]
            candidate = fields[1]
            rc, policy = cmd(["apt-cache", "policy", package])
            if rc:
                continue
            # Nur Versionen aus eindeutig erkennbaren Debian-Sicherheitsquellen zählen.
            security_origins = []
            policy_lines = policy.splitlines()
            candidate_block = False
            for row in policy_lines:
                stripped = row.strip()
                if stripped.startswith("*** "):
                    version_token = stripped[4:].split()[0] if len(stripped[4:].split()) else ""
                    candidate_block = (version_token == candidate)
                    continue
                if candidate_block:
                    # Stop at the next version stanza, but retain repository rows.
                    if re.match(r"^\s{2,}\S+\s+\d+\s*$", row) and not row.lstrip().startswith(("500 ", "100 ", "990 ", "700 ", "600 ", "400 ", "300 ", "200 ", "100 ")):
                        candidate_block = False
                        continue
                    low = row.lower()
                    if ("security.debian.org" in low or "debian-security" in low or
                        "trixie-security" in low or "bookworm-security" in low or
                        "bullseye-security" in low):
                        security_origins.append(stripped)
            if security_origins:
                rc, installed = cmd(["dpkg-query", "-W", "-f=${Version}", package])
                items.append({"package": package, "candidate": candidate,
                              "installed": installed.strip() if rc == 0 else "nicht installiert",
                              "origin": "; ".join(security_origins)})
        return items

    def manage_security_updates(self):
        self.status.setText("Sicherheitsupdates werden gesucht …")
        self.set_busy(True)
        self.security_manage_job = FunctionJob(self.find_security_updates)
        self.security_manage_job.result.connect(self.security_updates_dialog)
        def failed(error):
            self.set_busy(False)
            QMessageBox.critical(self, "Sicherheitsupdates", str(error))
        self.security_manage_job.failed.connect(failed)
        self.security_manage_job.start()

    def security_updates_dialog(self, items):
        self.set_busy(False)
        deferred = self._security_deferred()
        for item in items:
            item["deferred"] = deferred.get(item["package"]) == item["candidate"]
        dlg = QDialog(self); dlg.setWindowTitle("Sicherheitsupdates verwalten"); dlg.resize(980, 650)
        layout = QVBoxLayout(dlg)
        active = sum(not x["deferred"] for x in items)
        layout.addWidget(QLabel(f"{len(items)} Sicherheitsupdate(s) gefunden · {active} aktiv · {len(items)-active} zurückgestellt"))
        table = QTableWidget(len(items), 6)
        table.setHorizontalHeaderLabels(["Auswahl", "Paket", "Installiert", "Verfügbar", "Status", "Sicherheitsquelle"])
        table.setEditTriggers(QTableWidget.NoEditTriggers); table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        for row, item in enumerate(items):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Unchecked if item["deferred"] else Qt.Checked)
            table.setItem(row, 0, check)
            values = [item["package"], item["installed"], item["candidate"],
                      "Zurückgestellt" if item["deferred"] else "Bereit", item["origin"]]
            for col, value in enumerate(values, 1):
                table.setItem(row, col, QTableWidgetItem(value))
        layout.addWidget(table, 1)
        controls = QHBoxLayout()
        defer_btn = QPushButton("Ausgewählte zurückstellen")
        restore_btn = QPushButton("Ausgewählte wieder aktivieren")
        search_btn = QPushButton("Jetzt nach Updates suchen")
        install_btn = QPushButton("Ausgewählte installieren")
        history_btn = QPushButton("Verlauf anzeigen")
        controls.addWidget(defer_btn); controls.addWidget(restore_btn); controls.addWidget(search_btn); controls.addWidget(install_btn); controls.addWidget(history_btn)
        layout.addLayout(controls)
        auto = QCheckBox("Automatisch nach Sicherheitsupdates suchen")
        auto.setChecked(self.settings.value("security/auto_check", False, type=bool))
        interval = QComboBox()
        interval.addItem("Alle 15 Minuten", 15); interval.addItem("Alle 30 Minuten", 30)
        interval.addItem("Stündlich", 60); interval.addItem("Alle 6 Stunden", 360)
        interval.addItem("Täglich", 1440)
        current = self.settings.value("security/check_interval_minutes", 360, type=int)
        ix = interval.findData(current)
        interval.setCurrentIndex(ix if ix >= 0 else 3)
        auto_row = QHBoxLayout(); auto_row.addWidget(auto); auto_row.addWidget(QLabel("Prüfintervall:")); auto_row.addWidget(interval); auto_row.addStretch()
        layout.addLayout(auto_row)
        close = QPushButton("Schließen"); layout.addWidget(close)
        def selected_items():
            return [items[r] for r in range(table.rowCount())
                    if table.item(r,0).checkState() == Qt.Checked]
        def save_auto():
            self.settings.setValue("security/auto_check", auto.isChecked())
            self.settings.setValue("security/check_interval_minutes", interval.currentData())
            self.settings.sync(); self.configure_security_timer()
        auto.toggled.connect(lambda _=None: save_auto()); interval.currentIndexChanged.connect(lambda _=None: save_auto())
        def defer_selected():
            d = self._security_deferred()
            for item in selected_items():
                d[item["package"]] = item["candidate"]
                self._save_security_history("Zurückgestellt", item["package"], item["candidate"], "Gespeichert")
            self.settings.setValue("security/deferred", json.dumps(d, ensure_ascii=False)); self.settings.sync()
            dlg.accept(); self.manage_security_updates()
        def restore_selected():
            d = self._security_deferred()
            for item in selected_items():
                d.pop(item["package"], None)
                self._save_security_history("Wieder aktiviert", item["package"], item["candidate"], "Gespeichert")
            self.settings.setValue("security/deferred", json.dumps(d, ensure_ascii=False)); self.settings.sync()
            dlg.accept(); self.manage_security_updates()
        def install_selected():
            chosen = selected_items()
            if not chosen:
                QMessageBox.information(dlg, "Sicherheitsupdates", "Bitte mindestens ein Update auswählen."); return
            names = [x["package"] for x in chosen]
            preview_rc, preview = cmd(["apt-get", "-s", "--only-upgrade", "install", *names])
            if preview_rc:
                QMessageBox.critical(dlg, "APT-Vorschau fehlgeschlagen", preview); return
            question = "Folgende Sicherheitsupdates werden installiert:\n\n" + "\n".join(names) + "\n\n" + preview[-7000:] + "\n\nFortfahren?"
            if QMessageBox.question(dlg, "Sicherheitsupdates installieren", question) != QMessageBox.Yes: return
            dlg.accept()
            self.run_security_install(chosen)
        def show_history():
            hist = self._security_history()
            hd = QDialog(dlg); hd.setWindowTitle("Sicherheitsupdate-Verlauf"); hd.resize(760,500)
            hl = QVBoxLayout(hd); view = QTableWidget(len(hist),5)
            view.setHorizontalHeaderLabels(["Zeitpunkt","Aktion","Paket","Version","Ergebnis"])
            view.horizontalHeader().setStretchLastSection(True); view.setEditTriggers(QTableWidget.NoEditTriggers)
            for r,entry in enumerate(hist):
                for c,key in enumerate(("time","action","package","version","result")):
                    view.setItem(r,c,QTableWidgetItem(str(entry.get(key,""))))
            hl.addWidget(view); b=QPushButton("Schließen"); b.clicked.connect(hd.accept); hl.addWidget(b); hd.exec()
        defer_btn.clicked.connect(defer_selected); restore_btn.clicked.connect(restore_selected)
        # Dialog schließen und Sicherheitsupdate-Suche erneut im Hintergrund starten.
        search_btn.clicked.connect(lambda: (dlg.accept(), self.manage_security_updates()))
        install_btn.clicked.connect(install_selected); history_btn.clicked.connect(show_history)
        close.clicked.connect(dlg.accept)
        dlg.exec()

    def run_security_install(self, chosen):
        names = [x["package"] for x in chosen]
        progress = ActionProgressDialog(self, "Sicherheitsupdates installieren",
                                        f"{len(names)} ausgewählte Sicherheitsupdates werden installiert.")
        self.set_busy(True)
        args = privileged(["apt-get", "-o", "APT::Status-Fd=2", "-y", "--only-upgrade", "install", *names])
        self.security_install_stream = StreamJob(args)
        self.security_install_stream.output.connect(lambda line: (
            progress.append_output(line),
            (lambda parsed: progress.set_progress(parsed[0], parsed[1]) if parsed[0] is not None else None)(self.apt_status_progress(line))
        ))
        def finished(rc, output):
            progress.finish(rc); self.set_busy(False)
            result = "Erfolgreich" if rc == 0 else f"Fehler (APT {rc})"
            for item in chosen:
                self._save_security_history("Installiert", item["package"], item["candidate"], result)
            if rc == 0:
                deferred = self._security_deferred()
                for item in chosen: deferred.pop(item["package"], None)
                self.settings.setValue("security/deferred", json.dumps(deferred, ensure_ascii=False))
                self.settings.sync()
                self.status.setText("Sicherheitsupdates installiert")
            else:
                self.status.setText("Installation der Sicherheitsupdates fehlgeschlagen")
            self.search_pkgs()
        self.security_install_stream.finished_text.connect(finished)
        self.security_install_stream.start(); progress.exec()

    def _source_files(self):
        files=[]
        for f in ["/etc/apt/sources.list"]:
            if os.path.isfile(f): files.append(f)
        folder="/etc/apt/sources.list.d"
        try:
            files += [os.path.join(folder,x) for x in sorted(os.listdir(folder)) if x.endswith((".list",".sources")) and os.path.isfile(os.path.join(folder,x))]
        except OSError: pass
        return files

    def manage_sources(self):
        files = self._source_files()
        d = QDialog(self); d.setWindowTitle("Paketquellen (Repository-Verwaltung)"); d.resize(1050, 650)
        layout = QVBoxLayout(d)
        layout.addWidget(QLabel("APT-Paketquellen aktivieren, bearbeiten und verwalten."))
        table = QTableWidget(0, 5); table.setHorizontalHeaderLabels(["Aktiviert", "Typ", "Adresse", "Distribution", "Bereiche"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows); table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.horizontalHeader().setStretchLastSection(True); table.setColumnWidth(0, 85); table.setColumnWidth(1, 80)
        layout.addWidget(table, 1)
        source_entries = []
        def load_entries():
            source_entries.clear(); table.setRowCount(0)
            for path in files:
                try: raw = Path(path).read_text(encoding="utf-8", errors="replace")
                except OSError: continue
                if path.endswith(".sources"):
                    for block in re.split(r"\n\s*\n", raw.strip()):
                        if not block.strip(): continue
                        fields = {}
                        for line in block.splitlines():
                            if ":" in line and not line[:1].isspace():
                                k,v=line.split(":",1); fields[k.strip().lower()]=v.strip()
                        uris=fields.get("uris", "").split(); suites=fields.get("suites", "").split()
                        comps=fields.get("components", "").split()
                        types=fields.get("types", "deb").split()
                        for uri in uris:
                            for suite in suites:
                                source_entries.append({"path":path,"format":"sources","block":block,"enabled":fields.get("enabled","yes").lower()!="no","type":" ".join(types),"uri":uri,"suite":suite,"components":" ".join(comps)})
                else:
                    for idx,line in enumerate(raw.splitlines()):
                        stripped=line.strip(); enabled=not stripped.startswith("#")
                        content=stripped[1:].strip() if not enabled else stripped
                        parts=content.split()
                        if len(parts)>=3 and parts[0] in ("deb","deb-src"):
                            source_entries.append({"path":path,"format":"list","line":idx,"original":line,"enabled":enabled,"type":parts[0],"uri":parts[1],"suite":parts[2],"components":" ".join(parts[3:])})
            for entry in source_entries:
                r=table.rowCount(); table.insertRow(r)
                check=QTableWidgetItem(); check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsUserCheckable); check.setCheckState(Qt.Checked if entry["enabled"] else Qt.Unchecked)
                table.setItem(r,0,check)
                for c,key in enumerate(("type","uri","suite","components"),1):
                    item=QTableWidgetItem(entry[key]); item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                    table.setItem(r,c,item)
                table.item(r,0).setData(Qt.UserRole, entry)
        load_entries()
        editor_box=QGroupBox("Ausgewählte Paketquelle bearbeiten"); form=QFormLayout(editor_box)
        typ=QComboBox(); typ.addItems(["deb","deb-src"]); uri=QLineEdit(); suite=QLineEdit(); components=QLineEdit()
        form.addRow("Typ:",typ); form.addRow("Adresse:",uri); form.addRow("Distribution:",suite); form.addRow("Bereiche:",components); layout.addWidget(editor_box)
        def selected_entry():
            r=table.currentRow(); return source_entries[r] if 0<=r<len(source_entries) else None
        def fill_form():
            e=selected_entry()
            if e:
                typ.setCurrentText(e["type"]); uri.setText(e["uri"]); suite.setText(e["suite"]); components.setText(e["components"])
        table.itemSelectionChanged.connect(fill_form)
        def save_all():
            # Jede .list-Zeile wird gezielt ersetzt; nicht bearbeitete Zeilen bleiben erhalten.
            by_file={}
            for e in source_entries:
                if e["format"]=="list":
                    by_file.setdefault(e["path"],{})[e["line"]]=e
            for path, changes in by_file.items():
                lines=Path(path).read_text(encoding="utf-8",errors="replace").splitlines()
                for idx,e in changes.items():
                    if idx>=len(lines): continue
                    prefix="" if e["enabled"] else "# "
                    lines[idx]=prefix+" ".join([e["type"],e["uri"],e["suite"],e["components"]]).rstrip()
                Path(path).write_text("\n".join(lines)+"\n",encoding="utf-8")
            new_entries=[e for e in source_entries if e["format"]=="list" and e["line"]<0]
            for path in {e["path"] for e in new_entries}:
                Path(path).parent.mkdir(parents=True,exist_ok=True)
                with open(path,"a",encoding="utf-8") as f:
                    for e in [x for x in new_entries if x["path"]==path]:
                        f.write(("" if e["enabled"] else "# ")+" ".join([e["type"],e["uri"],e["suite"],e["components"]]).rstrip()+"\n")
            # Deb822-Dateien werden nur geändert, wenn der Status umgeschaltet wurde.
            for path in {e["path"] for e in source_entries if e["format"]=="sources"}:
                raw=Path(path).read_text(encoding="utf-8",errors="replace")
                original=raw
                for e in [x for x in source_entries if x["path"]==path and x["format"]=="sources"]:
                    if e["enabled"]: raw=re.sub(r"(?im)^Enabled:\\s*no\\s*$","Enabled: yes",raw)
                    else:
                        if re.search(r"(?im)^Enabled:",raw): raw=re.sub(r"(?im)^Enabled:.*$","Enabled: no",raw)
                        else: raw=raw.rstrip()+"\nEnabled: no\n"
                if raw!=original: Path(path).write_text(raw,encoding="utf-8")
            QMessageBox.information(d,"Paketquellen","Änderungen gespeichert. Aktualisiere anschließend die Paketlisten.")
            load_entries()
        def apply_form():
            e=selected_entry()
            if not e: return
            e.update(type=typ.currentText(),uri=uri.text().strip(),suite=suite.text().strip(),components=components.text().strip())
            r=table.currentRow()
            for c,val in enumerate((e["type"],e["uri"],e["suite"],e["components"]),1): table.item(r,c).setText(val)
        def toggle(row,col):
            if col==0 and 0<=row<len(source_entries): source_entries[row]["enabled"]=(table.item(row,0).checkState()==Qt.Checked)
        table.itemChanged.connect(toggle)
        def move(delta):
            r=table.currentRow(); target=r+delta
            if not (0<=r<table.rowCount() and 0<=target<table.rowCount()): return
            e=source_entries.pop(r); source_entries.insert(target,e); load_entries(); table.selectRow(target)
        def add_entry():
            e={"path":"/etc/apt/sources.list.d/lunapaket-extra.list","format":"list","line":-1,"original":"","enabled":True,"type":"deb","uri":"https://","suite":"stable","components":"main"}
            if not os.path.exists(e["path"]): files.append(e["path"])
            source_entries.append(e)
            r=table.rowCount(); table.insertRow(r)
            check=QTableWidgetItem(); check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable|Qt.ItemIsUserCheckable); check.setCheckState(Qt.Checked); table.setItem(r,0,check)
            for c,key in enumerate(("type","uri","suite","components"),1): table.setItem(r,c,QTableWidgetItem(e[key]))
            table.selectRow(r)
        def delete_entry():
            e=selected_entry()
            if not e: return
            if e["format"]=="list" and e["line"]>=0:
                lines=Path(e["path"]).read_text(encoding="utf-8",errors="replace").splitlines()
                if e["line"]<len(lines): lines[e["line"]]="# ENTFERNT: "+lines[e["line"]].lstrip("# ")
                Path(e["path"]).write_text("\n".join(lines)+"\n",encoding="utf-8")
            source_entries.remove(e); load_entries()
        actions=QHBoxLayout()
        for label,fn in (("Hoch",lambda:move(-1)),("Runter",lambda:move(1)),("Neu",add_entry),("Löschen",delete_entry),("Übernehmen",apply_form)):
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        actions.addStretch(1); layout.addLayout(actions)
        buttons=QDialogButtonBox(); save=buttons.addButton("OK",QDialogButtonBox.AcceptRole); cancel=buttons.addButton("Abbrechen",QDialogButtonBox.RejectRole)
        save.clicked.connect(lambda:(apply_form(),save_all(),d.accept())); cancel.clicked.connect(d.reject); layout.addWidget(buttons)
        d.exec()

    def check_sources(self):
        progress=ActionProgressDialog(self,"Paketquellen prüfen","APT prüft alle konfigurierten Paketquellen und meldet fehlerhafte oder nicht erreichbare Repositories.")
        job=StreamJob(privileged(["apt-get","update"]))
        job.output.connect(progress.append_output)
        result={"code":1}
        def done(rc,out):
            result["code"]=rc; progress.finish(rc)
        job.finished_text.connect(done)
        job.start(); progress.exec()
        if job.isRunning(): job.wait()
        if result["code"] == 0: QMessageBox.information(self,"Paketquellen","Die Paketlisten wurden erfolgreich aktualisiert.")
        else: QMessageBox.warning(self,"Paketquellen","Mindestens eine Paketquelle konnte nicht fehlerfrei aktualisiert werden. Details stehen im Prüfprotokoll.")

    def install_local_deb(self, paths=None):
        if paths is None:
            paths,_=QFileDialog.getOpenFileNames(self,"Lokale DEB-Dateien auswählen","","Debian-Pakete (*.deb)")
        else:
            paths=[os.path.abspath(x) for x in paths if x.lower().endswith(".deb") and os.path.isfile(x)]
        if not paths: return

        details=[]
        reinstall_paths=[]
        normal_paths=[]
        for path in paths:
            rc,out=cmd(["dpkg-deb","-f",path,"Package","Version","Architecture","Description"])
            if rc != 0:
                QMessageBox.warning(self,"Ungültiges DEB-Paket",f"{os.path.basename(path)} konnte nicht gelesen werden.\\n\\n{out}")
                continue
            fields={}
            current_key=None
            for line in out.splitlines():
                if line and not line[0].isspace() and ":" in line:
                    current_key,value=line.split(":",1); fields[current_key.strip()]=value.strip()
                elif current_key == "Description" and line:
                    fields[current_key] += "\\n" + line
            package=fields.get("Package","").strip()
            version=fields.get("Version","").strip()
            if not package:
                QMessageBox.warning(self,"Ungültiges DEB-Paket",f"Im Paket {os.path.basename(path)} fehlt der Paketname.")
                continue
            qrc,qout=cmd(["dpkg-query","-W","-f=${db:Status-Status}\\t${Version}",package])
            installed=False
            installed_version=""
            if qrc == 0:
                parts=qout.strip().split("\t",1)
                installed=bool(parts and parts[0] == "installed")
                installed_version=parts[1] if len(parts)>1 else ""
            details.append(f"{os.path.basename(path)}\\n{out.strip()}"+
                           (f"\\nInstalliert: {installed_version}" if installed else "\\nStatus: derzeit nicht installiert"))
            if installed and installed_version == version:
                reinstall_paths.append(path)
            else:
                normal_paths.append(path)

        if not normal_paths and not reinstall_paths:
            return

        if not normal_paths and not reinstall_paths:
            return

        # Eigenes Fenster für eine per "Öffnen mit" übergebene DEB-Datei.
        dialog=QDialog(self)
        dialog.setWindowTitle("Lokales Debian-Paket")
        dialog.resize(680,420)
        layout=QVBoxLayout(dialog)
        heading=QLabel("Ausgewählte Debian-Pakete")
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(heading)
        info=QLabel("Prüfe Paketstatus und Version. Wähle anschließend die gewünschte Aktion.")
        info.setWordWrap(True)
        layout.addWidget(info)
        table=QTableWidget(len(details),4)
        table.setHorizontalHeaderLabels(["Datei / Paket","Version","Installierter Status","Aktion"])
        table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents)
        for row,path in enumerate(paths):
            if row >= len(details): break
            rc,out=cmd(["dpkg-deb","-f",path,"Package","Version"])
            fields={}
            for line in out.splitlines():
                if ":" in line:
                    k,v=line.split(":",1); fields[k.strip()]=v.strip()
            package=fields.get("Package","")
            version=fields.get("Version","")
            qrc,qout=cmd(["dpkg-query","-W","-f=${db:Status-Status}\\t${Version}",package]) if package else (1,"")
            parts=qout.strip().split("\t",1)
            installed=bool(qrc==0 and parts and parts[0]=="installed")
            installed_version=parts[1] if len(parts)>1 else ""
            values=[os.path.basename(path),version,
                    (f"Installiert: {installed_version}" if installed else "Nicht installiert"),
                    ("Erneut installieren" if installed else "Installieren")]
            for col,value in enumerate(values):
                table.setItem(row,col,QTableWidgetItem(value))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(table,1)
        buttons=QDialogButtonBox()
        install_btn=buttons.addButton("Installieren / aktualisieren",QDialogButtonBox.AcceptRole)
        reinstall_btn=buttons.addButton("Erneut installieren",QDialogButtonBox.ActionRole)
        cancel_btn=buttons.addButton("Abbrechen",QDialogButtonBox.RejectRole)
        reinstall_btn.setEnabled(bool(reinstall_paths))
        install_btn.clicked.connect(dialog.accept)
        reinstall_btn.clicked.connect(lambda: (dialog.setProperty("force_reinstall",True),dialog.accept()))
        cancel_btn.clicked.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted:
            return
        reinstall=bool(dialog.property("force_reinstall"))
        if reinstall:
            normal_paths=list(paths)
        else:
            normal_paths=list(normal_paths)
        if not normal_paths:
            QMessageBox.information(self,"Keine Installation","Es gibt keine neuen oder aktualisierbaren Pakete. Für eine Neuinstallation bitte „Erneut installieren“ wählen.")
            return

        apt_args=["apt-get","install","-y"]
        if reinstall:
            apt_args.append("--reinstall")
        args=privileged([*apt_args,*normal_paths])
        self.run_action_job(args,"Lokale DEB installieren","Lokale Debian-Pakete werden installiert; bereits installierte Pakete werden bei Auswahl mit APT --reinstall erneut installiert.")

    def show_dependency_analysis(self):
        name=self.selected()
        if not name:
            name,ok=QInputDialog.getText(self,"Abhängigkeitsanalyse","Paketname:")
            if not ok or not name.strip(): return
            name=name.strip()
        sections=[]
        for title,args in [("Benötigte Abhängigkeiten",["apt-cache","depends",name]),("Rückwärtsabhängigkeiten (Pakete, die dieses Paket benötigen)",["apt-cache","rdepends",name]),("Konflikte / Ersetzungen",["apt-cache","show",name])]:
            rc,out=cmd(args)
            if title.startswith("Konflikte"):
                fields=[]
                for line in out.splitlines():
                    if line.startswith(("Conflicts:","Breaks:","Replaces:","Depends:","Pre-Depends:")): fields.append(line)
                out="\n".join(fields) or "Keine entsprechenden Konflikt-/Abhängigkeitsfelder in den Paketmetadaten gefunden."
            sections.append(title+"\n"+"="*len(title)+"\n"+(out.strip() or "Keine Angaben verfügbar."))
        d=QDialog(self); d.setWindowTitle("Abhängigkeitsanalyse – "+name); d.resize(850,600)
        lay=QVBoxLayout(d); t=QPlainTextEdit(); t.setReadOnly(True); t.setPlainText("\n\n".join(sections)); lay.addWidget(t)
        note=QLabel("Hinweis: Die endgültige Konflikt- und Entfernungsprüfung erfolgt zusätzlich durch APT-Simulation vor jeder Paketänderung."); note.setWordWrap(True); lay.addWidget(note)
        b=QDialogButtonBox(QDialogButtonBox.Close); b.rejected.connect(d.reject); b.accepted.connect(d.accept); lay.addWidget(b); d.exec()

    def sources(self):
        files=["/etc/apt/sources.list"]
        try: files += ["/etc/apt/sources.list.d/"+x for x in os.listdir("/etc/apt/sources.list.d") if x.endswith((".list",".sources"))]
        except OSError: pass
        text=""
        for f in files:
            try:text+=f"### {f}\n"+open(f,encoding="utf-8",errors="replace").read()+"\n"
            except OSError:pass
        d=QDialog(self); d.setWindowTitle("Paketquellen"); d.resize(800,500); lay=QVBoxLayout(d); t=QTextEdit(); t.setReadOnly(True); t.setPlainText(text or "Keine Paketquellen gefunden."); lay.addWidget(t); b=QDialogButtonBox(QDialogButtonBox.Close); b.rejected.connect(d.reject); lay.addWidget(b); d.exec()
def main():
    relaunch_as_root()
    app=QApplication(sys.argv)
    app.setApplicationName("LunaPaket")
    win=Window(); win.show()
    # Aufruf über Dateimanager: --open-deb [datei.deb].
    # Manche Dateimanager übergeben lokale Dateien als file://-URI.
    deb_paths=[]
    for arg in sys.argv[1:]:
        if arg == "--open-deb":
            continue
        candidate = arg
        if candidate.startswith("file://"):
            from urllib.parse import unquote, urlparse
            candidate = unquote(urlparse(candidate).path)
        if candidate.lower().endswith(".deb") and os.path.isfile(candidate):
            deb_paths.append(os.path.abspath(candidate))
    # Nur bei einem tatsächlich übergebenen DEB-Dateipfad das Paketfenster öffnen.
    # Beim normalen Start aus dem Startmenü bleibt die Paketübersicht ohne Dateiauswahl.
    if deb_paths:
        QTimer.singleShot(500, lambda paths=deb_paths: win.install_local_deb(paths))
    return app.exec()
if __name__=="__main__": raise SystemExit(main())
