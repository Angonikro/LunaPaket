#!/usr/bin/python3
import os, sys, subprocess, re, pwd, json, shlex, shutil, html, gzip, hashlib, time, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QThread, Signal, QSettings, QTimer, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QAction, QIcon, QPixmap, QImage
from PySide6.QtWidgets import *
from shiboken6 import isValid
VERSION="0.1.41"

# Thematische Filter auf dem bereits geladenen Paketbestand.
# Die Muster durchsuchen Paketname und Kurzbeschreibung; ein Paket kann
# dadurch in mehreren Bereichen erscheinen.
TOPIC_CATEGORIES = [
    ("amateurfunk", "Amateurfunk", "Amateur Radio", r"\b(hamradio|amateur.?radio|radio.?signal|gnuradio|gqrx|rtl.?sdr|soapysdr|direwolf|fldigi|chirp|qsstv|wsjtx|js8call|hamlib|ax25|aprs|cqrlog|xastir|qtel|sdrangel)\b"),
    ("network", "Internet & Netzwerk", "Internet & Network", r"\b(network|netzwerk|browser|firefox|chromium|curl|wget|ssh|openssh|ftp|sftp|wifi|wireless|wireshark|tcpdump|nmap| traceroute|dns|vpn)\b"),
    ("audio", "Audio & Musik", "Audio & Music", r"\b(audio|musik|music|sound|alsa|pulseaudio|pipewire|vlc|audacity|ardour|lmms|mpd|mplayer|rhythmbox|strawberry|lame|flac|vorbis)\b"),
    ("video", "Video & Multimedia", "Video & Multimedia", r"\b(video|multimedia|ffmpeg|ffplay|handbrake|makemkv|mkvtoolnix|kdenlive|shotcut|obs-studio|mpv|totem|dvd|bluray|gstreamer)\b"),
    ("graphics", "Grafik & Design", "Graphics & Design", r"\b(graphics|grafik|image|bildbearbeitung|gimp|inkscape|krita|blender|darktable|scribus|imagemagick|inkscape|freecad|openscad|cad)\b"),
    ("programming", "Programmierung", "Programming", r"\b(programming|programmierung|compiler|debugger|python|python3|gcc|g\+\+|clang|cmake|git|geany|kate|vim|emacs|code editor|ide|qtcreator| Lazarus|rustc|nodejs|golang)\b"),
    ("system", "System & Verwaltung", "System & Administration", r"\b(system|administration|verwaltung|systemd|gnome-system|partition|disk|laufwerk|backup|monitor|htop|lshw|hardinfo|gparted|timeshift|grub|udev|aptitude)\b"),
    ("security", "Sicherheit", "Security", r"\b(security|sicherheit|firewall|ufw|gufw|clamav|antivirus|crypt|verschlüssel|gnupg|gpg|keepass|fail2ban|apparmor|selinux|rkhunter|chkrootkit)\b"),
    ("electronics", "Elektronik & Hardware", "Electronics & Hardware", r"\b(electronics|elektronik|hardware|arduino|raspberry|raspi|esp32|esp-idf|platformio|avrdude|openocd|esptool|kicad|electronics|microcontroller|mikrocontroller|i2c|spi|serial)\b"),
    ("office", "Büro & Bildung", "Office & Education", r"\b(office|büro|bildung|education|libreoffice|openoffice|pdf|okular|evince|texlive|latex|dictionary|wörterbuch|learning|lernprogramm|stellarium|kalzium)\b"),
    ("games", "Spiele", "Games", r"\b(game|games|spiel|spiele|steam|lutris|dosbox|retroarch|scummvm|minecraft|supertux|xonotic|emulator)\b"),
    ("science", "Wissenschaft & Navigation", "Science & Navigation", r"\b(science|wissenschaft|navigation|gps|gpsd|qgis|map|karte|kartographie|stellarium|celestia|gnuplot|octave|scipy|r-?base|geography|astronomy|astronomie)\b"),
]
TOPIC_REGEX = {key: re.compile(pattern, re.IGNORECASE) for key, _de, _en, pattern in TOPIC_CATEGORIES}


class PackageTableModel(QAbstractTableModel):
    """Modellbasierte Paketliste ohne tausende QTableWidgetItems."""
    HEADERS = ("", "Paket", "Version", "Status", "Beschreibung")
    def __init__(self, parent=None):
        super().__init__(parent); self.rows=[]; self.checked=[]; self.installed=[]; self.visible_rows=[]; self.search_texts=[]
    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.visible_rows)
    def columnCount(self, parent=QModelIndex()): return 0 if parent.isValid() else 5
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and 0 <= section < 5:
            headers = self.HEADERS
            if getattr(self, "language", "de") == "en":
                headers = ("", "Package", "Version", "Status", "Description")
            return headers[section]
        return None
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows): return None
        r,c=index.row(),index.column()
        if r >= len(self.visible_rows): return None
        source_row = self.visible_rows[r]
        if c == 0:
            if role == Qt.CheckStateRole: return Qt.Checked if self.checked[source_row] else Qt.Unchecked
            if role == Qt.UserRole: return self.rows[source_row][0]
            if role == Qt.UserRole+1: return self.installed[source_row]
            return None
        if role == Qt.DecorationRole and c == 1 and len(self.rows[source_row]) > 5:
            icon_path = self.rows[source_row][5]
            if icon_path and os.path.isfile(icon_path):
                return QIcon(icon_path)
            return QIcon.fromTheme("application-x-executable")
        if role == Qt.DisplayRole:
            if c == 1 and len(self.rows[source_row]) > 6:
                value = str(self.rows[source_row][6] or self.rows[source_row][0])
            else:
                value = str(self.rows[source_row][c-1] if c-1 < len(self.rows[source_row]) else "")
            if getattr(self, "language", "de") == "en" and c == 3:
                value = {"Nicht installiert": "Not installed", "Installiert": "Installed"}.get(value, value)
            return value
        if role == Qt.UserRole: return self.rows[source_row][0]
        return None
    def flags(self,index):
        if not index.isValid(): return Qt.NoItemFlags
        f=Qt.ItemIsEnabled|Qt.ItemIsSelectable
        return f|Qt.ItemIsUserCheckable if index.column()==0 else f
    def setData(self,index,value,role=Qt.EditRole):
        if not index.isValid() or index.column()!=0 or role!=Qt.CheckStateRole: return False
        r=index.row()
        if r >= len(self.visible_rows): return False
        source_row = self.visible_rows[r]
        v=(value==Qt.Checked or value is True)
        if self.checked[source_row] != v:
            self.checked[source_row]=v; self.dataChanged.emit(index,index,[Qt.CheckStateRole])
        return True
    def replace_rows(self, rows, queue):
        self.beginResetModel(); self.rows=list(rows)
        self.visible_rows=list(range(len(self.rows)))
        self.search_texts=[" ".join(str(v) for v in x).casefold() for x in self.rows]
        self.installed=[len(x)>2 and str(x[2])=="Installiert" for x in self.rows]
        self.checked=[]
        for x,inst in zip(self.rows,self.installed):
            a=queue.get(x[0],""); v=inst
            if a in ("install","reinstall") or a.startswith("version:"): v=True
            elif a in ("remove","purge"): v=False
            self.checked.append(v)
        self.endResetModel()
    def set_checked_for_name(self,name,checked):
        for source_row,x in enumerate(self.rows):
            if x and x[0]==name:
                value=bool(checked)
                if self.checked[source_row] != value:
                    self.checked[source_row]=value
                    try: visible_row=self.visible_rows.index(source_row)
                    except ValueError: return source_row
                    idx=self.index(visible_row,0); self.dataChanged.emit(idx,idx,[Qt.CheckStateRole])
                return source_row
        return -1
    def apply_filter(self, category, term, autoremove, queue):
        term=(term or "").casefold()
        auto=autoremove or set()
        selected=[]
        for source_row,row in enumerate(self.rows):
            name=row[0] if row else ""
            installed=self.installed[source_row]
            if category==1 and not installed: continue
            if category==2 and installed: continue
            if category==3 and name.split(":",1)[0] not in auto: continue
            if category==4 and not queue.get(name): continue
            if category >= 6:
                topic_index = category - 6
                if topic_index >= len(TOPIC_CATEGORIES): continue
                topic_key = TOPIC_CATEGORIES[topic_index][0]
                searchable = self.search_texts[source_row]
                # Debian verwendet "games" bzw. "games/..." als Section.
                # Die Regel gilt automatisch für alle Pakete dieser Sektion.
                section = str(row[4] if len(row) > 4 else "").casefold()
                is_game_section = section == "games" or section.startswith("games/")
                if topic_key == "games":
                    if not is_game_section and not TOPIC_REGEX[topic_key].search(searchable):
                        continue
                elif not TOPIC_REGEX[topic_key].search(searchable):
                    continue
            if term and term not in self.search_texts[source_row]: continue
            selected.append(source_row)
        if selected == self.visible_rows: return len(selected)
        self.beginResetModel(); self.visible_rows=selected; self.endResetModel()
        return len(selected)

class _PackageItemProxy:
    def __init__(self,view,row,col): self.view,self._row,self._column=view,row,col
    def row(self): return self._row
    def column(self): return self._column
    def data(self,role): return self.view.package_model.data(self.view.package_model.index(self._row,self._column),role)
    def text(self): return str(self.view.package_model.data(self.view.package_model.index(self._row,self._column),Qt.DisplayRole) or "")
    def checkState(self): return self.view.package_model.data(self.view.package_model.index(self._row,self._column),Qt.CheckStateRole)
    def setCheckState(self,state): self.view.package_model.setData(self.view.package_model.index(self._row,self._column),state,Qt.CheckStateRole)

class PackageTableView(QTableView):
    itemChanged=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent); self.package_model=PackageTableModel(self); self.setModel(self.package_model)
        self.package_model.dataChanged.connect(self._changed); self.setSelectionBehavior(QAbstractItemView.SelectRows); self.setEditTriggers(QAbstractItemView.AllEditTriggers)
    def mousePressEvent(self, event):
        # Die Check-Spalte wird explizit per einfachem Linksklick umgeschaltet.
        # Damit hängt die Bedienung nicht vom Edit-Trigger des QTableView-Delegates ab.
        if event.button() == Qt.LeftButton:
            index = self.indexAt(event.position().toPoint())
            if index.isValid() and index.column() == 0:
                self.setCurrentIndex(index)
                self.selectRow(index.row())
                current = self.package_model.data(index, Qt.CheckStateRole)
                target = Qt.Unchecked if current == Qt.Checked else Qt.Checked
                self.package_model.setData(index, target, Qt.CheckStateRole)
                event.accept()
                return
        super().mousePressEvent(event)
    def _changed(self,a,b,roles):
        if a.column()==0 and (not roles or Qt.CheckStateRole in roles): self.itemChanged.emit(_PackageItemProxy(self,a.row(),0))
    def setHorizontalHeaderLabels(self,labels): self.package_model.HEADERS=tuple(labels)
    def rowCount(self): return self.package_model.rowCount()
    def columnCount(self): return self.package_model.columnCount()
    def item(self,r,c): return _PackageItemProxy(self,r,c) if 0<=r<self.rowCount() and 0<=c<5 else None
    def selectedItems(self):
        i=self.currentIndex(); return [_PackageItemProxy(self,i.row(),i.column())] if i.isValid() else []
    def currentColumn(self): return self.currentIndex().column()
    def sortItems(self,*args): pass
    def setSortingEnabled(self,*args): pass

def privileged(args):
    """Führt Systembefehle direkt aus, wenn LunaPaket als root läuft."""
    return list(args) if os.geteuid() == 0 else ["pkexec", *args]


def is_apt_command(args):
    """Erkennt direkte APT-Aufrufe sowie APT-Befehle innerhalb einer Shell-Kette."""
    values = [str(value) for value in args]
    for value in values:
        if os.path.basename(value) == "apt":
            return True
    # Vorgemerkte Änderungen werden als "sh -c 'apt ... && apt ...'" gestartet.
    # In diesem Fall steht apt nicht als eigenes argv-Element zur Verfügung.
    joined = " ".join(values)
    return bool(re.search(r"""(?<![A-Za-z0-9_./+-])(?:'apt'|"apt"|apt)(?=[\s'"])""", joined))

def log_apt_problem(args, returncode, output):
    """Schreibt ausschließlich fehlgeschlagene APT-Aufrufe in ein begrenztes Benutzer-Log."""
    try:
        from datetime import datetime
        uid = int(os.environ.get("PKEXEC_UID", os.environ.get("SUDO_UID", os.getuid())))
        account = pwd.getpwuid(uid)
        home = Path(account.pw_dir)
        log_dir = home / ".local" / "share" / "LunaPaket" / "logs"
        # LunaPaket kann für die Installation als root laufen. Das Protokoll
        # bleibt trotzdem im Besitz des angemeldeten Desktop-Benutzers.
        for directory in (home / ".local", home / ".local" / "share",
                          home / ".local" / "share" / "LunaPaket", log_dir):
            directory.mkdir(parents=True, exist_ok=True)
            if os.geteuid() == 0:
                os.chown(directory, account.pw_uid, account.pw_gid)
        os.chmod(log_dir, 0o700)
        log_file = log_dir / "apt-errors.log"
        backup_file = log_dir / "apt-errors.log.1"
        max_bytes = 512 * 1024
        command = shlex.join([str(x) for x in args])
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        details = str(output or "(Keine Programmausgabe vorhanden.)")
        # Ein einzelner Fehler darf die Größenbegrenzung nicht umgehen.
        details = details[-(max_bytes - 4096):]
        entry = (
            f"\n{'=' * 72}\n"
            f"Zeit: {timestamp}\n"
            f"Befehl: {command}\n"
            f"Exit-Code: {returncode}\n"
            f"Ausgabe:\n{details.rstrip()}\n"
        ).encode("utf-8", errors="replace")
        if log_file.exists() and log_file.stat().st_size + len(entry) > max_bytes:
            if backup_file.exists():
                backup_file.unlink()
            os.replace(log_file, backup_file)
        with log_file.open("ab") as stream:
            stream.write(entry)
        if os.geteuid() == 0:
            os.chown(log_file, account.pw_uid, account.pw_gid)
            if backup_file.exists():
                os.chown(backup_file, account.pw_uid, account.pw_gid)
        os.chmod(log_file, 0o600)
        if backup_file.exists():
            os.chmod(backup_file, 0o600)
    except Exception:
        # Das Logging darf den eigentlichen APT-Fehler nicht verdecken.
        pass

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
    try:
        timeout = 90 if len(args) > 1 and args[0] == "flatpak" and args[1] in ("remote-ls", "remotes", "list") else 1800
        p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    except Exception as exc:
        if is_apt_command(args):
            log_apt_problem(args, 1, str(exc))
        raise
    if p.returncode != 0 and is_apt_command(args):
        log_apt_problem(args, p.returncode, p.stdout)
    return p.returncode,p.stdout

def flatpak_user_cmd(args):
    """Führt einen Flatpak-Befehl im echten Desktop-Benutzerkonto aus.

    LunaPaket läuft für APT mit pkexec als root. Ein einfaches `flatpak --user`
    würde deshalb /root/.local/share/flatpak verwenden. PKEXEC_UID/SUDO_UID
    identifiziert den angemeldeten Benutzer; runuser wechselt vor dem Flatpak-
    Aufruf zu diesem Konto und setzt dessen Home-/XDG-Pfade explizit.
    """
    uid = int(os.environ.get("PKEXEC_UID", os.environ.get("SUDO_UID", os.getuid())))
    account = pwd.getpwuid(uid)
    if os.geteuid() != 0 or uid == os.getuid():
        return cmd(args)
    runuser = shutil.which("runuser")
    if not runuser:
        return 127, "runuser is required to access the desktop user's Flatpak installation."
    user_env = [
        f"HOME={account.pw_dir}",
        f"USER={account.pw_name}",
        f"LOGNAME={account.pw_name}",
        f"XDG_CONFIG_HOME={Path(account.pw_dir) / '.config'}",
        f"XDG_DATA_HOME={Path(account.pw_dir) / '.local' / 'share'}",
    ]
    command = [runuser, "-u", account.pw_name, "--", "env", *user_env, *[str(x) for x in args]]
    try:
        timeout = 90 if len(args) > 1 and args[0] in ("flatpak",) and args[1] in ("remote-ls", "remotes", "list") else 1800
        p = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout
    except Exception as exc:
        return 1, str(exc)
class Job(QThread):
    finished_text=Signal(int,str)
    def __init__(self,args): super().__init__(); self.args=args
    def run(self):
        try: r,o=cmd(self.args)
        except Exception as e: r,o=1,str(e)
        self.finished_text.emit(r,o)



def dpkg_log_snapshot():
    """Merkt die aktuelle Position im DPKG-Protokoll vor einer Paketaktion."""
    try:
        path = Path("/var/log/dpkg.log")
        return path.stat().st_size if path.exists() else 0
    except OSError:
        return 0


def dpkg_changes_since(offset):
    """Liest tatsächliche install/upgrade/remove/purge-Ereignisse aus dpkg.log."""
    changes = []
    try:
        path = Path("/var/log/dpkg.log")
        if not path.exists():
            return changes
        size = path.stat().st_size
        if size < offset:  # dpkg.log wurde während der Aktion rotiert/neu angelegt
            offset = 0
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            stream.seek(offset)
            for line in stream:
                match = re.match(
                    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) "
                    r"(install|upgrade|remove|purge) (\S+) (\S+) (\S+)",
                    line.strip()
                )
                if not match:
                    continue
                timestamp, operation, package, old_version, new_version = match.groups()
                if operation == "install":
                    label = "Erneut installiert" if old_version != "<none>" else "Installiert"
                    version = new_version
                elif operation == "upgrade":
                    label, version = "Aktualisiert", f"{old_version} -> {new_version}"
                elif operation == "remove":
                    label, version = "Entfernt", old_version
                else:
                    label, version = "Vollständig entfernt", old_version
                changes.append((label, package, version, timestamp))
    except OSError:
        pass
    return changes

def package_snapshot():
    """Ermittelt die aktuell installierten Pakete samt Version."""
    try:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${binary:Package}\\t${Version}\\t${db:Status-Status}\n"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120
        )
        if result.returncode != 0:
            return None
        packages = {}
        for line in result.stdout.splitlines():
            fields = line.split("\t")
            if len(fields) >= 3 and fields[2] == "installed":
                packages[fields[0]] = fields[1]
        return packages
    except Exception:
        return None


def write_package_history(args, before, after, returncode, dpkg_changes=None):
    """Schreibt Paketänderungen in einen auf 1 MiB begrenzten Verlauf."""
    changes = []
    if dpkg_changes:
        changes.extend((action, name, version) for action, name, version, _timestamp in dpkg_changes)
    logged_names = {name for _action, name, _version in changes}
    if before is not None and after is not None:
        for name in sorted(set(before) | set(after)):
            old_version, new_version = before.get(name), after.get(name)
            if name not in logged_names:
                if old_version is None and new_version is not None:
                    changes.append(("Installiert", name, new_version))
                elif old_version is not None and new_version is None:
                    changes.append(("Entfernt", name, old_version))
                elif old_version != new_version:
                    changes.append(("Aktualisiert", name, f"{old_version} -> {new_version}"))
    # Bei einer echten Neuinstallation derselben Version bleibt der dpkg-
    # Versionsbestand unverändert. Diese Aktion muss trotzdem im Verlauf stehen.
    args_list = [str(value) for value in args]
    if "--reinstall" in args_list:
        already_listed = {name for _action, name, _version in changes}
        for value in args_list:
            if value.lower().endswith(".deb") and Path(value).is_file():
                try:
                    result = subprocess.run(
                        ["dpkg-deb", "-f", value, "Package", "Version"],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30
                    )
                    fields = {}
                    for line in result.stdout.splitlines():
                        if ":" in line:
                            key, val = line.split(":", 1)
                            fields[key.strip()] = val.strip()
                    name = fields.get("Package", "")
                    version = fields.get("Version", "")
                    if name and name not in already_listed:
                        changes.append(("Erneut installiert", name, version or after.get(name, "unbekannt")))
                        already_listed.add(name)
                except Exception:
                    pass
            elif value and not value.startswith("-") and value not in ("apt", "install"):
                # Paketname bei apt install --reinstall paketname.
                name = value.split("=", 1)[0].split(":", 1)[0]
                if name in before and name in after and name not in already_listed:
                    changes.append(("Erneut installiert", name, after[name]))
                    already_listed.add(name)
    if not changes:
        return
    try:
        from datetime import datetime
        uid = int(os.environ.get("PKEXEC_UID", os.environ.get("SUDO_UID", os.getuid())))
        account = pwd.getpwuid(uid)
        home = Path(account.pw_dir)
        log_dir = home / ".local" / "share" / "LunaPaket" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(log_dir, account.pw_uid, account.pw_gid)
        os.chmod(log_dir, 0o700)
        history_file = log_dir / "package-history.log"
        max_bytes = 1024 * 1024
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        command = shlex.join([str(x) for x in args])
        result_text = "Erfolgreich" if returncode == 0 else f"Fehler (Exit-Code {returncode})"
        lines = ["", "=" * 72, f"Zeit: {timestamp}", f"Befehl: {command}",
                 f"Ergebnis: {result_text}", "Paketänderungen:"]
        lines.extend(f"  {action}: {name} ({version})" for action, name, version in changes)
        entry = ("\n".join(lines) + "\n").encode("utf-8", errors="replace")
        if len(entry) > max_bytes:
            entry = entry[-max_bytes:]
        existing = history_file.read_bytes() if history_file.exists() else b""
        combined = existing + entry
        if len(combined) > max_bytes:
            combined = combined[-max_bytes:]
            first_newline = combined.find(b"\n")
            if first_newline >= 0:
                combined = combined[first_newline + 1:]
        history_file.write_bytes(combined)
        if os.geteuid() == 0:
            os.chown(history_file, account.pw_uid, account.pw_gid)
        os.chmod(history_file, 0o600)
    except Exception:
        # Der Verlauf darf die Paketverwaltung niemals blockieren.
        pass


def read_package_history():
    """Liest den Paketverlauf des angemeldeten Desktop-Benutzers."""
    try:
        uid = int(os.environ.get("PKEXEC_UID", os.environ.get("SUDO_UID", os.getuid())))
        home = Path(pwd.getpwuid(uid).pw_dir)
        path = home / ".local" / "share" / "LunaPaket" / "logs" / "package-history.log"
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

class StreamJob(QThread):
    output = Signal(str)
    finished_text = Signal(int, str)
    def __init__(self, args):
        super().__init__(); self.args = args
    def run(self):
        chunks = []
        tracks_packages = is_apt_command(self.args)
        before = package_snapshot() if tracks_packages else None
        dpkg_offset = dpkg_log_snapshot() if tracks_packages else 0
        try:
            proc = subprocess.Popen(self.args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, universal_newlines=True,
                                    env={**os.environ, "LC_ALL": "C", "LANG": "C"})
            for line in iter(proc.stdout.readline, ''):
                chunks.append(line); self.output.emit(line.rstrip())
            proc.stdout.close(); rc = proc.wait()
            output = ''.join(chunks)
            if tracks_packages:
                dpkg_changes = dpkg_changes_since(dpkg_offset)
                write_package_history(self.args, before, package_snapshot(), rc, dpkg_changes)
            if rc != 0 and tracks_packages:
                log_apt_problem(self.args, rc, output)
            self.finished_text.emit(rc, output)
        except Exception as exc:
            if tracks_packages:
                dpkg_changes = dpkg_changes_since(dpkg_offset)
                write_package_history(self.args, before, package_snapshot(), 1, dpkg_changes)
                log_apt_problem(self.args, 1, str(exc))
            self.finished_text.emit(1, str(exc))

class FunctionJob(QThread):
    # A central strong-reference set prevents Python from collecting a QThread
    # when a view is switched quickly and its per-view job list is reset.
    _live_jobs = set()
    result=Signal(object)
    failed=Signal(str)
    progress=Signal(int, int)
    def __init__(self, fn, with_progress=False):
        super().__init__()
        self.fn=fn
        self.with_progress=with_progress
        self._live_jobs.add(self)
        self.finished.connect(lambda job=self: self._live_jobs.discard(job))
    def run(self):
        try:
            result = self.fn(self.progress.emit) if self.with_progress else self.fn()
            self.result.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

class ActionProgressDialog(QDialog):
    """Separates live action output from the normal protocol/details pane."""
    def __init__(self, parent, title, description, english=False):
        super().__init__(parent)
        self.english = english
        if english:
            title = {"Paketaktionen": "Package actions", "Paketaktionen bestätigen": "Confirm package actions"}.get(title, title)
            description = {"1 ausgewählte Paketaktion(en) werden ausgeführt.": "1 selected package action(s) are being executed."}.get(description, description)
        self.setWindowTitle(title)
        self.resize(800, 520)
        self.setWindowModality(Qt.WindowModal)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(description))
        self.current = QLabel("Starting operation …" if english else "Vorgang wird gestartet …")
        layout.addWidget(self.current)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p %")
        layout.addWidget(self.progress)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)
        self.auto_close = QCheckBox("Close window after successful action" if english else "Fenster nach erfolgreicher Aktion schließen")
        self.auto_close.setChecked(True)
        layout.addWidget(self.auto_close)
        self.close_button = QPushButton("Operation in progress …" if english else "Vorgang läuft …")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)

    def append_output(self, line):
        if line:
            # APT may inherit the desktop locale through pkexec despite the
            # worker locale. Keep the original command output, but present the
            # standard APT progress prefixes in English in the English UI.
            if self.english:
                replacements = (
                    ("Holen:", "Get:"), ("Ign:", "Ign:"), ("Treffer:", "Hit:"), ("Fehl:", "Err:"),
                    ("Paketlisten werden gelesen", "Reading package lists"),
                    ("Abhängigkeitsbaum wird aufgebaut", "Building dependency tree"),
                    ("Statusinformationen werden eingelesen", "Reading state information"),
                    ("Entpacken von ", "Unpacking "), ("Entpacke ", "Unpacking "),
                    ("Vorbereitung zum Entpacken von ", "Preparing to unpack "),
                    ("Einrichten von ", "Setting up "), ("Richte ein ", "Setting up "),
                    ("Verarbeite Trigger für ", "Processing triggers for "),
                    ("Trigger werden verarbeitet für ", "Processing triggers for "),
                    ("Wird verarbeitet: ", "Processing: "),
                    ("Paket wird verarbeitet", "Processing package"),
                    ("Pakete werden heruntergeladen", "Downloading packages"),
                )
                for old, new in replacements:
                    line = line.replace(old, new)
            self.output.append(line)

    def set_progress(self, percent, message):
        if percent is not None:
            self.progress.setValue(max(0, min(100, int(percent))))
        if message:
            self.current.setText(("Current: " if self.english else "Aktuell: ") + message)

    def finish(self, code):
        if code == 0:
            self.progress.setValue(100)
            self.current.setText("Action completed successfully." if self.english else "Aktion erfolgreich abgeschlossen.")
            self.close_button.setText("Close" if self.english else "Schließen")
        else:
            self.current.setText((f"Action failed (error code {code})." if self.english else f"Aktion fehlgeschlagen (Fehlercode {code})."))
            self.close_button.setText("Close" if self.english else "Schließen")
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
        self._table_mode = None
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
        self.font_size = int(self.settings.value("font_size", 11))
        app_font = QApplication.font(); app_font.setPointSize(self.font_size); QApplication.setFont(app_font)
        self.apply_theme()
        w=QWidget(); self.setCentralWidget(w); outer=QHBoxLayout(w)
        main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter = main_splitter
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setHandleWidth(7)
        outer.addWidget(main_splitter)
        # Zwei getrennte Listen: Grundansichten bleiben oben, Themenbereiche
        # werden mit einem Stretch-Element am unteren Rand der Seitenleiste verankert.
        self.sidebar_panel = QWidget()
        self.sidebar_panel.setMinimumWidth(205)
        self.sidebar_panel.setMaximumWidth(600)
        sidebar_layout = QVBoxLayout(self.sidebar_panel)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("packageSidebar")
        self.sidebar.addItems(["Alle Pakete", "Installiert", "Nicht installiert", "Aufräumen", "Vorgemerkt"])
        self.sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sidebar_layout.addWidget(self.sidebar)
        sidebar_layout.addStretch(1)
        self.topic_sidebar = QListWidget()
        self.topic_sidebar.setObjectName("packageSidebar")
        for _key, label_de, _label_en, _pattern in TOPIC_CATEGORIES:
            self.topic_sidebar.addItem(label_de)
        # Die Themenliste bleibt unten verankert; Scrollleisten werden ausgeblendet.
        # Scrollen per Mausrad bleibt bei Bedarf weiterhin möglich.
        self.topic_sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.topic_sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.topic_sidebar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sidebar_layout.addWidget(self.topic_sidebar)
        self._sidebar_sync = False
        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self._base_sidebar_changed)
        self.topic_sidebar.currentRowChanged.connect(self._topic_sidebar_changed)
        main_splitter.addWidget(self.sidebar_panel)
        self.sidebar.setFixedHeight(5 * 40 + 12)
        self.topic_sidebar.setFixedHeight(len(TOPIC_CATEGORIES) * 40 + 12)
        content=QWidget(); main_splitter.addWidget(content); main_splitter.setStretchFactor(0, 0); main_splitter.setStretchFactor(1, 1); main_splitter.setSizes([280, 1320]); l=QVBoxLayout(content)
        h=QHBoxLayout(); title=QLabel("<span style='font-size:22pt;color:#b99aff;font-weight:bold'>LunaPaket</span><br>" + ("Package management: Debian / Flathub" if self.language == "en" else "Paketverwaltung: Debian / Flathub")); self._main_subtitle_label = title; h.addWidget(title)
        h.addSpacing(14)
        self.apt_mode_btn = QPushButton("🐧  APT (Debian)")
        self.flatpak_mode_btn = QPushButton("🧊  Flathub (Flatpak)")
        self.apt_mode_btn.setCheckable(True); self.flatpak_mode_btn.setCheckable(True)
        self.apt_mode_btn.clicked.connect(lambda: self.set_package_mode("apt"))
        self.flatpak_mode_btn.clicked.connect(lambda: self.set_package_mode("flatpak"))
        h.addWidget(self.apt_mode_btn); h.addWidget(self.flatpak_mode_btn); h.addStretch()
        self.repo_btn=QPushButton("Paketquellen verwalten")
        self.repo_btn.setToolTip("APT-Repositories hinzufügen, bearbeiten, aktivieren oder deaktivieren")
        self.repo_btn.clicked.connect(self.manage_sources)
        h.addWidget(self.repo_btn)
        self.update_btn=QPushButton("Paketlisten aktualisieren"); self.update_btn.clicked.connect(self.update_lists); h.addWidget(self.update_btn)
        self.flatpak_update_btn = QPushButton("Flathub-Updates suchen")
        self.flatpak_update_btn.clicked.connect(self.check_flatpak_updates)
        self.flatpak_update_btn.setVisible(False)
        h.addWidget(self.flatpak_update_btn)
        self.upgrade_btn=QPushButton("System aktualisieren"); self.upgrade_btn.clicked.connect(self.upgrade); h.addWidget(self.upgrade_btn)
        self.security_updates_btn=QPushButton("Sicherheitsupdates verwalten"); self.security_updates_btn.clicked.connect(self.manage_security_updates); h.addWidget(self.security_updates_btn); l.addLayout(h)
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
        # Vertikaler Teiler: Tabellenbereich oben, Paketdetails/Status unten.
        self.work_splitter = QSplitter(Qt.Vertical)
        self.work_splitter.setChildrenCollapsible(False)
        self.work_splitter.setHandleWidth(7)
        upper_panel = QWidget(); upper_layout = QVBoxLayout(upper_panel)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        self.table=PackageTableView(self); self.table.setHorizontalHeaderLabels(["","Paket","Version","Status","Beschreibung"]); self.table.horizontalHeader().setSortIndicatorShown(True); self.table.horizontalHeader().setStretchLastSection(True); self.table.setColumnWidth(0,34); self.table.setColumnWidth(1,270); self.table.setColumnWidth(2,135); self.table.setColumnWidth(3,145); self.table.setIconSize(QSize(44,44)); self.table.verticalHeader().setDefaultSectionSize(54); self.table.selectionModel().selectionChanged.connect(self.details_for_selected); self.table.itemChanged.connect(self.checkbox_changed); self.table.setContextMenuPolicy(Qt.CustomContextMenu); self.table.customContextMenuRequested.connect(self.package_context_menu); upper_layout.addWidget(self.table, 1)
        row=QHBoxLayout()
        clear_queue_btn=QPushButton("Vormerkung löschen")
        clear_queue_btn.clicked.connect(self.clear_queue)
        row.addWidget(clear_queue_btn)
        apply_queue_btn=QPushButton("Vorgemerkte Änderungen anwenden")
        apply_queue_btn.clicked.connect(self.apply_queued_changes)
        row.addWidget(apply_queue_btn)
        self.apt_queue_widgets = [clear_queue_btn, apply_queue_btn]
        # Dieselben Vormerkungsaktionen wie in der APT-Ansicht werden auch
        # für Flatpak verwendet; nur die Ausführung unterscheidet sich intern.
        self.flatpak_queue_widgets = self.apt_queue_widgets
        upper_layout.addLayout(row)
        lower_panel = QWidget(); lower_layout = QVBoxLayout(lower_panel)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        self.details_title = QLabel("Anwendungsdetails")
        self.details_title.setStyleSheet("font-weight: bold; color: #b99aff;")
        lower_layout.addWidget(self.details_title)
        self.lower_content = QSplitter(Qt.Horizontal)
        self.lower_content.setChildrenCollapsible(False)
        self.lower_content.setHandleWidth(6)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumWidth(320)
        self.lower_content.addWidget(self.details)
        self.flatpak_gallery = QWidget()
        self.flatpak_gallery_layout = QHBoxLayout(self.flatpak_gallery)
        self.flatpak_gallery_layout.setContentsMargins(4, 4, 4, 4)
        self.flatpak_gallery_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.flatpak_gallery_scroll = QScrollArea()
        self.flatpak_gallery_scroll.setWidgetResizable(True)
        self.flatpak_gallery_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.flatpak_gallery_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.flatpak_gallery_scroll.setWidget(self.flatpak_gallery)
        self.lower_content.addWidget(self.flatpak_gallery_scroll)
        self.lower_content.setStretchFactor(0, 0)
        self.lower_content.setStretchFactor(1, 1)
        lower_layout.addWidget(self.lower_content, 1)
        self.lower_content.setSizes([560, 840])
        self.flatpak_screenshot = QLabel()  # compatibility placeholder; gallery is used instead
        self.flatpak_screenshot.setVisible(False)
        self.queue_label=QLabel("Keine vorgemerkten Änderungen"); lower_layout.addWidget(self.queue_label); self.status=QLabel("Bereit"); lower_layout.addWidget(self.status)
        self.work_splitter.addWidget(upper_panel); self.work_splitter.addWidget(lower_panel)
        self.work_splitter.setStretchFactor(0, 4); self.work_splitter.setStretchFactor(1, 1)
        self.work_splitter.setSizes([560, 180])
        saved_h = self.settings.value("layout/horizontal_splitter")
        saved_v = self.settings.value("layout/vertical_splitter")
        # Standardwerte nur beim allerersten Start setzen. Gespeicherte Werte
        # werden nach dem Layout-Aufbau erneut angewendet, damit Qt sie nicht
        # durch die anfänglichen Widget-Größen überschreibt.
        if not saved_h:
            main_splitter.setSizes([220, 1100])
        if not saved_v:
            self.work_splitter.setSizes([680, 150])
        def save_splitter_states(*_):
            self.settings.setValue("layout/horizontal_splitter", main_splitter.saveState())
            self.settings.setValue("layout/vertical_splitter", self.work_splitter.saveState())
        main_splitter.splitterMoved.connect(save_splitter_states)
        self.work_splitter.splitterMoved.connect(save_splitter_states)
        QTimer.singleShot(0, lambda: (
            main_splitter.restoreState(saved_h) if saved_h else None,
            self.work_splitter.restoreState(saved_v) if saved_v else None
        ))
        l.addWidget(self.work_splitter, 1)
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

        history_action = QAction("Paketverlauf anzeigen …", self)
        history_action.setToolTip("Zuletzt installierte, entfernte und aktualisierte Pakete anzeigen")
        history_action.triggered.connect(self.show_package_history)
        file_menu.addAction(history_action)

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
        self.flatpak_mode = False
        self.flatpak_queue = {}
        self.flatpak_catalog = []
        self.flatpak_loading = False
        self.table.package_model.flatpak_mode = False
        self.set_package_mode("apt", initial=True)
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
            self.setStyleSheet("QMainWindow,QWidget{background:#f3f4f8;color:#252638;font-size:11pt} QLineEdit,QComboBox,QTextEdit,QTableWidget,QTableView{background:#ffffff;color:#252638;border:1px solid #c9cbd8;padding:6px} QPushButton{background:#6746b8;color:white;border:0;border-radius:6px;padding:8px 13px} QPushButton:hover{background:#7959cb} QHeaderView::section{background:#e4e2ee;color:#37334b;padding:7px} QListWidget#packageSidebar{background:#e9e8f0;border:1px solid #c9c6d6;padding:5px} QListWidget#packageSidebar::item{padding:11px 8px;border-radius:5px} QListWidget#packageSidebar::item:selected{background:#6746b8;color:white} QTableWidget::indicator,QTableView::indicator{width:18px;height:18px} QTableWidget::indicator:checked,QTableView::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QTableWidget::indicator:unchecked,QTableView::indicator:unchecked{background:#ffffff;border:2px solid #8d899e;border-radius:3px} QCheckBox::indicator{width:18px;height:18px} QCheckBox::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QCheckBox::indicator:unchecked{background:#ffffff;border:2px solid #8d899e;border-radius:3px}".replace("font-size:11pt", f"font-size:{self.font_size}pt"))
        else:
            self.setStyleSheet("QMainWindow,QWidget{background:#20212a;color:#eeeef5;font-size:11pt} QLineEdit,QComboBox,QTextEdit,QTableWidget,QTableView{background:#292b37;color:#f2f1fa;border:1px solid #48495d;padding:6px} QPushButton{background:#6746b8;color:white;border:0;border-radius:6px;padding:8px 13px} QPushButton:hover{background:#7959cb} QHeaderView::section{background:#343545;color:#ddd9f4;padding:7px} QListWidget#packageSidebar{background:#252633;border:1px solid #414253;padding:5px} QListWidget#packageSidebar::item{padding:11px 8px;border-radius:5px} QListWidget#packageSidebar::item:selected{background:#6746b8;color:white} QTableWidget::indicator,QTableView::indicator{width:18px;height:18px} QTableWidget::indicator:checked,QTableView::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QTableWidget::indicator:unchecked,QTableView::indicator:unchecked{background:#ffffff;border:2px solid #8d899e;border-radius:3px} QCheckBox::indicator{width:18px;height:18px} QCheckBox::indicator:checked{background:#7652c8;border:2px solid #c9b5ff;border-radius:3px} QCheckBox::indicator:unchecked{background:#ffffff;border:2px solid #c9b5ff;border-radius:3px}".replace("font-size:11pt", f"font-size:{self.font_size}pt"))
    def translate_dialog(self, dialog):
        if self.language != "en":
            return
        translations = {
            "Paketverlauf":"Package history", "Installierte, entfernte und aktualisierte Pakete. Der Verlauf ist auf maximal 1 MB begrenzt.":"Installed, removed and upgraded packages. History is limited to 1 MB.",
            "Noch keine Paketänderungen durch LunaPaket protokolliert.":"No package changes have been logged by LunaPaket yet.",
            "Sicherheitsupdates verwalten":"Manage security updates", "Auswahl":"Selection", "Paket":"Package", "Installiert":"Installed", "Verfügbar":"Available", "Status":"Status", "Sicherheitsquelle":"Security origin",
            "Ausgewählte zurückstellen":"Defer selected", "Ausgewählte wieder aktivieren":"Reactivate selected", "Jetzt nach Updates suchen":"Check for updates now", "Ausgewählte installieren":"Install selected", "Verlauf anzeigen":"Show history", "Automatisch nach Sicherheitsupdates suchen":"Automatically check for security updates", "Prüfintervall:":"Check interval:", "Schließen":"Close", "Alle 15 Minuten":"Every 15 minutes", "Alle 30 Minuten":"Every 30 minutes", "Stündlich":"Hourly", "Alle 6 Stunden":"Every 6 hours", "Täglich":"Daily", "Bereit":"Ready", "Zurückgestellt":"Deferred",
            "Paketquellen (Repository-Verwaltung)":"Repositories (repository management)", "APT-Paketquellen aktivieren, bearbeiten und verwalten.":"Enable, edit and manage APT repositories.", "Aktiviert":"Enabled", "Typ:":"Type:", "Adresse:":"Address:", "Distribution:":"Distribution:", "Bereiche:":"Components:", "Ausgewählte Paketquelle bearbeiten":"Edit selected repository", "Hoch":"Up", "Runter":"Down", "Neu":"New", "Löschen":"Delete", "Übernehmen":"Apply", "Abbrechen":"Cancel", "OK":"OK",
            "Einstellungen – Distribution":"Distribution settings", "⚠  Diese Einstellungen betreffen die elementaren Bestandteile Ihres Systems. Überdenken Sie solche Änderungen daher eingehend.":"⚠  These settings affect essential components of your system. Consider such changes carefully.", "Paketaktualisierungsverhalten (vorgegebene Distribution)":"Package upgrade policy (default distribution)", "Anwenden":"Apply", "Immer die höchste Version bevorzugen":"Always prefer the highest version", "Immer die installierte Version bevorzugen":"Always prefer the installed version", "Version bevorzugen von:":"Prefer version from:",
        }
        translations.update({
            "Paketaktionen bestätigen":"Confirm package actions",
            "Prüfe die geplanten Aktionen. Entferne Häkchen, um einzelne Aktionen abzuwählen.":"Review the planned actions. Uncheck items to omit individual actions.",
            "Installieren":"Install", "Neu installieren":"Reinstall", "Entfernen":"Remove",
            "Vollständig entfernen":"Purge", "Version sperren":"Hold version",
            "Versionssperre aufheben":"Unhold version", "APT-Prüfung (Simulation, noch keine Änderungen ausgeführt):":"APT check (simulation; no changes have been made):",
            "Fenster nach erfolgreicher Aktion schließen":"Close window after successful action",
            "Jetzt ausführen":"Run now", "Aufräumen bestätigen":"Confirm cleanup",
            "Diese Pakete hat APT als nicht mehr benötigt erkannt. Sollen sie entfernt werden?":"APT identified these packages as no longer required. Remove them?",
            "Jetzt aufräumen":"Clean up now", "Abbrechen":"Cancel",
            "Aufräumen":"Cleanup", "Der Paketkatalog wird noch geladen.":"The package catalog is still loading.",
            "Es werden keine nicht mehr benötigten Pakete gefunden.":"No packages eligible for autoremove were found.",
            "Aufräumen abgebrochen – keine Pakete entfernt":"Cleanup cancelled – no packages were removed",
            "Paketaktionen":"Package actions", "Vorgemerkte Änderungen":"Queued changes",
            "Es sind keine Änderungen vorgemerkt. Bitte Pakete zuerst über die Kontrollkästchen auswählen.":"No changes are queued. Select packages using the checkboxes first.",
            "Bitte zuerst Pakete auswählen oder vormerken.":"Please select or queue packages first.",
            "Bitte zuerst ein Paket auswählen.":"Please select a package first.",
            "Keine Paketaktionen ausgewählt":"No package actions selected", "Keine APT-Änderungen.":"No APT changes.",
            "Prüfung fehlgeschlagen":"Check failed", "APT-Prüfung fehlgeschlagen":"APT check failed",
            "Änderungen werden im Hintergrund geprüft …":"Checking changes in the background …",
            "Vorgemerkte Änderungen bleiben erhalten":"Queued changes have been kept",
            "Keine Paketdetails verfügbar.":"No package details available.", "Keine Eigenschaften verfügbar.":"No properties available.",
            "Version auswählen":"Select version", "Für dieses Paket wurden keine verfügbaren Versionen gefunden.":"No available versions were found for this package.",
            "Installierte Dateien":"Installed files", "Das Paket ist nicht installiert oder dpkg konnte die Dateiliste nicht lesen.":"The package is not installed or dpkg could not read its file list.",
            "Paketeigenschaften":"Package properties", "Installierte Dateien anzeigen":"Show installed files",
            "Installieren vormerken":"Queue for installation", "Neu installieren vormerken":"Queue for reinstallation",
            "Entfernen vormerken":"Queue for removal", "Vollständig entfernen (Purge) vormerken":"Queue for purge",
            "Version auswählen …":"Select version …", "Versionssperre aufheben vormerken":"Queue unhold",
            "Version sperren vormerken":"Queue hold", "Abhängigkeiten und Konflikte …":"Dependencies and conflicts …",
            "Eigenschaften …":"Properties …", "Installierte Dateien anzeigen …":"Show installed files …",
            "Schriftgröße":"Font size", "Schriftgröße in Punkt:":"Font size in points:",
            "Ungültiges DEB-Paket":"Invalid DEB package", "Paketverlauf anzeigen":"Show package history",
            "Keine Paketänderungen durch LunaPaket protokolliert.":"No package changes have been logged by LunaPaket.",
            "Paketquellen":"Repositories", "Paketquellen verwalten":"Manage repositories",
            "Sicherheitsupdates":"Security updates", "Sicherheitsupdates installieren":"Install security updates",
            "Bitte mindestens ein Update auswählen.":"Please select at least one update.",
            "APT-Vorschau fehlgeschlagen":"APT preview failed", "Abhängigkeiten und Konflikte":"Dependencies and conflicts",
        })
        dialog.setWindowTitle(translations.get(dialog.windowTitle(), dialog.windowTitle()))
        for w in dialog.findChildren(QWidget):
            if isinstance(w, (QPushButton, QLabel, QCheckBox, QRadioButton, QGroupBox)):
                w.setText(translations.get(w.text(), w.text()))
            elif isinstance(w, QComboBox):
                for i in range(w.count()): w.setItemText(i, translations.get(w.itemText(i), w.itemText(i)))
            elif isinstance(w, QTableWidget):
                for i in range(w.columnCount()):
                    h=w.horizontalHeaderItem(i)
                    if h: h.setText(translations.get(h.text(),h.text()))
        for menu in dialog.findChildren(QMenu): menu.setTitle(translations.get(menu.title(),menu.title()))

    def translate_main_window(self):
        translations = {
            "LunaPaket – Paketverwaltung":"LunaPaket – Package Manager",
            "Alle Pakete":"All packages","Installiert":"Installed","Nicht installiert":"Not installed",
            "Aufräumen":"Cleanup","Vorgemerkt":"Queued","Amateurfunk":"Amateur Radio",
            "Internet & Netzwerk":"Internet & Network","Audio & Musik":"Audio & Music",
            "Video & Multimedia":"Video & Multimedia","Grafik & Design":"Graphics & Design",
            "Programmierung":"Programming","System & Verwaltung":"System & Administration",
            "Sicherheit":"Security","Elektronik & Hardware":"Electronics & Hardware",
            "Büro & Bildung":"Office & Education","Spiele":"Games",
            "Wissenschaft & Navigation":"Science & Navigation",
            "Paketquellen verwalten":"Manage repositories",
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
            "Schließen":"Close", "Paketverlauf anzeigen …":"Show package history …",
            "Paketverlauf":"Package history", "Installierte, entfernte und aktualisierte Pakete. Der Verlauf ist auf maximal 1 MB begrenzt.":"Installed, removed and upgraded packages. History is limited to 1 MB.",
            "Noch keine Paketänderungen durch LunaPaket protokolliert.":"No package changes have been logged by LunaPaket yet.",
            "Sicherheitsupdates werden gesucht …":"Searching for security updates …", "System ist auf dem neuesten Stand":"System is up to date",
            "Es sind keine Paketaktualisierungen verfügbar.\n\nDas System ist aktuell.":"No package updates are available.\n\nThe system is up to date.",
            "Schriftgröße":"Font size", "Schriftgröße in Punkt:":"Font size in points:",
            "Schriftgröße auf {size} pt gesetzt":"Font size set to {size} pt",
            "Sicherheitsupdates verwalten":"Manage security updates", "Auswahl":"Selection", "Installiert":"Installed", "Verfügbar":"Available", "Sicherheitsquelle":"Security origin",
            "Ausgewählte zurückstellen":"Defer selected", "Ausgewählte wieder aktivieren":"Reactivate selected", "Jetzt nach Updates suchen":"Check for updates now", "Ausgewählte installieren":"Install selected", "Verlauf anzeigen":"Show history",
            "Automatisch nach Sicherheitsupdates suchen":"Automatically check for security updates", "Prüfintervall:":"Check interval:", "Alle 15 Minuten":"Every 15 minutes", "Alle 30 Minuten":"Every 30 minutes", "Stündlich":"Hourly", "Alle 6 Stunden":"Every 6 hours", "Täglich":"Daily", "Zurückgestellt":"Deferred",
            "Paketquellen (Repository-Verwaltung)":"Repositories (repository management)", "APT-Paketquellen aktivieren, bearbeiten und verwalten.":"Enable, edit and manage APT repositories.",
            "Aktiviert":"Enabled", "Typ:":"Type:", "Adresse:":"Address:", "Distribution:":"Distribution:", "Bereiche:":"Components:",
            "Ausgewählte Paketquelle bearbeiten":"Edit selected repository", "Hoch":"Up", "Runter":"Down", "Neu":"New", "Löschen":"Delete", "Übernehmen":"Apply", "Abbrechen":"Cancel",
            "Einstellungen – Distribution":"Distribution settings", "⚠  Diese Einstellungen betreffen die elementaren Bestandteile Ihres Systems. Überdenken Sie solche Änderungen daher eingehend.":"⚠  These settings affect essential components of your system. Consider such changes carefully.",
            "Paketaktualisierungsverhalten (vorgegebene Distribution)":"Package upgrade policy (default distribution)", "Anwenden":"Apply", "Immer die höchste Version bevorzugen":"Always prefer the highest version", "Immer die installierte Version bevorzugen":"Always prefer the installed version", "Version bevorzugen von:":"Prefer version from:", "Anwenden":"Apply"
        }
        translations.update({
            "Paketquellen verwalten":"Manage repositories", "Paketlisten aktualisieren":"Refresh package lists",
            "System aktualisieren":"Upgrade system", "Sicherheitsupdates verwalten":"Manage security updates",
            "Vormerkung löschen":"Clear queue", "Vorgemerkte Änderungen anwenden":"Apply queued changes",
            "Keine vorgemerkten Änderungen":"No queued changes", "Bereit":"Ready",
            "Datei":"File", "Beenden":"Quit", "Paketquellen":"Repositories", "Einstellungen":"Settings",
            "Hilfe":"Help", "Paket":"Package", "Beschreibung":"Description", "Nicht installiert":"Not installed",
            "Installiert":"Installed", "Alle Pakete":"All packages", "Aufräumen":"Cleanup", "Vorgemerkt":"Queued",
            "Pakete suchen …":"Search packages …", "Suchergebnisse":"Search results", "Installierte Pakete":"Installed packages",
            "Suchen":"Search", "DEB-Pakete öffnen …":"Open DEB packages …",
            "Paketquellen prüfen / Paketlisten aktualisieren":"Check repositories / refresh package lists",
            "Paketquellen anzeigen":"Show repositories", "Distribution …":"Distribution …",
            "Schriftgröße …":"Font size …", "Allgemeine Einstellungen …":"General settings …",
            "Über LunaPaket":"About LunaPaket", "Paketverlauf anzeigen …":"Show package history …",
            "Paketaktion läuft …":"Package operation in progress …", "Änderungen werden im Hintergrund geprüft …":"Checking changes in the background …",
            "Keine entbehrlichen Pakete gefunden":"No removable packages found",
            "Paketkatalog wird geladen …":"Loading package catalog …",
            "Paketkatalog wird noch geladen.":"The package catalog is still loading.",
            "Paketaktion läuft …":"Package operation in progress …",
            "Keine vorgemerkten Änderungen":"No queued changes",
            "Paketliste wird aktualisiert …":"Refreshing package lists …",
            "System wird aktualisiert …":"Upgrading system …",
        })
        mapping = translations if self.language == "en" else {v: k for k, v in translations.items()}

        current_title = self.windowTitle()
        german_prefix = "LunaPaket – Paketverwaltung"
        english_prefix = "LunaPaket – Package Manager"
        if self.language == "en" and current_title.startswith(german_prefix):
            current_title = current_title.replace(german_prefix, english_prefix, 1)
        elif self.language == "de" and current_title.startswith(english_prefix):
            current_title = current_title.replace(english_prefix, german_prefix, 1)
        self.setWindowTitle(current_title)

        # The main package table is a QTableView backed by a custom model;
        # translate its model headers and package status values explicitly.
        if hasattr(self, "table") and hasattr(self.table, "package_model"):
            self.table.package_model.language = self.language
            self.table.package_model.headerDataChanged.emit(Qt.Horizontal, 0, 4)
            if self.table.package_model.rowCount():
                self.table.package_model.dataChanged.emit(
                    self.table.package_model.index(0, 3),
                    self.table.package_model.index(self.table.package_model.rowCount()-1, 3),
                    [Qt.DisplayRole])
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
        # Visibility is based on the active package mode, never on translated button text.
        if hasattr(self, "flatpak_mode"):
            apt_visible = not self.flatpak_mode
            self.repo_btn.setVisible(apt_visible)
            self.update_btn.setVisible(apt_visible)
            self.upgrade_btn.setVisible(apt_visible)
            self.security_updates_btn.setVisible(apt_visible)
            self.flatpak_update_btn.setVisible(self.flatpak_mode)

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
        if hasattr(self, "work_splitter"):
            self.settings.setValue("layout/vertical_splitter", self.work_splitter.saveState())
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
        self.translate_dialog(d)
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
        catalog_label = QLabel()
        catalog_retention = QComboBox()
        catalog_retention.addItem("1 day" if self.language == "en" else "1 Tag", 1)
        catalog_retention.addItem("3 days" if self.language == "en" else "3 Tage", 3)
        catalog_retention.addItem("7 days" if self.language == "en" else "7 Tage", 7)
        catalog_retention.addItem("14 days" if self.language == "en" else "14 Tage", 14)
        catalog_retention.addItem("30 days" if self.language == "en" else "30 Tage", 30)
        catalog_retention.addItem("Never expire" if self.language == "en" else "Nie automatisch löschen", 0)
        current_retention = int(self.settings.value("cache/appstream_retention_days", 7))
        retention_index = catalog_retention.findData(current_retention)
        catalog_retention.setCurrentIndex(retention_index if retention_index >= 0 else 2)
        catalog_row = QHBoxLayout()
        catalog_row.addWidget(catalog_label)
        catalog_row.addWidget(catalog_retention, 1)
        flathub_catalog_label = QLabel()
        flathub_catalog_retention = QComboBox()
        for label, days in (
            (("1 day" if self.language == "en" else "1 Tag"), 1),
            (("3 days" if self.language == "en" else "3 Tage"), 3),
            (("7 days" if self.language == "en" else "7 Tage"), 7),
            (("14 days" if self.language == "en" else "14 Tage"), 14),
            (("30 days" if self.language == "en" else "30 Tage"), 30),
            (("Never expire" if self.language == "en" else "Nie automatisch löschen"), 0),
        ):
            flathub_catalog_retention.addItem(label, days)
        flathub_days = int(self.settings.value("cache/flathub_catalog_retention_days", 7))
        flathub_index = flathub_catalog_retention.findData(flathub_days)
        flathub_catalog_retention.setCurrentIndex(flathub_index if flathub_index >= 0 else 2)
        flathub_catalog_row = QHBoxLayout()
        flathub_catalog_row.addWidget(flathub_catalog_label)
        flathub_catalog_row.addWidget(flathub_catalog_retention, 1)
        delete_catalog = QPushButton()
        refresh_catalog = QPushButton()
        def update_settings_language():
            english = self.language == "en"
            dlg.setWindowTitle("LunaPaket – Settings" if english else "LunaPaket – Einstellungen")
            remember.setText("Remember window size and position" if english else "Fenstergröße und Fensterposition merken")
            remember.setToolTip("Saves the window size and position on exit and restores them next time." if english else "Speichert Größe und Position beim Schließen und stellt sie beim nächsten Start wieder her.")
            cache.setText("Delete downloaded package files after successful installation" if english else "Heruntergeladene Paketdateien nach erfolgreicher Installation löschen")
            catalog_label.setText("Keep APT image catalog:" if english else "APT-Bilderkatalog speichern für:")
            flathub_catalog_label.setText(
                "Keep Flathub application list:" if english else "Flathub-Anwendungsliste speichern für:"
            )
            retention_labels = (
                ["1 day", "3 days", "7 days", "14 days", "30 days", "Never expire"]
                if english else ["1 Tag", "3 Tage", "7 Tage", "14 Tage", "30 Tage", "Nie automatisch löschen"]
            )
            for item_index, item_label in enumerate(retention_labels):
                catalog_retention.setItemText(item_index, item_label)
            delete_catalog.setText("Delete saved APT catalog" if english else "Gespeicherten APT-Katalog löschen")
            refresh_catalog.setText("Refresh APT AppStream catalog now" if english else "APT-AppStream-Katalog jetzt aktualisieren")
            buttons.button(QDialogButtonBox.Close).setText("Close" if english else "Schließen")
        cache.setChecked(self.clean_cache_enabled)
        cache.setChecked(self.clean_cache_enabled)
        layout.addWidget(remember)
        layout.addWidget(cache)
        layout.addLayout(catalog_row)
        layout.addLayout(flathub_catalog_row)
        layout.addWidget(refresh_catalog)
        layout.addWidget(delete_catalog)
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
            # Modeabhängige Schaltflächen und Beschriftungen sofort neu setzen.
            # Dadurch hängt die Sichtbarkeit nicht davon ab, ob die Anwendung
            # nach einem Sprachwechsel neu gestartet wurde.
            self.set_package_mode("flatpak" if self.flatpak_mode else "apt")
            self.translate_main_window()
            self._populate_topic_sidebar()
            if self.flatpak_mode and self.flatpak_catalog:
                selected_app = self.selected_flatpak_id()
                self.apply_table_filters()
                if selected_app:
                    self.show_flatpak_details(selected_app)
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
        def retention_changed(index):
            value = int(catalog_retention.currentData())
            self.settings.setValue("cache/appstream_retention_days", value)
            self._apt_appstream_cache = None
            self._sync_settings_permissions()
        catalog_retention.currentIndexChanged.connect(retention_changed)
        def flathub_retention_changed(index):
            value = int(flathub_catalog_retention.currentData())
            self.settings.setValue("cache/flathub_catalog_retention_days", value)
        flathub_catalog_retention.currentIndexChanged.connect(flathub_retention_changed)
        def delete_saved_catalog():
            english = self.language == "en"
            title = "Delete APT image catalog" if english else "APT-Bilderkatalog löschen"
            question = (
                "Delete the saved APT image catalog and downloaded AppStream metadata?\n"
                "Downloaded screenshot images will be kept."
                if english else
                "Den gespeicherten APT-Bilderkatalog und die heruntergeladenen AppStream-Metadaten löschen?\n"
                "Bereits heruntergeladene Screenshot-Bilder bleiben erhalten."
            )
            answer = QMessageBox.question(
                dlg, title, question,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return
            cache_root = Path.home() / ".cache" / "LunaPaket"
            removed = 0
            try:
                for pattern in ("apt-appstream-index-*.json", "flathub_catalog.json"):
                    for item in cache_root.glob(pattern):
                        try:
                            item.unlink()
                            removed += 1
                        except OSError:
                            pass
                appstream_dir = cache_root / "appstream"
                if appstream_dir.exists():
                    for item in appstream_dir.iterdir():
                        if item.is_file():
                            try:
                                item.unlink()
                                removed += 1
                            except OSError:
                                pass
                self._apt_appstream_cache = None
                QMessageBox.information(
                    dlg, title,
                    (f"Saved catalog files deleted ({removed})." if english else
                     f"Gespeicherte Katalogdateien gelöscht ({removed}).")
                )
            except Exception as error:
                QMessageBox.warning(dlg, title, str(error))
        delete_catalog.clicked.connect(delete_saved_catalog)

        def refresh_saved_catalog():
            if getattr(self, "_apt_catalog_refresh_running", False):
                return
            english = self.language == "en"
            refresh_catalog.setEnabled(False)
            refresh_catalog.setText("Refreshing catalog …" if english else "Katalog wird aktualisiert …")
            self._apt_catalog_refresh_running = True
            self.status.setText(
                "Refreshing APT AppStream catalog in the background …" if english
                else "APT-AppStream-Katalog wird im Hintergrund aktualisiert …"
            )
            self.apt_catalog_refresh_job = FunctionJob(lambda: self._read_apt_appstream_metadata(force_refresh=True))

            def refresh_done(data):
                self._apt_catalog_refresh_running = False
                self._apt_appstream_cache = data
                refresh_catalog.setEnabled(True)
                refresh_catalog.setText(
                    "Refresh APT AppStream catalog now" if self.language == "en"
                    else "APT-AppStream-Katalog jetzt aktualisieren"
                )
                self.status.setText(
                    (f"APT AppStream catalog updated ({len(data)} packages)." if self.language == "en"
                     else f"APT-AppStream-Katalog aktualisiert ({len(data)} Pakete).")
                )
                if not self.flatpak_mode:
                    selected_name = self.selected()
                    if selected_name:
                        self.show_apt_screenshots(selected_name)
                QMessageBox.information(
                    dlg,
                    "APT AppStream" if self.language == "en" else "APT-AppStream",
                    (f"Catalog refreshed. {len(data)} package entries loaded." if self.language == "en"
                     else f"Katalog aktualisiert. {len(data)} Paketeinträge geladen.")
                )

            def refresh_failed(error):
                self._apt_catalog_refresh_running = False
                refresh_catalog.setEnabled(True)
                refresh_catalog.setText(
                    "Refresh APT AppStream catalog now" if self.language == "en"
                    else "APT-AppStream-Katalog jetzt aktualisieren"
                )
                self.status.setText(
                    ("APT AppStream refresh failed: " if self.language == "en" else "APT-AppStream-Aktualisierung fehlgeschlagen: ")
                    + str(error)
                )
                QMessageBox.warning(dlg, "APT AppStream", str(error))

            self.apt_catalog_refresh_job.result.connect(refresh_done)
            self.apt_catalog_refresh_job.failed.connect(refresh_failed)
            self.apt_catalog_refresh_job.start()

        refresh_catalog.clicked.connect(refresh_saved_catalog)
        dlg.exec()

    def closeEvent(self, event):
        # QThreads müssen vor dem Zerstören des Fensters fertig sein.
        # Netzwerk-Bildabrufe haben ein begrenztes Timeout.
        for job in list(FunctionJob._live_jobs):
            if job.isRunning():
                job.wait(15000)
        if self.remember_window_enabled:
            self.settings.setValue("window/geometry", self.saveGeometry())
        if hasattr(self, "work_splitter"):
            self.settings.setValue("layout/vertical_splitter", self.work_splitter.saveState())
        if hasattr(self, "main_splitter"):
            self.settings.setValue("layout/horizontal_splitter", self.main_splitter.saveState())
        self._sync_settings_permissions()
        super().closeEvent(event)
    def _populate_topic_sidebar(self):
        """Zeigt dieselben zwölf Themenkategorien in APT und Flathub."""
        self.topic_sidebar.blockSignals(True)
        self.topic_sidebar.clear()
        for _key, label_de, label_en, _pattern in TOPIC_CATEGORIES:
            self.topic_sidebar.addItem(label_en if self.language == "en" else label_de)
        self.topic_sidebar.setCurrentRow(-1)
        self.topic_sidebar.blockSignals(False)

    def set_package_mode(self, mode, initial=False):
        """Schaltet zwischen dem unveränderten APT-Katalog und Flathub um."""
        flatpak = mode == "flatpak"
        self.flatpak_mode = flatpak
        self.table.package_model.flatpak_mode = flatpak
        self.table.setIconSize(QSize(44, 44) if flatpak else QSize(16, 16))
        self.table.verticalHeader().setDefaultSectionSize(54 if flatpak else 30)
        self.apt_mode_btn.setChecked(not flatpak)
        self.flatpak_mode_btn.setChecked(flatpak)
        for widget in [self.repo_btn, self.update_btn]:
            widget.setVisible(not flatpak)
        self.flatpak_update_btn.setVisible(flatpak)
        self.flatpak_update_btn.setText("Check for Flathub updates" if self.language == "en" else "Flathub-Updates suchen")
        # System- und Sicherheitsupdates bleiben ausschließlich APT-Funktionen.
        self.upgrade_btn.setVisible(not flatpak)
        self.security_updates_btn.setVisible(not flatpak)
        for widget in self.apt_queue_widgets:
            widget.setVisible(True)
        if self.language == "en":
            self.apt_queue_widgets[0].setText("Clear queue")
            self.apt_queue_widgets[1].setText("Apply queued changes")
        else:
            self.apt_queue_widgets[0].setText("Vormerkung löschen")
            self.apt_queue_widgets[1].setText("Vorgemerkte Änderungen anwenden")
        self.topic_sidebar.setVisible(True)
        self._populate_topic_sidebar()
        self.flatpak_gallery_scroll.setVisible(True)
        self.cleanup_select_all.setVisible(False)
        if flatpak:
            self.sidebar.blockSignals(True)
            self.sidebar.clear()
            self.sidebar.addItems(
                ["All applications", "Installed", "Not installed", "Cleanup"] if self.language == "en"
                else ["Alle Anwendungen", "Installiert", "Nicht installiert", "Aufräumen"])
            self.sidebar.setCurrentRow(0)
            self.sidebar.blockSignals(False)
            self.search.setPlaceholderText(
                "Search Flathub applications …" if self.language == "en"
                else "Flathub-Anwendungen suchen …")
            self.filter.setVisible(False)
            self.details_title.setText("Application details" if self.language == "en" else "Anwendungsdetails")
            self.details.setPlainText(
                "Select an application from the list. App information will appear here."
                if self.language == "en" else
                "Wähle eine Anwendung aus der Liste aus. Die App-Informationen erscheinen hier.")
            self.clear_flatpak_gallery()
            self.flatpak_gallery_layout.addWidget(QLabel(
                "App images appear here when Flathub provides screenshots."
                if self.language == "en" else
                "App-Bilder erscheinen hier, sofern Flathub Screenshots bereitstellt."))
            if self.flatpak_catalog:
                self.apply_table_filters()
            else:
                self.load_flatpak_catalog()
        else:
            self.clear_flatpak_gallery()
            self.flatpak_gallery_layout.addWidget(QLabel(
                "Select an APT package to view available screenshots."
                if self.language == "en" else
                "Wähle ein APT-Paket aus, um verfügbare Screenshots anzuzeigen."))
            self.details_title.setText("Package details" if self.language == "en" else "Paketdetails")
            self.topic_sidebar.blockSignals(True)
            self.topic_sidebar.setCurrentRow(-1)
            self.topic_sidebar.blockSignals(False)
            self.sidebar.blockSignals(True)
            self.sidebar.clear()
            self.sidebar.addItems(
                ["All packages", "Installed", "Not installed", "Cleanup", "Queued"] if self.language == "en"
                else ["Alle Pakete", "Installiert", "Nicht installiert", "Aufräumen", "Vorgemerkt"])
            self.sidebar.setCurrentRow(0)
            self.sidebar.blockSignals(False)
            self.filter.setVisible(True)
            self.search.setPlaceholderText(
                "Search packages …" if self.language == "en" else "Pakete suchen …")
            if (self.catalog_cache is not None and self._table_catalog_ready
                    and self._table_mode == "apt"):
                self.apply_table_filters()
            elif self.catalog_cache is not None:
                # Der APT-Katalog kann fertig geworden sein, während Flathub
                # aktiv war. Beim Zurückwechseln die gespeicherten Daten anzeigen.
                self.rows(self.catalog_cache["rows"])
            elif not initial:
                self.search_pkgs()
        self.update_queue_label()
        if flatpak:
            # Beim erneuten Wechsel zu Flathub ist der Katalog häufig bereits
            # vollständig geladen. Dann darf der Status nicht wieder auf
            # „Loading“ zurückgesetzt werden.
            if self.flatpak_catalog:
                count = len(self.flatpak_catalog)
                self.status.setText(
                    f"{count} Flatpak applications found · Flathub" if self.language == "en"
                    else f"{count} Flatpak-Anwendungen gefunden · Flathub")
            else:
                self.status.setText(
                    "Loading Flathub catalog …" if self.language == "en"
                    else "Flathub wird geladen …")
        else:
            self.status.setText("APT mode active" if self.language == "en" else "APT-Modus aktiv")

    @staticmethod
    def _flatpak_icon_path(app_id):
        roots = [
            Path.home() / ".local/share/flatpak/appstream",
            Path("/var/lib/flatpak/appstream"),
        ]
        for base in roots:
            if not base.exists():
                continue
            try:
                for path in base.glob(f"*/**/icons/*/*/{app_id}.*"):
                    if path.suffix.lower() in (".png", ".svg", ".webp"):
                        return str(path)
                for path in base.glob(f"*/**/icons/*/{app_id}.*"):
                    if path.suffix.lower() in (".png", ".svg", ".webp"):
                        return str(path)
            except OSError:
                pass
        return ""

    @staticmethod
    def _read_flatpak_appstream_metadata():
        """Liest optionale AppStream-Metadaten aus dem lokalen Flatpak-Cache."""
        metadata = {}
        roots = [Path.home() / ".local/share/flatpak/appstream",
                 Path("/var/lib/flatpak/appstream")]
        files = []
        for base in roots:
            if base.exists():
                files.extend(base.glob("*/**/active/appstream.xml.gz"))
                files.extend(base.glob("*/**/active/appstream.xml"))
        for path in files:
            try:
                opener = gzip.open if path.suffix == ".gz" else open
                with opener(path, "rb") as stream:
                    for _event, elem in ET.iterparse(stream, events=("end",)):
                        if elem.tag.rsplit("}", 1)[-1] != "component":
                            continue
                        def node_text(node):
                            return " ".join("".join(node.itertext()).split()) if node is not None else ""
                        def child_node(parent, tag):
                            return next((x for x in parent if x.tag.rsplit("}",1)[-1] == tag), None)
                        def localized_child(parent, tag):
                            default_node = next((x for x in parent
                                                 if x.tag.rsplit("}",1)[-1] == tag
                                                 and not x.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")), None)
                            if default_node is None:
                                default_node = child_node(parent, tag)
                            default_value = node_text(default_node)
                            translations = {}
                            for candidate in parent:
                                if candidate.tag.rsplit("}",1)[-1] != tag:
                                    continue
                                locale = candidate.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "").strip()
                                value = node_text(candidate)
                                if locale and value:
                                    translations[locale] = value
                            return default_value, translations
                        app_id = node_text(child_node(elem, "id"))
                        if app_id:
                            app_name, app_name_locales = localized_child(elem, "name")
                            app_summary, app_summary_locales = localized_child(elem, "summary")
                            description_node = next((x for x in elem
                                                     if x.tag.rsplit("}",1)[-1] == "description"
                                                     and not x.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")), None)
                            if description_node is None:
                                description_node = child_node(elem, "description")
                            app_description = node_text(description_node)
                            app_description_locales = {}
                            if description_node is not None:
                                for candidate in elem:
                                    if candidate.tag.rsplit("}",1)[-1] != "description":
                                        continue
                                    locale = candidate.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", "").strip()
                                    value = node_text(candidate)
                                    if locale and value:
                                        app_description_locales[locale] = value
                            developer = ""
                            developer_locales = {}
                            for node in elem.iter():
                                if node.tag.rsplit("}",1)[-1] == "developer":
                                    developer, developer_locales = localized_child(node, "name")
                                    break
                            homepage = ""
                            for node in elem:
                                if node.tag.rsplit("}",1)[-1] == "url" and node.attrib.get("type") == "homepage":
                                    homepage = (node.text or "").strip()
                            screenshots = []
                            for node in elem.iter():
                                if node.tag.rsplit("}",1)[-1] == "screenshot":
                                    image_url = ""
                                    caption = ""
                                    for sub in node.iter():
                                        tag = sub.tag.rsplit("}",1)[-1]
                                        if tag == "image" and sub.text and not image_url:
                                            image_url = sub.text.strip()
                                        elif tag == "caption" and sub.text and not caption:
                                            caption = sub.text.strip()
                                    if image_url:
                                        screenshots.append((image_url, caption))
                            category_values = []
                            categories_node = next((x for x in elem if x.tag.rsplit("}", 1)[-1] == "categories"), None)
                            if categories_node is not None:
                                for category_node in categories_node:
                                    if category_node.tag.rsplit("}", 1)[-1] == "category":
                                        value = " ".join("".join(category_node.itertext()).split())
                                        if value:
                                            category_values.append(value)
                            metadata[app_id] = {
                                "name": app_name,
                                "summary": app_summary,
                                "description": app_description,
                                "localized": {
                                    "name": app_name_locales,
                                    "summary": app_summary_locales,
                                    "description": app_description_locales,
                                    "developer": developer_locales,
                                },
                                "developer": developer,
                                "license": node_text(child_node(elem, "project_license")),
                                "homepage": homepage,
                                "screenshots": screenshots,
                                "categories": category_values,
                            }
                        elem.clear()
            except Exception:
                continue
        return metadata

    @staticmethod
    def _flatpak_icon_index(roots=None):
        """Indexiert Flatpak-AppStream-Icons, auch wenn 'active' ein Symlink ist."""
        if roots is None:
            roots = [
                Path.home() / ".local/share/flatpak/appstream",
                Path("/var/lib/flatpak/appstream"),
            ]
        index = {}
        for base in roots:
            base = Path(base)
            if not base.exists():
                continue
            try:
                # Flatpak verwendet für AppStream häufig einen 'active'-Symlink.
                # Path.glob("**") läuft nicht zuverlässig durch solche Symlinks.
                for current, dirs, files in os.walk(str(base), followlinks=True):
                    current_path = Path(current)
                    if "icons" not in current_path.parts:
                        continue
                    for filename in files:
                        suffix = Path(filename).suffix.lower()
                        if suffix not in (".png", ".svg", ".webp"):
                            continue
                        icon_id = Path(filename).stem
                        index.setdefault(icon_id, str(Path(current) / filename))
            except OSError:
                continue
        return index

    @staticmethod
    def collect_flatpak_catalog(retention_days=7):
        """Load Flathub from a fresh local cache, otherwise refresh it in the background."""
        if not shutil.which("flatpak"):
            raise RuntimeError("Flatpak is not installed / Flatpak ist nicht installiert.")

        def flatpak_query(args, timeout=35):
            try:
                proc = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, timeout=timeout,
                                      stdin=subprocess.DEVNULL,
                                      env={**os.environ, "GIO_USE_VFS": "local"})
                return proc.returncode, proc.stdout
            except subprocess.TimeoutExpired:
                return 124, "Flatpak query timed out / Flatpak-Abfrage hat zu lange gedauert"
            except Exception as exc:
                return 1, str(exc)

        # The default Flatpak queries worked before the previous scope rewrite.
        # Avoid four sequential remote calls, each previously allowed 30 minutes.
        rc, out = flatpak_query(["flatpak", "list", "--app",
                                 "--columns=application,version"], 15)
        installed = {}
        if rc == 0:
            for line in out.splitlines():
                parts = re.split(r"\s+", line.strip(), maxsplit=1)
                if parts and parts[0].strip():
                    installed[parts[0].strip()] = parts[1].strip() if len(parts) > 1 else ""

        cache_file = Path.home() / ".cache" / "LunaPaket" / "flathub_catalog.json"
        try:
            cache_fresh = (
                cache_file.is_file()
                and (retention_days == 0
                     or time.time() - cache_file.stat().st_mtime < retention_days * 86400)
            )
            if cache_fresh:
                cached_rows = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(cached_rows, list):
                    # Icon-Dateien können sich nach Flatpak-Installationen,
                    # -Entfernungen oder AppStream-Aktualisierungen ändern.
                    # Deshalb niemals alte Icon-Pfade blind aus dem JSON-Cache
                    # übernehmen, sondern den lokalen AppStream-Iconbestand
                    # bei jedem Katalogladen erneut indizieren.
                    current_icon_index = Window._flatpak_icon_index()
                    current_appstream = Window._read_flatpak_appstream_metadata()
                    refreshed_rows = []
                    for row in cached_rows:
                        if not isinstance(row, list) or len(row) < 8:
                            continue
                        row = list(row)
                        row[2] = "Installiert" if row[0] in installed else "Nicht installiert"
                        row[5] = current_icon_index.get(row[0], "")
                        meta = dict(row[7]) if isinstance(row[7], dict) else {}
                        fresh_meta = current_appstream.get(row[0], {})
                        if fresh_meta:
                            # Neue AppStream-Sprachvarianten auch in bereits
                            # vorhandene Katalog-Caches übernehmen.
                            meta.update(fresh_meta)
                            if len(row) > 3:
                                row[3] = fresh_meta.get("summary") or row[3]
                            if len(row) > 6:
                                row[6] = fresh_meta.get("name") or row[6]
                        meta["installed_scopes"] = []
                        row[7] = meta
                        refreshed_rows.append(tuple(row))
                    if refreshed_rows:
                        return refreshed_rows
        except (OSError, ValueError, TypeError):
            pass

        rc, out = flatpak_query(["flatpak", "remote-ls", "--app",
                                 "--columns=application,version", "flathub"], 40)
        remote_rows = {}
        if rc == 0:
            for line in out.splitlines():
                parts = re.split(r"\s+", line.strip(), maxsplit=1)
                if parts and parts[0].strip():
                    remote_rows[parts[0].strip()] = parts[1].strip() if len(parts) > 1 else ""
        elif not installed:
            raise RuntimeError("Flathub catalog could not be loaded / Flathub-Katalog konnte nicht geladen werden: " + out)

        for app_id, values in installed.items():
            remote_rows.setdefault(app_id, values)

        # Inspect local configuration, not the network, to select the installation scope.
        rc, remote_output = flatpak_query(["flatpak", "remotes", "--columns=name,options"], 10)
        remote_scope = "--user"
        if rc == 0:
            for line in remote_output.splitlines():
                fields = line.split("\t")
                if fields and fields[0].strip() == "flathub":
                    remote_scope = "--user" if len(fields) > 1 and "user" in fields[1].lower() else "--system"
                    break

        appstream_metadata = Window._read_flatpak_appstream_metadata()
        icon_index = Window._flatpak_icon_index()
        rows = []
        for app_id, version in sorted(remote_rows.items(), key=lambda x: (
                str(appstream_metadata.get(x[0], {}).get("name") or x[0]).casefold())):
            is_installed = app_id in installed
            meta = dict(appstream_metadata.get(app_id, {}))
            name = meta.get("name") or app_id
            description = meta.get("summary") or name
            meta["remote_scope"] = remote_scope
            meta["installed_scopes"] = []  # resolved before uninstall if necessary
            rows.append((app_id, version, "Installiert" if is_installed else "Nicht installiert",
                         description, "flathub", icon_index.get(app_id, ""), name, meta))
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = cache_file.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            temporary.replace(cache_file)
        except OSError:
            pass
        return rows

    def load_flatpak_catalog(self):
        if self.flatpak_loading:
            return
        self.flatpak_loading = True
        self.status.setText("Flathub-Katalog wird im Hintergrund geladen …")
        retention_days = int(self.settings.value("cache/flathub_catalog_retention_days", 7))
        self.flatpak_job = FunctionJob(lambda: self.collect_flatpak_catalog(retention_days))
        self.flatpak_job.result.connect(self.flatpak_catalog_loaded)
        self.flatpak_job.failed.connect(self.flatpak_catalog_failed)
        self.flatpak_job.start()

    def flatpak_catalog_loaded(self, rows):
        self.flatpak_loading = False
        self.flatpak_catalog = rows
        # Ergebnisse dürfen im Hintergrund gespeichert werden, aber nur die
        # aktive Flathub-Ansicht darf das gemeinsame Tabellenmodell aktualisieren.
        if not self.flatpak_mode:
            return
        self.apply_table_filters()
        if not self.table.currentIndex().isValid():
            self.details_title.setText("Application details" if self.language == "en" else "Anwendungsdetails")
            self.details.setPlainText(
                "Select an application from the list. App information will appear here."
                if self.language == "en" else
                "Wähle eine Anwendung aus der Liste aus. Die App-Informationen erscheinen hier."
            )
        self.status.setText(
            f"{len(rows)} Flatpak applications found · Flathub" if self.language == "en"
            else f"{len(rows)} Flatpak-Anwendungen gefunden · Flathub")

    def flatpak_catalog_failed(self, error):
        self.flatpak_loading = False
        if not self.flatpak_mode:
            return
        self.table.package_model.replace_rows([], {})
        self._table_mode = "flatpak"
        self.status.setText("Flathub: " + str(error))

    def queue_flatpak_action(self, app_id, action):
        if action is None:
            self.flatpak_queue.pop(app_id, None)
        else:
            self.flatpak_queue[app_id] = action
        self.update_queue_label()
        self.apply_table_filters()

    def selected_flatpak_id(self):
        index = self.table.currentIndex()
        if not index.isValid():
            return None
        return str(self.table.package_model.data(index, Qt.UserRole) or "")

    def install_selected_flatpak(self):
        app_id = self.selected_flatpak_id()
        if not app_id:
            QMessageBox.information(
                self, "Flathub",
                "Please select an application first." if self.language == "en"
                else "Bitte zuerst eine Anwendung auswählen."
            )
            return
        self.status.setText(f"{app_id} wird installiert …")
        self.set_busy(True)
        self.flatpak_action_job = FunctionJob(lambda: cmd(self._flatpak_command_for_action(app_id, "install")))
        def finished(result):
            rc, output = result
            self.set_busy(False)
            self.details.setPlainText(output)
            if rc == 0:
                self.load_flatpak_catalog()
            else:
                self.status.setText(
                    "Flatpak installation failed." if self.language == "en"
                    else "Flatpak-Installation fehlgeschlagen."
                )
        self.flatpak_action_job.result.connect(finished)
        self.flatpak_action_job.failed.connect(
            lambda e: (
                self.set_busy(False),
                self.status.setText(("Flatpak error: " if self.language == "en" else "Flatpak-Fehler: ") + str(e))
            )
        )
        self.flatpak_action_job.start()

    def remove_selected_flatpak(self):
        app_id = self.selected_flatpak_id()
        if not app_id:
            QMessageBox.information(self, "Flathub", "Bitte zuerst eine Anwendung auswählen.")
            return
        answer = QMessageBox.question(
            self,
            "Remove Flatpak application" if self.language == "en" else "Flatpak entfernen",
            (f"Really remove {app_id}?" if self.language == "en" else f"{app_id} wirklich entfernen?"),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        self.set_busy(True)
        self.flatpak_action_job = FunctionJob(lambda: cmd(self._flatpak_command_for_action(app_id, "remove")))
        def finished(result):
            rc, output = result
            self.set_busy(False)
            self.details.setPlainText(output)
            if rc == 0:
                self.load_flatpak_catalog()
            else:
                self.status.setText(
                    "Flatpak removal failed." if self.language == "en"
                    else "Flatpak-Deinstallation fehlgeschlagen."
                )
        self.flatpak_action_job.result.connect(finished)
        self.flatpak_action_job.failed.connect(lambda e: (self.set_busy(False), self.status.setText("Flatpak-Fehler: " + str(e))))
        self.flatpak_action_job.start()

    def rows(self, data):
        # Ein Modell-Reset übernimmt den gesamten APT-Katalog in einem Schritt.
        # Qt erzeugt keine individuellen Items für jede sichtbare Tabellenzelle.
        self._table_mode = "apt"
        self._rows_generation = getattr(self, "_rows_generation", 0) + 1
        self.table.setUpdatesEnabled(False)
        self.table.package_model.replace_rows(data, self.queue)
        self.table.setUpdatesEnabled(True)
        self._table_catalog_ready = True
        self.apply_table_filters()
        count=len(data)
        self.status.setText((f"{count} packages loaded · Categories are filtered without reloading" if self.language == "en" else f"{count} Pakete vollständig geladen · Kategorien werden ohne Neuladen gefiltert"))

    def checkbox_changed(self, item):
        # Checkbox-Änderungen, die durch mark()/refresh_checkbox() ausgelöst
        # werden, dürfen die ausdrücklich gewählte Aktion (insbesondere purge)
        # nicht als normales remove zurück in die Vormerkliste schreiben.
        if getattr(self, "_syncing_queue_checkbox", False):
            return
        if item.column() != 0 or self.table.signalsBlocked():
            return
        name=item.data(Qt.UserRole)
        if not name:
            return
        installed = bool(item.data(Qt.UserRole + 1))
        checked = item.checkState() == Qt.Checked
        if self.flatpak_mode:
            if checked and not installed:
                self.flatpak_queue[name] = "install"
            elif not checked and installed:
                self.flatpak_queue[name] = "remove"
            else:
                self.flatpak_queue.pop(name, None)
            self.update_queue_label()
            return
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
    def _base_sidebar_changed(self, row):
        if self._sidebar_sync or row < 0:
            return
        self._sidebar_sync = True
        self.topic_sidebar.setCurrentRow(-1)
        self._sidebar_sync = False
        self.sidebar_changed(row)

    def _topic_sidebar_changed(self, row):
        if self._sidebar_sync or row < 0:
            return
        self._sidebar_sync = True
        self.sidebar.setCurrentRow(-1)
        self._sidebar_sync = False
        self.sidebar_changed(6 + row)

    def sidebar_changed(self, _row):
        if self.flatpak_mode:
            if _row == 3:
                # Cleanup is an action, not an application-list filter.
                self.show_flatpak_cleanup_dialog()
                self.sidebar.blockSignals(True)
                self.sidebar.setCurrentRow(2)
                self.sidebar.blockSignals(False)
            self.apply_table_filters()
            return
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
        size, ok = QInputDialog.getInt(self, "Font size" if self.language == "en" else "Schriftgröße", "Font size in points:" if self.language == "en" else "Schriftgröße in Punkt:", self.font_size, 8, 24, 1)
        if ok:
            self.font_size = size
            self.settings.setValue("font_size", size)
            font = QApplication.font(); font.setPointSize(size); QApplication.setFont(font)
            # QSS-Schriftgrößen überschreiben die Qt-Anwendungsfont; Theme daher
            # mit der neuen Größe erneut anwenden.
            self.apply_theme()
            self.status.setText((f"Font size set to {size} pt" if self.language == "en" else f"Schriftgröße auf {size} pt gesetzt"))
    def search_pkgs(self):
        if getattr(self, "flatpak_mode", False):
            if self.flatpak_catalog:
                self.apply_table_filters()
            else:
                self.load_flatpak_catalog()
            return
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
        self.status.setText("Paketkatalog: 0 Pakete eingelesen …" if self.language != "en" else "Package catalog: 0 packages read …")
        self.search_job = FunctionJob(self.collect_catalog, with_progress=True)
        self.search_job.progress.connect(self.catalog_progress)
        self.search_job.result.connect(self.catalog_loaded)
        self.search_job.failed.connect(self.catalog_load_failed)
        self.search_job.start()

    def catalog_progress(self, current, total):
        """Zeigt den laufenden Katalogaufbau sichtbar im Statusbereich an."""
        if self.language == "en":
            self.status.setText(f"Reading package catalog: {current:,} / {total:,} packages …")
        else:
            self.status.setText(f"Paketkatalog wird eingelesen: {current:,} / {total:,} Pakete …")

    def apply_row_filter(self, row):
        """Aktualisiert den gefilterten Modellindex ohne tausende setRowHidden-Aufrufe."""
        self.apply_table_filters()

    def _current_sidebar_category(self):
        topic_row = self.topic_sidebar.currentRow()
        return 6 + topic_row if topic_row >= 0 else max(0, self.sidebar.currentRow())

    @staticmethod
    def _flatpak_appstream_category_ids(topic_key):
        """Nur eindeutige AppStream-Kategorien verwenden, keine Sammelbegriffe."""
        mapping = {
            "amateurfunk": {"hamradio"},
            "network": {"network", "webbrowser", "chat", "email", "instantmessaging",
                        "telephony", "ircclient", "feed", "news"},
            "audio": {"audio", "music", "audioplayer", "midi", "sequencer",
                      "synthesizer", "disc burning"},
            "video": {"video", "audiovideo", "videoplayer", "tv"},
            "graphics": {"graphics", "photography", "2dgraphics", "3dgraphics",
                         "vectorgraphics", "rastergraphics", "publishing"},
            "programming": {"development", "ide", "debugger", "building",
                            "profiling", "revisioncontrol"},
            "system": {"system", "settings", "utility", "filemanager",
                       "filesystem", "terminalemulator", "monitor"},
            "security": {"security", "encryption", "passwordmanager"},
            "electronics": {"electronics", "hamradio"},
            "office": {"office", "education", "wordprocessor", "spreadsheet",
                       "presentation", "calendar", "dictionary"},
            "games": {"game", "arcadegame", "boardgame", "cardgame",
                      "logicgame", "strategygame", "actiongame"},
            "science": {"science", "geography", "astronomy", "biology",
                        "chemistry", "math", "numericalanalysis"},
        }
        return mapping.get(topic_key, set())

    def apply_table_filters(self):
        if self.flatpak_mode:
            term = self.search.text().strip().casefold()
            row_filter = self.sidebar.currentRow()
            topic_row = self.topic_sidebar.currentRow()
            rows = []
            for original_row in self.flatpak_catalog:
                row = list(original_row)
                meta = row[7] if len(row) > 7 and isinstance(row[7], dict) else {}
                if len(row) > 6:
                    row[6] = self._flatpak_localized_value(meta, "name", self.language, row[6] or row[0])
                if len(row) > 3:
                    row[3] = self._flatpak_localized_value(meta, "summary", self.language, row[3])
                row = tuple(row)
                installed = row[2] == "Installiert"
                if row_filter == 1 and not installed:
                    continue
                if row_filter == 2 and installed:
                    continue
                searchable = " ".join(str(v) for v in row[:4]) + " " + str(row[6] if len(row) > 6 else row[0])
                searchable_folded = searchable.casefold()
                if term and term not in searchable_folded:
                    continue
                if topic_row >= 0:
                    topic_key, _label_de, _label_en, pattern = TOPIC_CATEGORIES[topic_row]
                    meta = row[7] if len(row) > 7 and isinstance(row[7], dict) else {}
                    appstream_categories = {
                        str(value).strip().casefold()
                        for value in meta.get("categories", [])
                        if str(value).strip()
                    }
                    # AppStream-Kategorien werden als vollständige IDs verglichen.
                    # Allgemeine Oberbegriffe wie "Science" oder "Engineering"
                    # dürfen nicht hunderte fachfremde Anwendungen einsortieren.
                    category_match = bool(
                        appstream_categories & self._flatpak_appstream_category_ids(topic_key)
                    )
                    # Fehlen passende AppStream-Kategorien, dienen gezielte
                    # Begriffe aus Anwendungsname, ID und Beschreibung als Fallback.
                    text_match = bool(re.search(pattern, searchable_folded, re.IGNORECASE))
                    if not category_match and not text_match:
                        continue
                rows.append(row)
            rows.sort(key=lambda row: str(row[6] if len(row) > 6 else row[0]).casefold())
            self.table.package_model.replace_rows(rows, self.flatpak_queue)
            self.table.package_model.flatpak_mode = True
            self._table_mode = "flatpak"
            # Dieses Flag gehört ausschließlich zum APT-Katalog. Ein geladener
            # Flathub-Katalog darf den APT-Ladezustand nicht vortäuschen.
            self.status.setText(
                f"{len(rows)} Flatpak applications shown · Flathub" if self.language == "en"
                else f"{len(rows)} Flatpak-Anwendungen angezeigt · Flathub")
            return
        if self.catalog_cache is None or not getattr(self, "_table_catalog_ready", False):
            return
        category = self._current_sidebar_category()
        autoremove = self.catalog_cache.get("autoremove", set())
        visible = self.table.package_model.apply_filter(
            category, self.search.text().strip(), autoremove, self.queue)
        self.status.setText((f"{visible} packages shown · Full list remains in memory" if self.language == "en" else f"{visible} Pakete angezeigt · Gesamtliste bleibt im Speicher"))

    @staticmethod
    def collect_catalog(progress=None):
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
            raise RuntimeError("Paketnamen konnten nicht aus APT gelesen werden.\n" + names_out)
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
        total_names = len(names)
        if progress:
            progress(0, total_names)
        for position, name in enumerate(names, 1):
            entry = candidates.get(name.split(":", 1)[0])
            if entry is None:
                rows.append((name, "", "Nicht installiert", ""))
                if progress and (position % 250 == 0 or position == total_names):
                    progress(position, total_names)
                continue
            package = entry[1]
            installed = package.installed
            candidate = package.candidate
            is_installed = installed is not None
            selected = installed if is_installed else candidate
            version = selected.version if selected is not None else ""
            summary = (selected.summary or "") if selected is not None else ""
            # Debian-Sektion als zusätzliche, nicht sichtbare Filter-Metainformation.
            # Spiele werden anhand der Paketmetadaten erkannt, nicht über Paketnamen.
            section = (getattr(selected, "section", "") or "") if selected is not None else ""
            rows.append((name, version,
                         "Installiert" if is_installed else "Nicht installiert",
                         summary, section))
            if package.is_upgradable:
                upgradable.add(name.split(":", 1)[0])
            if package.is_auto_removable:
                autoremove.add(name.split(":", 1)[0])
            if progress and (position % 250 == 0 or position == total_names):
                progress(position, total_names)

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
        # APT-Ergebnisse nur anzeigen, wenn APT noch der aktive Modus ist.
        # Beim zwischenzeitlichen Wechsel zu Flathub bleibt dessen Tabelle erhalten.
        if not self.flatpak_mode:
            self.rows(catalog["rows"])

    def catalog_load_failed(self, error):
        self._catalog_loading = False
        if not self.flatpak_mode:
            self.status.setText("Fehler beim Laden: " + str(error))

    def search_done(self, rows):
        self.rows(rows)
        if getattr(self, "search_again", False): self.search_pkgs()
    def selected(self):
        x=self.table.selectedItems(); return x[0].data(Qt.UserRole) if x else None
    def clear_flatpak_gallery(self):
        while self.flatpak_gallery_layout.count():
            item = self.flatpak_gallery_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _screenshot_caption(self, caption, fallback=""):
        """Return one short caption in the active UI language, never a locale map."""
        value = caption
        if isinstance(value, dict):
            preferred = ("de", "de_DE", "de-DE", "C", "en", "en_US", "en-US") if self.language != "en" else (
                "en", "en_US", "en-US", "C", "de", "de_DE", "de-DE"
            )
            selected = ""
            for key in preferred:
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    selected = candidate.strip()
                    break
            if not selected:
                language_prefix = "en" if self.language == "en" else "de"
                candidate = next((v for k, v in value.items()
                                  if str(k).lower().replace("-", "_").startswith(language_prefix)
                                  and isinstance(v, str) and v.strip()), "")
                selected = candidate.strip() if candidate else ""
            value = selected
        if isinstance(value, (list, tuple)):
            value = next((v for v in value if isinstance(v, str) and v.strip()), "")
        if not isinstance(value, str):
            value = ""
        value = " ".join(value.replace("\\n", " ").split())
        # Avoid dumping serialized dictionaries or unexpectedly long metadata.
        if value.startswith("{") or value.startswith("[") or len(value) > 220:
            value = ""
        return value or fallback

    @staticmethod
    def _flatpak_localized_value(meta, field, language, fallback=""):
        """Wählt AppStream-Texte passend zur UI-Sprache mit sauberem Fallback."""
        localized = meta.get("localized", {}) if isinstance(meta, dict) else {}
        values = localized.get(field, {}) if isinstance(localized, dict) else {}
        if not isinstance(values, dict):
            values = {}
        wanted = "en" if language == "en" else "de"
        # Exakte Sprachcodes zuerst, danach regionale Varianten (de_DE, en-GB …).
        for key in (wanted, wanted + "_", wanted + "-"):
            if key in values and isinstance(values[key], str) and values[key].strip():
                return values[key].strip()
        regional = next((value for key, value in values.items()
                         if str(key).lower().replace("-", "_").startswith(wanted + "_")
                         and isinstance(value, str) and value.strip()), "")
        if regional:
            return regional.strip()
        base = meta.get(field, "") if isinstance(meta, dict) else ""
        if isinstance(base, str) and base.strip():
            return base.strip()
        # Falls die Basissprache fehlt, Englisch/Deutsch als zweite Wahl nutzen.
        alternate = "de" if wanted == "en" else "en"
        candidate = values.get(alternate, "")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        candidate = next((value for key, value in values.items()
                          if str(key).lower().replace("-", "_").startswith(alternate + "_")
                          and isinstance(value, str) and value.strip()), "")
        return candidate.strip() if candidate else fallback

    def show_flatpak_details(self, app_id):
        """Zeigt die App-Detailseite im unteren Fensterbereich."""
        row = next((item for item in self.flatpak_catalog if item[0] == app_id), None)
        self.flatpak_screenshot.clear()
        self.flatpak_screenshot.setVisible(False)
        self.details_title.setText("Application details" if self.language == "en" else "Anwendungsdetails")
        if not row:
            self.details.setPlainText(
                f"No details found for {app_id} in the Flathub catalog."
                if self.language == "en" else
                f"Keine Detaildaten für {app_id} im Flathub-Katalog gefunden."
            )
            return
        meta = row[7] if len(row) > 7 and isinstance(row[7], dict) else {}
        name = self._flatpak_localized_value(meta, "name", self.language,
                                             row[6] if len(row) > 6 else row[0])
        description = self._flatpak_localized_value(meta, "description", self.language,
                                                    meta.get("description") or row[3]) or (
            "No detailed description is available in the AppStream catalog."
            if self.language == "en" else
            "Für diese Anwendung ist keine ausführliche Beschreibung im AppStream-Katalog hinterlegt."
        )
        safe = lambda value: html.escape(str(value or ""))
        if self.language == "en":
            fields = [("App ID", row[0]), ("Version", row[1] or "Not specified"),
                      ("Status", "Installed" if row[2] == "Installiert" else "Not installed"),
                      ("Source", "Flathub / Flatpak"),
                      ("Developer", self._flatpak_localized_value(meta, "developer", self.language, meta.get("developer")) or "Not provided in AppStream metadata"),
                      ("License", meta.get("license") or "Not provided in AppStream metadata"),
                      ("Homepage", meta.get("homepage") or "Not provided in AppStream metadata")]
            details_heading = "Application details: "
            description_heading = "Description"
        else:
            fields = [("App-ID", row[0]), ("Version", row[1] or "Nicht angegeben"),
                      ("Status", row[2]), ("Quelle", "Flathub / Flatpak"),
                      ("Entwickler", self._flatpak_localized_value(meta, "developer", self.language, meta.get("developer")) or "Keine Angabe im AppStream-Katalog"),
                      ("Lizenz", meta.get("license") or "Keine Angabe im AppStream-Katalog"),
                      ("Homepage", meta.get("homepage") or "Keine Angabe im AppStream-Katalog")]
            details_heading = "Anwendungsdetails: "
            description_heading = "Beschreibung"
        table = "".join(f"<tr><td><b>{safe(k)}</b></td><td>{safe(v)}</td></tr>" for k,v in fields)
        desc_html = "".join(f"<p>{safe(part)}</p>" for part in re.split(r"\n+", description) if part.strip())
        shots = meta.get("screenshots", [])
        shot_html = ""
        # Screenshots werden ausschließlich als Bildergalerie angezeigt,
        # ohne Bildunterschriften oder zusätzliche Textlinks.
        self.details.setHtml(
            "<html><body style='font-family:sans-serif;color:#e8e8ee;'>"
            "<h2 style='color:#b99aff;'>" + safe(details_heading + name) + "</h2>"
            "<table cellpadding='5' cellspacing='0'>" + table + "</table><hr>"
            "<h3 style='color:#b99aff;'>" + safe(description_heading) + "</h3>" + desc_html +
            "</body></html>"
        )
        self.clear_flatpak_gallery()
        if shots:
            self.flatpak_gallery_scroll.setVisible(True)
            if not hasattr(self, "flatpak_image_jobs"):
                self.flatpak_image_jobs = []
            for image_url, caption in shots[:4]:
                tile = QWidget()
                tile_layout = QVBoxLayout(tile)
                tile_layout.setContentsMargins(4, 4, 4, 4)
                preview = QLabel(
                    "Loading screenshot in the background …" if self.language == "en"
                    else "Screenshot wird im Hintergrund geladen …"
                )
                preview.setAlignment(Qt.AlignCenter)
                preview.setMinimumSize(220, 145)
                preview.setMaximumSize(360, 190)
                preview.setWordWrap(True)
                preview.setStyleSheet("background:#20212a;border:1px solid #484858;border-radius:5px;padding:4px;")
                tile_layout.addWidget(preview)
                self.flatpak_gallery_layout.addWidget(tile)
                def fetch_image(url=image_url):
                    request = urllib.request.Request(url, headers={"User-Agent": "LunaPaket/0.1.41"})
                    with urllib.request.urlopen(request, timeout=12) as response:
                        return response.read(8 * 1024 * 1024)
                job = FunctionJob(fetch_image)
                def image_loaded(data, target=preview, selected_app=app_id):
                    if (not isValid(target) or not self.flatpak_mode
                            or self.selected_flatpak_id() != selected_app):
                        return
                    pixmap = QPixmap()
                    if pixmap.loadFromData(data):
                        target.setPixmap(pixmap.scaled(340, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    else:
                        target.setText("Image format not supported" if self.language == "en" else "Bildformat nicht unterstützt")
                job.result.connect(image_loaded)
                def image_failed(_error, target=preview, selected_app=app_id):
                    if (isValid(target) and self.flatpak_mode
                            and self.selected_flatpak_id() == selected_app):
                        target.setText(
                            "Image currently unavailable" if self.language == "en"
                            else "Bild derzeit nicht verfügbar"
                        )
                job.failed.connect(image_failed)
                self.flatpak_image_jobs.append(job)
                job.start()
        else:
            self.flatpak_gallery_scroll.setVisible(True)
            empty = QLabel("Für diese Anwendung sind keine Screenshots in den Flathub-Metadaten hinterlegt.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setWordWrap(True)
            self.flatpak_gallery_layout.addWidget(empty)

    def _read_apt_appstream_metadata(self, force_refresh=False):
        """Liest Debian DEP-11/AppStream-Metadaten einschließlich .yml.xz."""
        result = {}
        try:
            import yaml
        except Exception:
            return result

        import lzma
        roots = [Path("/var/lib/apt/lists"), Path("/var/cache/app-info/xmls")]
        files = []

        # Debian Trixie stable APT DEP-11 metadata kann veraltete Screenshot-
        # Hashes enthalten. Deshalb bevorzugt LunaPaket den aktuellen Katalog
        # des offiziellen Debian-AppStream-Generators. Download/Parsing laufen
        # bereits in FunctionJob und blockieren somit nicht die GUI.
        try:
            import platform, time
            os_release = {}
            try:
                for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os_release[key] = value.strip().strip('"')
            except Exception:
                pass
            suite = os_release.get("VERSION_CODENAME") or os_release.get("UBUNTU_CODENAME") or "trixie"
            machine = platform.machine().lower()
            arch = {"aarch64": "arm64", "armv8l": "arm64", "x86_64": "amd64", "i386": "i386", "i686": "i386"}.get(machine, machine)
            metadata_cache_dir = Path.home() / ".cache" / "LunaPaket"
            metadata_cache_dir.mkdir(parents=True, exist_ok=True)
            metadata_cache_file = metadata_cache_dir / f"apt-appstream-index-v2-{suite}-{arch}.json"
            # Der bereits aufbereitete Index wird zuerst von der Festplatte
            # gelesen. So muss der große AppStream-Katalog nicht bei jedem
            # Programmstart erneut heruntergeladen und vollständig geparst werden.
            retention_days = int(self.settings.value("cache/appstream_retention_days", 7))
            index_is_fresh = (
                metadata_cache_file.exists()
                and (retention_days == 0 or time.time() - metadata_cache_file.stat().st_mtime < retention_days * 86400)
            )
            if index_is_fresh and not force_refresh:
                try:
                    cached_index = json.loads(metadata_cache_file.read_text(encoding="utf-8"))
                    if isinstance(cached_index, dict):
                        return cached_index
                except Exception:
                    pass
            cache_dir = metadata_cache_dir / "appstream"
            cache_dir.mkdir(parents=True, exist_ok=True)
            for component in ("main", "contrib", "non-free", "non-free-firmware"):
                cache_file = cache_dir / f"{suite}-{component}-{arch}.yml.gz"
                component_cache_expired = (
                    force_refresh
                    or not cache_file.exists()
                    or (retention_days != 0 and time.time() - cache_file.stat().st_mtime > retention_days * 86400)
                )
                if component_cache_expired:
                    url = f"https://appstream.debian.org/data/{suite}/{component}/Components-{arch}.yml.gz"
                    try:
                        request = urllib.request.Request(url, headers={"User-Agent": "LunaPaket/0.1.41 AppStream"})
                        with urllib.request.urlopen(request, timeout=25) as response:
                            payload = response.read(40 * 1024 * 1024)
                        if payload[:2] == b"\x1f\x8b":
                            temp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
                            temp_file.write_bytes(payload)
                            temp_file.replace(cache_file)
                    except Exception:
                        pass
                if cache_file.exists():
                    files.append(cache_file)
        except Exception:
            pass

        for root in roots:
            if root.exists():
                files.extend(root.glob("*dep11*Components*.yml*"))
                files.extend(root.glob("*Components*.yml*"))
                files.extend(root.glob("*.xml.gz"))
                files.extend(root.glob("*.xml"))
        for path in sorted(set(files), key=lambda item: "LunaPaket" in str(item)):
            try:
                if path.name.endswith(".xz"):
                    opener = lzma.open
                elif path.name.endswith(".gz"):
                    opener = gzip.open
                else:
                    opener = open
                with opener(path, "rt", encoding="utf-8", errors="replace") as stream:
                    if path.name.endswith((".xml", ".xml.gz")):
                        for _event, elem in ET.iterparse(stream, events=("end",)):
                            if elem.tag.rsplit("}", 1)[-1] != "component":
                                continue
                            package_names = []
                            for node in elem.iter():
                                if node.tag.rsplit("}", 1)[-1] in ("pkgname", "package"):
                                    value = (node.text or "").strip()
                                    if value:
                                        package_names.append(value)
                            screenshots = []
                            for node in elem.iter():
                                if node.tag.rsplit("}", 1)[-1] == "screenshot":
                                    for sub in node.iter():
                                        if sub.tag.rsplit("}", 1)[-1] == "image" and sub.text:
                                            screenshots.append((sub.text.strip(), ""))
                                            break
                            for package_name in package_names:
                                result[package_name] = {"screenshots": screenshots}
                            elem.clear()
                        continue

                    documents = [doc for doc in yaml.safe_load_all(stream) if isinstance(doc, dict)]
                base_url = ""
                for doc in documents:
                    base_url = (doc.get("MediaBaseUrl") or doc.get("media_base_url") or base_url)
                for doc in documents:
                    components = doc.get("Components") or doc.get("components")
                    if isinstance(components, list):
                        component_list = [item for item in components if isinstance(item, dict)]
                    else:
                        # DEP-11 legt Komponenten normalerweise als einzelne YAML-Dokumente ab.
                        component_list = [doc] if (doc.get("Package") or doc.get("Pkgname") or doc.get("package")) else []
                    for component in component_list:
                        package_names = component.get("Package") or component.get("Pkgname") or component.get("package") or []
                        if isinstance(package_names, str):
                            package_names = [package_names]
                        screenshots = []
                        for shot in component.get("Screenshots") or component.get("screenshots") or []:
                            if not isinstance(shot, dict):
                                continue
                            source = (shot.get("source-image") or shot.get("SourceImage") or
                                      shot.get("source") or shot.get("Source") or {})
                            url = source.get("url") or source.get("Url") or "" if isinstance(source, dict) else str(source or "")
                            if not url:
                                thumbs = shot.get("thumbnails") or shot.get("Thumbnails") or []
                                if thumbs and isinstance(thumbs[0], dict):
                                    url = thumbs[0].get("url") or thumbs[0].get("Url") or ""
                            if url:
                                if url.startswith("/") and base_url:
                                    url = base_url.rstrip("/") + url
                                elif not url.startswith(("http://", "https://")) and base_url:
                                    url = base_url.rstrip("/") + "/" + url.lstrip("/")
                                screenshots.append((url, shot.get("caption") or ""))
                        for package_name in package_names:
                            result[str(package_name)] = {"screenshots": screenshots}
            except Exception:
                continue
        # Index atomar speichern, damit bei einem Abbruch keine beschädigte
        # Cache-Datei zurückbleibt.
        try:
            if "metadata_cache_file" in locals():
                temp_index = metadata_cache_file.with_suffix(".json.tmp")
                temp_index.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
                temp_index.replace(metadata_cache_file)
        except Exception:
            pass
        return result

    @staticmethod
    def _fetch_apt_screenshot(image_url):
        """Liest ein APT-Bild zuerst aus dem lokalen Cache, sonst aus dem Netz."""
        cache_dir = Path.home() / ".cache" / "LunaPaket" / "apt-screenshots"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / (hashlib.sha256(image_url.encode("utf-8")).hexdigest() + ".img")
        if cache_file.is_file() and cache_file.stat().st_size:
            try:
                data = cache_file.read_bytes()
                image = QImage.fromData(data)
                if not image.isNull():
                    return image.scaled(340, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except Exception:
                pass
            try:
                cache_file.unlink()
            except OSError:
                pass

        request = urllib.request.Request(image_url, headers={"User-Agent": "LunaPaket/0.1.41"})
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(8 * 1024 * 1024)
        image = QImage.fromData(data)
        if image.isNull():
            raise ValueError("Bildformat nicht unterstützt")
        temp_file = cache_file.with_suffix(".img.tmp")
        temp_file.write_bytes(data)
        temp_file.replace(cache_file)
        return image.scaled(340, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def show_apt_screenshots(self, package_name):
        """Zeigt vorhandene Debian-AppStream-Screenshots rechts neben den APT-Details."""
        self.clear_flatpak_gallery()
        self.flatpak_gallery_scroll.setVisible(True)
        cache = getattr(self, "_apt_appstream_cache", None)
        if cache is None:
            self.flatpak_gallery_layout.addWidget(QLabel("Debian-AppStream-Bilder werden gesucht …"))
            self.apt_appstream_job = FunctionJob(self._read_apt_appstream_metadata)
            def metadata_ready(data, name=package_name):
                self._apt_appstream_cache = data
                if self.selected() == name and not self.flatpak_mode:
                    self.show_apt_screenshots(name)
            self.apt_appstream_job.result.connect(metadata_ready)
            self.apt_appstream_job.failed.connect(
                lambda _e, name=package_name:
                self._show_apt_gallery_empty(
                    "Debian does not provide images for this package."
                    if self.language == "en" else
                    "Debian stellt für dieses Paket keine Bilder bereit."
                ) if not self.flatpak_mode and self.selected() == name else None
            )
            self.apt_appstream_job.start()
            return

        meta = cache.get(package_name, {})
        shots = meta.get("screenshots", [])
        if not shots:
            self._show_apt_gallery_empty(
                "Für dieses APT-Paket sind keine Screenshots in den lokalen Debian-AppStream-Metadaten vorhanden."
            )
            return

        if not hasattr(self, "apt_image_jobs"):
            self.apt_image_jobs = []
        for image_url, caption in shots[:4]:
            tile = QWidget()
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(4, 4, 4, 4)
            preview = QLabel("Lokaler Bildcache wird geprüft …" if self.language == "de" else "Checking local image cache …")
            preview.setAlignment(Qt.AlignCenter)
            preview.setMinimumSize(220, 145)
            preview.setMaximumSize(360, 190)
            preview.setWordWrap(True)
            preview.setStyleSheet("background:#20212a;border:1px solid #484858;border-radius:5px;padding:4px;")
            tile_layout.addWidget(preview)
            self.flatpak_gallery_layout.addWidget(tile)
            def fetch_image(url=image_url):
                return self._fetch_apt_screenshot(url)
            job = FunctionJob(fetch_image)
            def image_loaded(data, target=preview, selected_package=package_name):
                if (not isValid(target) or self.flatpak_mode or self.selected() != selected_package):
                    return
                if isinstance(data, QImage) and not data.isNull():
                    # Dekodieren und Skalieren geschieht bereits im Worker;
                    # der GUI-Thread übernimmt nur noch das Anzeigen.
                    target.setPixmap(QPixmap.fromImage(data))
                else:
                    target.setText("Bildformat nicht unterstützt")
            job.result.connect(image_loaded)
            def image_failed(_error, target=preview, selected_package=package_name):
                if isValid(target) and not self.flatpak_mode and self.selected() == selected_package:
                    target.setText(
                        "Image currently unavailable" if self.language == "en"
                        else "Bild derzeit nicht verfügbar"
                    )
            job.failed.connect(image_failed)
            self.apt_image_jobs.append(job)
            job.start()

    def _show_apt_gallery_empty(self, message):
        self.clear_flatpak_gallery()
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        self.flatpak_gallery_layout.addWidget(label)

    def details_for_selected(self):
        if self.flatpak_mode:
            app_id = self.selected_flatpak_id()
            if app_id:
                self.show_flatpak_details(app_id)
            return
        self.details_title.setText("Paketdetails")
        n=self.selected()
        if not n or self.table.currentColumn() == 0:
            self.clear_flatpak_gallery()
            self._show_apt_gallery_empty("Wähle ein APT-Paket aus. Verfügbare Debian-AppStream-Bilder erscheinen hier.")
            return
        self.show_apt_screenshots(n)
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
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.setCurrentIndex(index)
        self.table.selectRow(index.row())
        if self.flatpak_mode:
            app_id = self.selected_flatpak_id()
            if not app_id:
                return
            row = next((item for item in self.flatpak_catalog if item[0] == app_id), None)
            if not row:
                return
            queued = self.flatpak_queue.get(app_id)
            installed = row[2] == "Installiert"
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { padding: 5px; }
                QMenu::item { padding: 8px 30px 8px 12px; min-height: 22px; margin: 1px 0px; }
                QMenu::separator { height: 1px; margin: 5px 8px; }
            """)
            if queued:
                menu.addAction("Vormerkung aufheben", lambda: self.queue_flatpak_action(app_id, None))
            elif installed:
                menu.addAction("Entfernen vormerken", lambda: self.queue_flatpak_action(app_id, "remove"))
            else:
                menu.addAction("Installieren vormerken", lambda: self.queue_flatpak_action(app_id, "install"))
            menu.addSeparator()
            menu.addAction("Anwendungsdetails anzeigen", lambda checked=False, app=app_id: self.show_flatpak_details(app))
            menu.addAction("App-ID kopieren", lambda: QApplication.clipboard().setText(app_id))
            menu.exec(self.table.viewport().mapToGlobal(pos))
            return
        name = self.selected()
        if not name:
            return
        menu = QMenu(self)
        # Größere, gut treffbare Menüzeilen – die gewohnte native QMenu-
        # Darstellung bleibt erhalten, nur die Abstände werden verbessert.
        menu.setStyleSheet("""
            QMenu {
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 30px 8px 12px;
                min-height: 22px;
                margin: 1px 0px;
            }
            QMenu::separator {
                height: 1px;
                margin: 5px 8px;
            }
        """)
        menu.addAction("Queue for installation" if self.language == "en" else "Installieren vormerken", lambda: self.mark("install"))
        menu.addAction("Queue for reinstallation" if self.language == "en" else "Neu installieren vormerken", lambda: self.mark("reinstall"))
        menu.addAction("Queue for removal" if self.language == "en" else "Entfernen vormerken", lambda: self.mark("remove"))
        menu.addAction("Queue for purge" if self.language == "en" else "Vollständig entfernen (Purge) vormerken", lambda: self.mark("purge"))
        menu.addSeparator()
        menu.addAction("Select version …" if self.language == "en" else "Version auswählen …", self.choose_version)
        held = self.package_is_held(name)
        menu.addAction(("Queue unhold" if held else "Queue hold") if self.language == "en" else ("Versionssperre aufheben vormerken" if held else "Version sperren vormerken"),
                       lambda: self.mark("unhold" if held else "hold"))
        menu.addSeparator()
        menu.addAction("Dependencies and conflicts …" if self.language == "en" else "Abhängigkeiten und Konflikte …", self.show_dependency_analysis)
        menu.addAction("Properties …" if self.language == "en" else "Eigenschaften …", self.show_properties)
        menu.addAction("Show installed files …" if self.language == "en" else "Installierte Dateien anzeigen …", self.show_package_files)
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
        version, ok = QInputDialog.getItem(self, "Select version" if self.language == "en" else "Version auswählen", (f"Version for {name}:" if self.language == "en" else f"Version für {name}:"), versions, 0, False)
        if ok and version:
            self.queue[name] = "version:" + version
            self.update_queue_label()
            self.refresh_checkbox(name)

    def update_queue_label(self):
        active_queue = self.flatpak_queue if getattr(self, "flatpak_mode", False) else self.queue
        if not active_queue:
            self.queue_label.setText("No queued changes" if self.language == "en" else "Keine vorgemerkten Änderungen")
        else:
            labels_de = {"install":"Installieren", "reinstall":"Neu installieren", "remove":"Entfernen", "purge":"Vollständig entfernen", "hold":"Version sperren", "unhold":"Versionssperre aufheben"}
            labels_en = {"install":"Install", "reinstall":"Reinstall", "remove":"Remove", "purge":"Purge", "hold":"Hold", "unhold":"Unhold"}
            labels = labels_en if self.language == "en" else labels_de
            prefix = "Queued: " if self.language == "en" else "Vorgemerkt: "
            self.queue_label.setText(prefix + ", ".join(f"{k} ({labels.get(v, v)})" for k, v in active_queue.items()))

    def show_properties(self):
        name = self.selected()
        if not name:
            return
        _, out = cmd(["apt-cache", "show", name])
        english = self.language == "en"
        d = QDialog(self); d.setWindowTitle(("Package properties – " if english else "Paketeigenschaften – ") + name); d.resize(820, 560)
        lay = QVBoxLayout(d); t = QTextEdit(); t.setReadOnly(True); t.setPlainText(out or ("No properties available." if english else "Keine Eigenschaften verfügbar.")); lay.addWidget(t)
        bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(d.reject); bb.accepted.connect(d.accept); lay.addWidget(bb); d.exec()

    def show_package_files(self):
        name = self.selected()
        if not name:
            return
        r, out = cmd(["dpkg", "-L", name])
        english = self.language == "en"
        if r != 0:
            QMessageBox.information(self, "Installed files" if english else "Installierte Dateien", ("The package is not installed or dpkg could not read its file list.\n\n" if english else "Das Paket ist nicht installiert oder dpkg konnte die Dateiliste nicht lesen.\n\n") + out)
            return
        d = QDialog(self); d.setWindowTitle(("Installed files – " if english else "Installierte Dateien – ") + name); d.resize(760, 520)
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

    def _flatpak_command_for_action(self, app_id, action):
        row = next((item for item in self.flatpak_catalog if item and item[0] == app_id), None)
        meta = row[7] if row and len(row) > 7 and isinstance(row[7], dict) else {}
        if action == "install":
            scope = meta.get("remote_scope", "--user")
            args = ["flatpak", "install", scope, "-y", "flathub", app_id]
            return privileged(args) if scope == "--system" else args
        # Flatpak selects the installed scope itself when only one exists.
        # Do not force --user for a system-installed application.
        return ["flatpak", "uninstall", "-y", app_id]

    def apply_queued_changes(self):
        """Führt ausschließlich die ausdrücklich vorgemerkten Paketaktionen aus."""
        if self.flatpak_mode:
            if not self.flatpak_queue:
                QMessageBox.information(
                    self,
                    "Queued changes" if self.language == "en" else "Vorgemerkte Änderungen",
                    "There are no queued Flatpak changes." if self.language == "en"
                    else "Es sind keine Flatpak-Änderungen vorgemerkt."
                )
                return
            actions = dict(self.flatpak_queue)
            app_ids = list(actions)
            self.status.setText(
                "Applying queued Flatpak changes …" if self.language == "en"
                else "Vorgemerkte Flatpak-Änderungen werden angewendet …"
            )
            self.set_busy(True)
            def run_flatpak_queue():
                outputs = []
                failures = []
                for app_id, action in actions.items():
                    args = self._flatpak_command_for_action(app_id, action)
                    try:
                        rc, output = cmd(args)
                    except Exception as error:
                        rc, output = 1, str(error)
                    outputs.append(output or f"{app_id}: exit {rc}")
                    if rc != 0:
                        failures.append(app_id)
                return failures, "\n\n".join(outputs)
            self.flatpak_queue_job = FunctionJob(run_flatpak_queue)
            def finished(result):
                failures, output = result
                self.set_busy(False)
                self.details.setPlainText(output)
                for app_id in app_ids:
                    if app_id not in failures:
                        self.flatpak_queue.pop(app_id, None)
                self.update_queue_label()
                self.load_flatpak_catalog()
                if failures:
                    self.status.setText(
                        ("Flatpak: Some queued actions failed: " if self.language == "en"
                         else "Flatpak: Einige vorgemerkte Aktionen sind fehlgeschlagen: ")
                        + ", ".join(failures)
                    )
                else:
                    self.status.setText(
                        "All queued Flatpak changes have been applied." if self.language == "en"
                        else "Alle vorgemerkten Flatpak-Änderungen wurden ausgeführt."
                    )
            self.flatpak_queue_job.result.connect(finished)
            self.flatpak_queue_job.failed.connect(
                lambda error: (
                    self.set_busy(False),
                    self.status.setText(
                        ("Flatpak error: " if self.language == "en" else "Flatpak-Fehler: ") + str(error)
                    )
                )
            )
            self.flatpak_queue_job.start()
            return
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
        if self._current_sidebar_category() == 3:
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

    def check_flatpak_updates(self):
        """Sucht App- und Runtime-Updates in Benutzer- und System-Flatpak."""
        english = self.language == "en"
        if not shutil.which("flatpak"):
            QMessageBox.warning(self, "Flatpak", "Flatpak is not installed." if english else "Flatpak ist nicht installiert.")
            return
        self.flatpak_update_btn.setEnabled(False)
        self.status.setText("Checking Flathub updates …" if english else "Flathub-Updates werden gesucht …")

        def scan():
            found = []
            errors = []
            for scope, flag in (("user", "--user"), ("system", "--system")):
                # remote-ls erwartet das Remote als Positionsargument. Ohne
                # "flathub" wird die Update-Abfrage nicht zuverlässig ausgeführt.
                flatpak_args = ["flatpak", "remote-ls", "--updates", "--columns=ref", flag, "flathub"]
                rc, output = flatpak_user_cmd(flatpak_args) if scope == "user" else cmd(flatpak_args)
                if rc != 0:
                    errors.append((scope, output.strip()))
                    continue
                for line in output.splitlines():
                    ref = line.strip()
                    if not ref or ref.lower() == "ref" or not (ref.startswith("app/") or ref.startswith("runtime/")):
                        continue
                    found.append((scope, ref))
            # Ein Ref kann in beiden Installationen vorkommen und bleibt dann getrennt auswählbar.
            return sorted(set(found), key=lambda item: (item[0], item[1])), errors

        self.flatpak_update_scan_job = FunctionJob(scan)
        def ready(result):
            self.flatpak_update_btn.setEnabled(True)
            updates, errors = result
            if not updates:
                self.status.setText("No Flatpak updates available." if english else "Keine Flatpak-Updates verfügbar.")
                message = "No application or runtime updates are available." if english else "Es sind keine App- oder Runtime-Updates verfügbar."
                if errors:
                    message += "\n\n" + ("Some installation scopes could not be checked:" if english else "Einige Installationsbereiche konnten nicht geprüft werden:")
                    message += "\n" + "\n".join(f"{scope}: {output}" for scope, output in errors)
                    QMessageBox.warning(self, "Flatpak", message)
                else:
                    QMessageBox.information(self, "Flatpak", message)
                return

            dlg = QDialog(self)
            dlg.setWindowTitle("Available Flatpak updates" if english else "Verfügbare Flatpak-Updates")
            dlg.resize(760, 560)
            layout = QVBoxLayout(dlg)
            update_count = len(updates)
            if english:
                intro_text = ("1 update found. Applications and runtimes are included." if update_count == 1 else
                              f"{update_count} updates found. Applications and runtimes are included.")
            else:
                intro_text = ("1 Update gefunden. Anwendungen und Laufzeitumgebungen sind enthalten." if update_count == 1 else
                              f"{update_count} Updates gefunden. Anwendungen und Laufzeitumgebungen sind enthalten.")
            intro = QLabel(intro_text)
            layout.addWidget(intro)
            select_all = QCheckBox("Select all" if english else "Alle auswählen")
            select_all.setChecked(True)
            layout.addWidget(select_all)
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
            content = QWidget(); rows_layout = QVBoxLayout(content)
            checks = []
            for scope, ref in updates:
                kind = "Runtime" if ref.startswith("runtime/") else "Application"
                kind_label = ("Runtime" if english else "Laufzeit") if kind == "Runtime" else ("Application" if english else "Anwendung")
                scope_label = ("User" if scope == "user" else "System") if english else ("Benutzer" if scope == "user" else "System")
                check = QCheckBox(f"{ref.split('/')[1]}   ·   {kind_label}   ·   {scope_label}")
                check.setChecked(True)
                check.setProperty("flatpak_scope", scope)
                check.setProperty("flatpak_ref", ref)
                checks.append(check); rows_layout.addWidget(check)
            rows_layout.addStretch(1)
            scroll.setWidget(content); layout.addWidget(scroll, 1)
            select_all.toggled.connect(lambda checked: [item.setChecked(checked) for item in checks])
            buttons = QDialogButtonBox()
            update_selected = buttons.addButton("Update selected" if english else "Ausgewählte aktualisieren", QDialogButtonBox.AcceptRole)
            update_all = buttons.addButton("Update all" if english else "Alle aktualisieren", QDialogButtonBox.ActionRole)
            close_btn = buttons.addButton(QDialogButtonBox.Close)
            close_btn.setText("Close" if english else "Schließen")
            buttons.rejected.connect(dlg.reject)
            close_btn.clicked.connect(dlg.reject)
            layout.addWidget(buttons)

            def start_updates(all_items=False):
                selected = updates if all_items else [(item.property("flatpak_scope"), item.property("flatpak_ref")) for item in checks if item.isChecked()]
                if not selected:
                    QMessageBox.information(dlg, "Flatpak", "Select at least one update." if english else "Bitte mindestens ein Update auswählen.")
                    return
                question = (f"Install {len(selected)} selected update(s)?" if english else f"{len(selected)} ausgewählte Updates installieren?")
                confirm = QMessageBox(dlg)
                confirm.setIcon(QMessageBox.Question)
                confirm.setWindowTitle("Flatpak")
                confirm.setText(question)
                confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                confirm.setDefaultButton(QMessageBox.No)
                yes_button = confirm.button(QMessageBox.Yes)
                no_button = confirm.button(QMessageBox.No)
                if english:
                    yes_button.setText("Yes")
                    no_button.setText("No")
                else:
                    yes_button.setText("Ja")
                    no_button.setText("Nein")
                if confirm.exec() != QMessageBox.Yes:
                    return
                dlg.accept()
                self.flatpak_update_btn.setEnabled(False)
                self.set_busy(True)
                self.status.setText("Installing Flatpak updates …" if english else "Flatpak-Updates werden installiert …")
                def install():
                    results = []
                    for scope, ref in selected:
                        args = ["flatpak", "update", "-y", "--noninteractive", scope_flag(scope), ref]
                        rc, output = cmd(privileged(args)) if scope == "system" else flatpak_user_cmd(args)
                        results.append((scope, ref, rc, output))
                    return results
                self.flatpak_update_job = FunctionJob(install)
                def installed(results):
                    self.set_busy(False); self.flatpak_update_btn.setEnabled(True)
                    failures = [(scope, ref, output) for scope, ref, rc, output in results if rc != 0]
                    details = "\n\n".join(output.strip() or f"{ref}: exit {rc}" for scope, ref, rc, output in results)
                    self.details.setPlainText(details)
                    if failures:
                        self.status.setText("Some Flatpak updates failed." if english else "Einige Flatpak-Updates sind fehlgeschlagen.")
                        QMessageBox.warning(self, "Flatpak", ("Some updates could not be installed:" if english else "Einige Updates konnten nicht installiert werden:") + "\n\n" + "\n".join(ref for _scope, ref, _output in failures))
                    else:
                        self.status.setText("Flatpak updates completed." if english else "Flatpak-Updates abgeschlossen.")
                        QMessageBox.information(self, "Flatpak", "All selected Flatpak updates were installed." if english else "Alle ausgewählten Flatpak-Updates wurden installiert.")
                    self.load_flatpak_catalog()
                self.flatpak_update_job.result.connect(installed)
                self.flatpak_update_job.failed.connect(lambda error: (self.set_busy(False), self.flatpak_update_btn.setEnabled(True), QMessageBox.critical(self, "Flatpak", str(error))))
                self.flatpak_update_job.start()

            def scope_flag(scope):
                return "--user" if scope == "user" else "--system"
            update_selected.clicked.connect(lambda: start_updates(False))
            update_all.clicked.connect(lambda: start_updates(True))
            if errors:
                intro.setText(intro.text() + "\n" + ("Warning: one installation scope could not be checked." if english else "Hinweis: Ein Installationsbereich konnte nicht geprüft werden."))
            self.status.setText((f"{len(updates)} Flatpak update(s) available." if english else f"{len(updates)} Flatpak-Updates verfügbar."))
            dlg.exec()
        self.flatpak_update_scan_job.result.connect(ready)
        self.flatpak_update_scan_job.failed.connect(lambda error: (self.flatpak_update_btn.setEnabled(True), self.status.setText("Flatpak update check failed" if english else "Flatpak-Updateprüfung fehlgeschlagen"), QMessageBox.warning(self, "Flatpak", str(error))))
        self.flatpak_update_scan_job.start()

    def show_flatpak_cleanup_dialog(self):
        """Findet ungenutzte Flatpak-Runtimes getrennt in Benutzer- und Systeminstallation."""
        if not shutil.which("flatpak"):
            QMessageBox.warning(
                self, "Flatpak",
                "Flatpak is not installed." if self.language == "en"
                else "Flatpak ist nicht installiert."
            )
            return

        scopes = (
            ["User installation", "System installation"] if self.language == "en"
            else ["Benutzerinstallation", "Systeminstallation"]
        )
        scope, accepted = QInputDialog.getItem(
            self,
            "Flatpak cleanup" if self.language == "en" else "Flatpak aufräumen",
            "Which installation should be checked?" if self.language == "en"
            else "Welche Installation soll geprüft werden?",
            scopes, 0, False
        )
        if not accepted:
            return
        system_scope = scope == scopes[1]
        scope_flag = "--system" if system_scope else "--user"
        scope_name = (
            ("system installation" if self.language == "en" else "Systeminstallation")
            if system_scope else
            ("user installation" if self.language == "en" else "Benutzerinstallation")
        )

        self.status.setText(
            (f"Checking unused runtimes in the {scope_name} …" if self.language == "en"
             else f"Suche nach ungenutzten Runtimes in der {scope_name} …")
        )
        self.set_busy(True)

        def preview():
            # Read-only preview: explicitly decline Flatpak's own confirmation prompt.
            result = subprocess.run(
                ["flatpak", "uninstall", "--unused", scope_flag],
                input="n\\n", text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=180
            )
            return result.returncode, result.stdout

        self.flatpak_cleanup_preview_job = FunctionJob(preview)

        def preview_ready(result):
            self.set_busy(False)
            rc, output = result
            if rc not in (0, 1) and not output.strip():
                QMessageBox.warning(
                    self, "Flatpak",
                    ("Could not check unused runtimes.\\n\\n" if self.language == "en"
                     else "Ungenutzte Runtimes konnten nicht geprüft werden.\\n\\n") + output
                )
                return
            refs = list(dict.fromkeys(re.findall(r"(?m)^\\s*(runtime/[^\\s]+)", output)))
            if not refs:
                QMessageBox.information(
                    self,
                    "Cleanup" if self.language == "en" else "Aufräumen",
                    (f"No unused runtimes were found in the {scope_name}." if self.language == "en"
                     else f"In der {scope_name} wurden keine ungenutzten Runtimes gefunden.")
                )
                self.status.setText(
                    ("No unused runtimes found." if self.language == "en"
                     else "Keine ungenutzten Runtimes gefunden.")
                )
                return

            dlg = QDialog(self)
            dlg.setWindowTitle(
                "Confirm Flatpak cleanup" if self.language == "en"
                else "Flatpak-Aufräumen bestätigen"
            )
            dlg.resize(680, 440)
            layout = QVBoxLayout(dlg)
            intro = QLabel(
                (f"{len(refs)} unused runtimes/extensions in the {scope_name} can be removed. "
                 "Installed applications and app data will be kept.")
                if self.language == "en"
                else (f"{len(refs)} ungenutzte Runtimes/Erweiterungen in der {scope_name} können entfernt werden. "
                      "Installierte Anwendungen und App-Daten bleiben erhalten.")
            )
            intro.setWordWrap(True)
            layout.addWidget(intro)
            listing = QListWidget()
            listing.addItems(refs)
            listing.setSelectionMode(QAbstractItemView.NoSelection)
            layout.addWidget(listing, 1)
            buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
            buttons.button(QDialogButtonBox.Ok).setText(
                "Clean up now" if self.language == "en" else "Jetzt aufräumen"
            )
            buttons.button(QDialogButtonBox.Cancel).setText(
                "Cancel" if self.language == "en" else "Abbrechen"
            )
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)
            layout.addWidget(buttons)
            if dlg.exec() != QDialog.Accepted:
                self.status.setText(
                    "Cleanup cancelled – nothing was removed." if self.language == "en"
                    else "Aufräumen abgebrochen – nichts wurde entfernt."
                )
                return

            self.status.setText(
                (f"Removing unused runtimes from the {scope_name} …" if self.language == "en"
                 else f"Ungenutzte Runtimes aus der {scope_name} werden entfernt …")
            )
            self.set_busy(True)
            self.flatpak_cleanup_job = FunctionJob(
                lambda: cmd(["flatpak", "uninstall", "--unused", scope_flag, "--assumeyes"])
            )

            def cleanup_finished(cleanup_result):
                self.set_busy(False)
                cleanup_rc, cleanup_output = cleanup_result
                self.details.setPlainText(cleanup_output)
                if cleanup_rc == 0:
                    self.status.setText(
                        (f"Removed unused runtimes from the {scope_name}." if self.language == "en"
                         else f"Ungenutzte Runtimes aus der {scope_name} entfernt.")
                    )
                else:
                    self.status.setText(
                        ("Flatpak cleanup failed: " if self.language == "en"
                         else "Flatpak-Aufräumen fehlgeschlagen: ") + cleanup_output
                    )

            self.flatpak_cleanup_job.result.connect(cleanup_finished)
            self.flatpak_cleanup_job.failed.connect(
                lambda error: (
                    self.set_busy(False),
                    self.status.setText(
                        ("Flatpak cleanup error: " if self.language == "en"
                         else "Flatpak-Aufräumfehler: ") + str(error)
                    )
                )
            )
            self.flatpak_cleanup_job.start()

        self.flatpak_cleanup_preview_job.result.connect(preview_ready)
        self.flatpak_cleanup_preview_job.failed.connect(
            lambda error: (
                self.set_busy(False),
                self.status.setText(
                    ("Could not check Flatpak cleanup: " if self.language == "en"
                     else "Flatpak-Aufräumen konnte nicht geprüft werden: ") + str(error)
                )
            )
        )
        self.flatpak_cleanup_preview_job.start()

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
        self.translate_dialog(dlg)
        if dlg.exec() != QDialog.Accepted:
            self.status.setText("Aufräumen abgebrochen – keine Pakete entfernt")
            return
        # Beibehalten: die tatsächlich funktionierende APT-Autoremove-Ausführung.
        self.run_action_job(privileged(["apt", "-o", "APT::Status-Fd=2", "-y", "autoremove"]),
                            "Aufräumen", f"APT entfernt nicht mehr benötigte Pakete ({len(candidates)} gefunden).",
                            len(candidates))

    def mark(self,action):
        n=self.selected()
        if not n: QMessageBox.information(self,"LunaPaket","Bitte zuerst ein Paket auswählen."); return
        self.queue[n]=action; self.update_queue_label(); self.refresh_checkbox(n)
    def refresh_checkbox(self, name):
        model=self.table.package_model; installed=False
        for row,values in enumerate(model.rows):
            if values and values[0]==name: installed=model.installed[row]; break
        action=self.queue.get(name, ""); checked=installed
        if action in ("install","reinstall") or action.startswith("version:"): checked=True
        elif action in ("remove","purge"): checked=False
        # Das Modell-Signal darf checkbox_changed nicht als Benutzereingabe
        # interpretieren: sonst wird "purge" unmittelbar zu "remove".
        self._syncing_queue_checkbox = True
        try:
            model.set_checked_for_name(name,checked)
        finally:
            self._syncing_queue_checkbox = False

    def clear_queue(self):
        if self.flatpak_mode:
            self.flatpak_queue.clear()
            self.update_queue_label()
            model = self.table.package_model
            model.checked = list(model.installed)
            if model.rowCount():
                model.dataChanged.emit(model.index(0, 0), model.index(model.rowCount()-1, 0), [Qt.CheckStateRole])
            return
        self.queue.clear(); self.update_queue_label()
        model=self.table.package_model; model.checked=list(model.installed)
        if model.rowCount(): model.dataChanged.emit(model.index(0,0),model.index(model.rowCount()-1,0),[Qt.CheckStateRole])

    def commit(self):
        if not self.queue:
            return
        actions = dict(self.queue)
        self.status.setText("Checking changes in the background …" if self.language == "en" else "Änderungen werden im Hintergrund geprüft …")
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
                apt_commands.append(["apt", "-s"] + apt_args + names)
        versions = [(n, a.split(":", 1)[1]) for n, a in actions.items() if a.startswith("version:")]
        for n, version in versions:
            apt_commands.append(["apt", "-s", "install", f"{n}={version}"])
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
        en = self.language == "en"
        dlg.setWindowTitle("Confirm package actions" if en else "Paketaktionen bestätigen")
        dlg.resize(800, 560)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Review the planned actions. Uncheck items to exclude individual actions." if en else "Prüfe die geplanten Aktionen. Entferne Häkchen, um einzelne Aktionen abzuwählen."))
        listing = QListWidget()
        labels = ({"install":"Install", "reinstall":"Reinstall", "remove":"Remove",
                   "purge":"Purge", "hold":"Hold version", "unhold":"Release version hold"} if en else
                  {"install":"Installieren", "reinstall":"Neu installieren", "remove":"Entfernen",
                   "purge":"Vollständig entfernen", "hold":"Version sperren", "unhold":"Versionssperre aufheben"})
        for name, action in actions.items():
            label = f"{labels.get(action, action)}: {name}"
            if action.startswith("version:"):
                label = (f"Install version {action.split(':', 1)[1]}: {name}" if en else
                         f"Version {action.split(':', 1)[1]} installieren: {name}")
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            listing.addItem(item)
        layout.addWidget(listing, 2)
        layout.addWidget(QLabel("APT check (simulation; no changes have been made):" if en else "APT-Prüfung (Simulation, noch keine Änderungen ausgeführt):"))
        details = QTextEdit()
        details.setReadOnly(True)
        details.setPlainText(preview)
        layout.addWidget(details, 1)
        auto_close = QCheckBox("Close window after successful action" if en else "Fenster nach erfolgreicher Aktion schließen")
        auto_close.setChecked(True)
        layout.addWidget(auto_close)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Run now" if en else "Jetzt ausführen")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancel" if en else "Abbrechen")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)
        self.translate_dialog(dlg)
        if dlg.exec() != QDialog.Accepted:
            self.status.setText("Queued changes have been kept" if en else "Vorgemerkte Änderungen bleiben erhalten")
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
                commands.append(["apt", "-o", "APT::Status-Fd=2", "-y"] + apt_args + names)
        commands.extend([["apt", "-o", "APT::Status-Fd=2", "-y", "install", f"{n}={version}"] for n, version in versions])
        commands.extend([["apt-mark", a, n] for n, a in actions.items() if a in ("hold", "unhold")])
        if not commands:
            return
        has_installation = any(a in ("install", "reinstall") or a.startswith("version:") for a in actions.values())
        if has_installation and self.clean_cache_enabled:
            commands.append(["apt", "clean"])
        self.queue.clear()
        self.update_queue_label()
        shell = "set -e; " + " && ".join(" ".join("'" + x.replace("'", "'\\''") + "'" for x in c) for c in commands)
        expected = sum(1 for action in actions.values()
                       if action in ("install", "reinstall", "remove", "purge") or action.startswith("version:"))
        action_title = "Package actions" if self.language == "en" else "Paketaktionen"
        action_description = (
            f"{len(actions)} selected package action(s) are being executed."
            if self.language == "en" else
            f"{len(actions)} ausgewählte Paketaktion(en) werden ausgeführt."
        )
        self.run_action_job(privileged(["/bin/sh", "-c", shell]), action_title,
                            action_description, expected,
                            auto_close=auto_close.isChecked())

    def show_package_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Paketverlauf")
        dialog.resize(850, 600)
        layout = QVBoxLayout(dialog)
        info = QLabel("Installierte, entfernte und aktualisierte Pakete. Der Verlauf ist auf maximal 1 MB begrenzt.")
        info.setWordWrap(True)
        layout.addWidget(info)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        history = read_package_history()
        if self.language == "en":
            history = history.replace(r"\n", "\n")
            for de, en in (("Zeit:", "Time:"), ("Befehl:", "Command:"), ("Ergebnis:", "Result:"), ("Erfolgreich", "Successful"), ("Fehler (Exit-Code", "Error (exit code"), ("Paketänderungen:", "Package changes:"), ("Installiert:", "Installed:"), ("Entfernt:", "Removed:"), ("Aktualisiert:", "Upgraded:"), ("Erneut installiert:", "Reinstalled:")):
                history = history.replace(de, en)
        view.setPlainText(history if history else ("No package changes have been logged by LunaPaket yet." if self.language == "en" else "Noch keine Paketänderungen durch LunaPaket protokolliert."))
        layout.addWidget(view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        self.translate_dialog(dialog)
        dialog.exec()

    def set_busy(self, busy):
        self._busy = bool(busy)
        self.update_btn.setEnabled(not busy)

    @staticmethod
    def apt_status_progress(line):
        """Liest APTs maschinenlesbares dlstatus-/pmstatus-Protokoll."""
        clean = line.strip().lstrip("\x1b")
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
        self.status.setText("Package operation in progress …" if self.language == "en" else "Paketaktion läuft …")
        self.set_busy(True)
        dialog = ActionProgressDialog(self, title, description, english=self.language == "en")
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
            match = re.match(r"^(?:Setting up|Removing|Purging|Unpacking)\s+([^ :]+)", line)
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
            self.status.setText(("Package operation completed" if code == 0 else f"Package operation failed (APT code {code})") if self.language == "en" else ("Paketaktion abgeschlossen" if code == 0 else f"Paketaktion fehlgeschlagen (APT-Code {code})"))
            if code == 0:
                self.catalog_cache = None
                self._table_catalog_ready = False
                self.search_pkgs()
        self.action_stream.finished_text.connect(finished)
        self.action_stream.start()
        dialog.exec()

    def run_job(self,args):
        self.status.setText("APT is working in the background …" if self.language == "en" else "APT arbeitet im Hintergrund …"); self.set_busy(True)
        self.job=Job(args); self.job.finished_text.connect(self.job_done); self.job.start()
    def job_done(self,r,o):
        self.set_busy(False)
        self.details.setPlainText(o[-18000:])
        self.status.setText(("Completed" if r == 0 else "Error – see details below") if self.language == "en" else ("Abgeschlossen" if r==0 else "Fehler – Details unten"))
        if r == 0:
            self.catalog_cache = None
            self._table_catalog_ready = False
        self.search_pkgs()
    def update_lists(self):
        self.catalog_cache = None
        self._table_catalog_ready = False
        self.run_job(privileged(["apt","update"]))
    def upgrade(self):
        self.catalog_cache = None
        self._table_catalog_ready = False
        # Erst Paketlisten aktualisieren und Upgrade-Kandidaten ermitteln.
        self.status.setText("Updating package sources …" if self.language == "en" else "Paketquellen werden aktualisiert …")
        self.set_busy(True)
        self.upgrade_check_job = FunctionJob(self.check_upgrades)
        self.upgrade_check_job.result.connect(self.upgrade_check_done)
        self.upgrade_check_job.failed.connect(self.upgrade_check_failed)
        self.upgrade_check_job.start()

    @staticmethod
    def check_upgrades():
        rc, update_output = cmd(privileged(["apt", "update"]))
        if rc != 0:
            raise RuntimeError("Paketlisten konnten nicht aktualisiert werden.\n\n" + update_output)
        rc, listing = cmd(["apt", "list", "--upgradable"])
        if rc != 0:
            raise RuntimeError(listing or "Aktualisierungen konnten nicht ermittelt werden.")
        packages = [line.strip() for line in listing.splitlines()[1:] if line.strip() and "/" in line]
        # APT nennt bei der Upgrade-Simulation die Herkunft der Zielversion.
        # Debian-Sicherheitsquellen sind an security.debian.org bzw.
        # trixie-security/bookworm-security und Debian-Security erkennbar.
        rc, simulation = cmd(["apt", "-s", "upgrade"])
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
        en = self.language == "en"
        self.set_busy(False)
        self.status.setText("Update check failed" if en else "Aktualisierungsprüfung fehlgeschlagen")
        QMessageBox.critical(
            self,
            "System update failed" if en else "System aktualisieren",
            (str(error).replace("Paketlisten konnten nicht aktualisiert werden.", "Could not refresh package lists.")
                    .replace("Aktualisierungen konnten nicht ermittelt werden.", "Could not determine available updates.")
                    .replace("Sicherheitsaktualisierungen konnten nicht erkannt werden.", "Could not identify security updates.")
             if en else str(error))
        )

    def upgrade_check_done(self, result):
        update_output, packages, security_packages = result
        self.set_busy(False)
        en = self.language == "en"
        if not packages:
            self.status.setText("System is up to date" if en else "System ist auf dem neuesten Stand")
            QMessageBox.information(self, "System update" if en else "System aktualisieren",
                "No package updates are available.\n\nThe system is up to date." if en else
                "Es sind keine Paketaktualisierungen verfügbar.\n\nDas System ist aktuell.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle((f"Available updates – {len(packages)} packages" if en else f"Verfügbare Aktualisierungen – {len(packages)} Pakete"))
        dlg.resize(900, 590)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(
            (f"{len(packages)} update(s) found, including {len(security_packages)} security update(s).\nNothing has been installed yet." if en else
             f"{len(packages)} Aktualisierung(en) gefunden, davon {len(security_packages)} Sicherheitsaktualisierung(en).\nNoch wurde nichts installiert.")
        ))
        table = QTableWidget(len(packages), 4)
        table.setHorizontalHeaderLabels(["Package", "New version", "Source / architecture", "Type"] if en else ["Paket", "Neue Version", "Quelle / Architektur", "Art"])
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
            is_security = name.split(":", 1)[0] in security_set
            kind = (("Security update" if is_security else "Regular update") if en else ("Sicherheitsupdate" if is_security else "Normales Update"))
            for col, value in enumerate((name, version, source, kind)):
                table.setItem(row, col, QTableWidgetItem(value))
        lay.addWidget(table, 3)
        lay.addWidget(QLabel("APT check and available packages:" if en else "APT-Prüfung und verfügbare Pakete:"))
        log = QTextEdit(); log.setReadOnly(True); log.setMaximumHeight(110)
        log.setPlainText(("Package lists updated successfully.\n" if en else "Paketlisten erfolgreich aktualisiert.\n") + "\n".join(packages))
        lay.addWidget(log, 1)
        auto_close = QCheckBox("Close window after successful action" if en else "Fenster nach erfolgreicher Aktion schließen")
        auto_close.setChecked(True)
        lay.addWidget(auto_close)
        buttons = QDialogButtonBox()
        cancel = buttons.addButton("Cancel" if en else "Abbrechen", QDialogButtonBox.RejectRole)
        security_btn = None
        if security_packages:
            security_btn = buttons.addButton("Install security updates only" if en else "Nur Sicherheitsupdates installieren", QDialogButtonBox.ActionRole)
        all_btn = buttons.addButton("Install all updates" if en else "Alle Aktualisierungen installieren", QDialogButtonBox.AcceptRole)
        lay.addWidget(buttons)
        choice = {"mode": None}
        cancel.clicked.connect(dlg.reject)
        all_btn.clicked.connect(lambda: (choice.update(mode="all"), dlg.accept()))
        if security_btn:
            security_btn.clicked.connect(lambda: (choice.update(mode="security"), dlg.accept()))
        if dlg.exec() != QDialog.Accepted or not choice["mode"]:
            self.status.setText("Update cancelled – nothing installed" if en else "Aktualisierung abgebrochen – nichts installiert")
            return
        selected = security_packages if choice["mode"] == "security" else packages
        self.start_upgrade_install(selected, security_only=(choice["mode"] == "security"), auto_close=auto_close.isChecked())

    def start_upgrade_install(self, packages, security_only=False, auto_close=True):
        en = self.language == "en"
        if en:
            title = "Installing security updates" if security_only else "Updating system"
            description = f"Installing {len(packages)} package update(s)."
        else:
            title = "Sicherheitsaktualisierungen installieren" if security_only else "System wird aktualisiert"
            description = f"{len(packages)} Paketaktualisierung(en) werden installiert."
        progress = ActionProgressDialog(self, title, description, english=en)
        progress.auto_close.setChecked(bool(auto_close))
        self.set_busy(True)
        if security_only:
            names = [line.split()[0].split("/", 1)[0] for line in packages]
            args = privileged(["apt", "-o", "APT::Status-Fd=2", "-y", "--only-upgrade", "install", *names])
        else:
            args = privileged(["apt", "-o", "APT::Status-Fd=2", "-y", "upgrade"])
        self.upgrade_stream = StreamJob(args)
        unpacked = set()
        configured = set()

        def upgrade_output_line(line):
            progress.append_output(line)
            apt_percent, apt_message = self.apt_status_progress(line)
            if apt_percent is not None:
                progress.set_progress(apt_percent, apt_message)
                return
            # dpkg progress output follows the system locale; normalize the
            # common German and English package-action prefixes for the UI.
            unpack_match = re.match(r"^(?:Unpacking|Preparing to unpack|Entpacken von|Entpacke)\s+([^ :]+)", line)
            setup_match = re.match(r"^(?:Setting up|Einrichten von|Richte ein)\s+([^ :]+)", line)
            if unpack_match:
                package = unpack_match.group(1)
                unpacked.add(package)
                percent = min(50, int(len(unpacked) * 50 / max(1, len(packages))))
                progress.set_progress(percent, package + (" (Unpacking)" if en else " (Entpacken)"))
            elif setup_match:
                package = setup_match.group(1)
                configured.add(package)
                percent = 50 + min(49, int(len(configured) * 49 / max(1, len(packages))))
                progress.set_progress(percent, package + (" (Configuring)" if en else " (Einrichten)"))
            elif line:
                progress.set_progress(None, line[:180])

        self.upgrade_stream.output.connect(upgrade_output_line)
        def finished(rc, output):
            progress.finish(rc)
            self.set_busy(False)
            if rc == 0:
                self.status.setText(
                    ("Security updates completed" if security_only else "System update completed")
                    if en else
                    ("Sicherheitsaktualisierungen abgeschlossen" if security_only else "Systemaktualisierung abgeschlossen")
                )
                self.catalog_cache = None
                self._table_catalog_ready = False
            else:
                self.status.setText("Update failed" if en else "Fehler bei der Aktualisierung")
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
            self.status.setText((f"Automatic security check: {len(active)} pending security updates" if self.language == "en" else f"Automatische Sicherheitsprüfung: {len(active)} offene Sicherheitsupdates"))
            previous = self.settings.value("security/last_count", -1, type=int)
            self.settings.setValue("security/last_count", len(active))
            self.settings.setValue("security/last_check", __import__("datetime").datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"))
            if len(active) > max(0, previous):
                self.status.setText((f"New security updates found: {len(active)}" if self.language == "en" else f"Neue Sicherheitsupdates gefunden: {len(active)}"))
        def failed(error):
            self._security_check_running = False
            self.status.setText("Automatic security check failed" if self.language == "en" else "Automatische Sicherheitsprüfung fehlgeschlagen")
        self.security_silent_job.result.connect(done)
        self.security_silent_job.failed.connect(failed)
        self.security_silent_job.start()

    @staticmethod
    def find_security_updates():
        rc, update_out = cmd(privileged(["apt", "update"]))
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
        self.status.setText("Searching for security updates …" if self.language == "en" else "Sicherheitsupdates werden gesucht …")
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
        dlg = QDialog(self); dlg.setWindowTitle("Manage security updates" if self.language == "en" else "Sicherheitsupdates verwalten"); dlg.resize(980, 650)
        layout = QVBoxLayout(dlg)
        active = sum(not x["deferred"] for x in items)
        summary = (f"{len(items)} security update(s) found · {active} active · {len(items)-active} deferred" if self.language == "en" else f"{len(items)} Sicherheitsupdate(s) gefunden · {active} aktiv · {len(items)-active} zurückgestellt")
        layout.addWidget(QLabel(summary))
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
            preview_rc, preview = cmd(["apt", "-s", "--only-upgrade", "install", *names])
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
            hl.addWidget(view); b=QPushButton("Schließen"); b.clicked.connect(hd.accept); hl.addWidget(b); self.translate_dialog(hd); hd.exec()
        defer_btn.clicked.connect(defer_selected); restore_btn.clicked.connect(restore_selected)
        # Dialog schließen und Sicherheitsupdate-Suche erneut im Hintergrund starten.
        search_btn.clicked.connect(lambda: (dlg.accept(), self.manage_security_updates()))
        install_btn.clicked.connect(install_selected); history_btn.clicked.connect(show_history)
        close.clicked.connect(dlg.accept)
        self.translate_dialog(dlg)
        dlg.exec()

    def run_security_install(self, chosen):
        names = [x["package"] for x in chosen]
        progress = ActionProgressDialog(self, "Install security updates" if self.language == "en" else "Sicherheitsupdates installieren",
                                        (f"Installing {len(names)} selected security updates." if self.language == "en" else f"{len(names)} ausgewählte Sicherheitsupdates werden installiert."), english=self.language == "en")
        self.set_busy(True)
        args = privileged(["apt", "-o", "APT::Status-Fd=2", "-y", "--only-upgrade", "install", *names])
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
                self.status.setText("Security updates installed" if self.language == "en" else "Sicherheitsupdates installiert")
            else:
                self.status.setText("Security update installation failed" if self.language == "en" else "Installation der Sicherheitsupdates fehlgeschlagen")
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
        english = self.language == "en"
        d = QDialog(self)
        d.setWindowTitle("Repositories (repository management)" if english else "Paketquellen (Repository-Verwaltung)")
        d.resize(1050, 650)
        layout = QVBoxLayout(d)
        layout.addWidget(QLabel("Enable, edit and manage APT repositories." if english else "APT-Paketquellen aktivieren, bearbeiten und verwalten."))
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["Enabled", "Type", "Address", "Distribution", "Components"] if english else ["Aktiviert", "Typ", "Adresse", "Distribution", "Bereiche"])
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
        editor_box=QGroupBox("Edit selected repository" if english else "Ausgewählte Paketquelle bearbeiten"); form=QFormLayout(editor_box)
        typ=QComboBox(); typ.addItems(["deb","deb-src"]); uri=QLineEdit(); suite=QLineEdit(); components=QLineEdit()
        form.addRow("Type:" if english else "Typ:",typ); form.addRow("Address:" if english else "Adresse:",uri); form.addRow("Distribution:",suite); form.addRow("Components:" if english else "Bereiche:",components); layout.addWidget(editor_box)
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
            QMessageBox.information(d, "Repositories" if english else "Paketquellen", "Changes saved. Refresh the package lists afterwards." if english else "Änderungen gespeichert. Aktualisiere anschließend die Paketlisten.")
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
        for label,fn in ((("Up",lambda:move(-1)),("Down",lambda:move(1)),("New",add_entry),("Delete",delete_entry),("Apply",apply_form)) if english else (("Hoch",lambda:move(-1)),("Runter",lambda:move(1)),("Neu",add_entry),("Löschen",delete_entry),("Übernehmen",apply_form))):
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        actions.addStretch(1); layout.addLayout(actions)
        buttons=QDialogButtonBox(); save=buttons.addButton("OK",QDialogButtonBox.AcceptRole); cancel=buttons.addButton("Cancel" if english else "Abbrechen",QDialogButtonBox.RejectRole)
        save.clicked.connect(lambda:(apply_form(),save_all(),d.accept())); cancel.clicked.connect(d.reject); layout.addWidget(buttons)
        d.exec()

    def check_sources(self):
        progress=ActionProgressDialog(self, "Check repositories" if self.language == "en" else "Paketquellen prüfen", "APT checks all configured repositories and reports invalid or unreachable sources." if self.language == "en" else "APT prüft alle konfigurierten Paketquellen und meldet fehlerhafte oder nicht erreichbare Repositories.", english=self.language == "en")
        job=StreamJob(privileged(["apt","update"]))
        job.output.connect(progress.append_output)
        result={"code":1}
        def done(rc,out):
            result["code"]=rc; progress.finish(rc)
        job.finished_text.connect(done)
        job.start(); progress.exec()
        if job.isRunning(): job.wait()
        if result["code"] == 0: QMessageBox.information(self, "Repositories" if self.language == "en" else "Paketquellen", "Package lists were refreshed successfully." if self.language == "en" else "Die Paketlisten wurden erfolgreich aktualisiert.")
        else: QMessageBox.warning(self, "Repositories" if self.language == "en" else "Paketquellen", "At least one repository could not be refreshed successfully. See the check log for details." if self.language == "en" else "Mindestens eine Paketquelle konnte nicht fehlerfrei aktualisiert werden. Details stehen im Prüfprotokoll.")

    def install_local_deb(self, paths=None):
        if paths is None:
            paths,_=QFileDialog.getOpenFileNames(self, "Select local DEB files" if self.language == "en" else "Lokale DEB-Dateien auswählen", "", "Debian packages (*.deb)" if self.language == "en" else "Debian-Pakete (*.deb)")
        else:
            paths=[os.path.abspath(x) for x in paths if x.lower().endswith(".deb") and os.path.isfile(x)]
        if not paths: return

        details=[]
        reinstall_paths=[]
        normal_paths=[]
        for path in paths:
            rc,out=cmd(["dpkg-deb","-f",path,"Package","Version","Architecture","Description"])
            if rc != 0:
                QMessageBox.warning(self,"Ungültiges DEB-Paket",f"{os.path.basename(path)} konnte nicht gelesen werden.\n\n{out}")
                continue
            fields={}
            current_key=None
            for line in out.splitlines():
                if line and not line[0].isspace() and ":" in line:
                    current_key,value=line.split(":",1); fields[current_key.strip()]=value.strip()
                elif current_key == "Description" and line:
                    fields[current_key] += "\n" + line
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
            details.append(f"{os.path.basename(path)}\n{out.strip()}"+
                           (f"\nInstalliert: {installed_version}" if installed else "\nStatus: derzeit nicht installiert"))
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
        english = self.language == "en"
        dialog.setWindowTitle("Local Debian package" if english else "Lokales Debian-Paket")
        dialog.resize(680,420)
        layout=QVBoxLayout(dialog)
        heading=QLabel("Selected Debian packages" if english else "Ausgewählte Debian-Pakete")
        heading.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(heading)
        info=QLabel("Check package status and version, then choose the desired action." if english else "Prüfe Paketstatus und Version. Wähle anschließend die gewünschte Aktion.")
        info.setWordWrap(True)
        layout.addWidget(info)
        table=QTableWidget(len(details),4)
        table.setHorizontalHeaderLabels(["File / package","Version","Installed status","Action"] if english else ["Datei / Paket","Version","Installierter Status","Aktion"])
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
                    (f"Installed: {installed_version}" if english else f"Installiert: {installed_version}") if installed else ("Not installed" if english else "Nicht installiert"),
                    (("Reinstall" if english else "Erneut installieren") if installed else ("Install" if english else "Installieren"))]
            for col,value in enumerate(values):
                table.setItem(row,col,QTableWidgetItem(value))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(table,1)
        buttons=QDialogButtonBox()
        install_btn=buttons.addButton("Install / upgrade" if english else "Installieren / aktualisieren",QDialogButtonBox.AcceptRole)
        reinstall_btn=buttons.addButton("Reinstall" if english else "Erneut installieren",QDialogButtonBox.ActionRole)
        cancel_btn=buttons.addButton("Cancel" if english else "Abbrechen",QDialogButtonBox.RejectRole)
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
            QMessageBox.information(self, "No installation" if english else "Keine Installation", "There are no new or upgradable packages. Choose “Reinstall” to reinstall a package." if english else "Es gibt keine neuen oder aktualisierbaren Pakete. Für eine Neuinstallation bitte „Erneut installieren“ wählen.")
            return

        apt_args=["apt","install","-y"]
        if reinstall:
            apt_args.append("--reinstall")
        args=privileged([*apt_args,*normal_paths])
        self.run_action_job(args, "Install local DEB" if english else "Lokale DEB installieren", "Installing local Debian packages; selected already-installed packages will be reinstalled using APT --reinstall." if english else "Lokale Debian-Pakete werden installiert; bereits installierte Pakete werden bei Auswahl mit APT --reinstall erneut installiert.")

    def show_dependency_analysis(self):
        english = self.language == "en"
        name = self.selected()
        if not name:
            name, ok = QInputDialog.getText(self, "Dependency analysis" if english else "Abhängigkeitsanalyse", "Package name:" if english else "Paketname:")
            if not ok or not name.strip():
                return
            name = name.strip()

        labels = [
            ("Required dependencies" if english else "Benötigte Abhängigkeiten", ["apt-cache", "depends", name]),
            ("Reverse dependencies (packages that depend on this package)" if english else "Rückwärtsabhängigkeiten (Pakete, die dieses Paket benötigen)", ["apt-cache", "rdepends", name]),
            ("Conflicts / Replacements" if english else "Konflikte / Ersetzungen", ["apt-cache", "show", name]),
        ]
        sections = []
        for title, args in labels:
            if english:
                try:
                    result = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, timeout=1800,
                                            env={**os.environ, "LC_ALL": "C", "LANG": "C"})
                    rc, out = result.returncode, result.stdout
                except Exception as exc:
                    rc, out = 1, str(exc)
            else:
                rc, out = cmd(args)
            if "Conflicts" in title or "Konflikte" in title:
                fields = []
                for line in out.splitlines():
                    if line.startswith(("Conflicts:", "Breaks:", "Replaces:", "Depends:", "Pre-Depends:")):
                        fields.append(line)
                fallback = "No relevant conflict or dependency fields were found in the package metadata." if english else "Keine entsprechenden Konflikt-/Abhängigkeitsfelder in den Paketmetadaten gefunden."
                out = "\n".join(fields) or fallback
            no_data = "No information available." if english else "Keine Angaben verfügbar."
            sections.append(title + "\n" + "=" * len(title) + "\n" + (out.strip() or no_data))

        d = QDialog(self)
        d.setWindowTitle(("Dependency analysis – " if english else "Abhängigkeitsanalyse – ") + name)
        d.resize(850, 600)
        lay = QVBoxLayout(d)
        t = QPlainTextEdit(); t.setReadOnly(True); t.setPlainText("\n\n".join(sections)); lay.addWidget(t)
        note_text = ("Note: APT simulation also performs the final conflict and removal checks before each package change." if english else "Hinweis: Die endgültige Konflikt- und Entfernungsprüfung erfolgt zusätzlich durch APT-Simulation vor jeder Paketänderung.")
        note = QLabel(note_text); note.setWordWrap(True); lay.addWidget(note)
        b = QDialogButtonBox(QDialogButtonBox.Close); b.rejected.connect(d.reject); b.accepted.connect(d.accept); lay.addWidget(b)
        if english:
            d.setWindowTitle("Dependency analysis – " + name)
            b.button(QDialogButtonBox.Close).setText("Close")
        d.exec()

    def sources(self):
        files=["/etc/apt/sources.list"]
        try: files += ["/etc/apt/sources.list.d/"+x for x in os.listdir("/etc/apt/sources.list.d") if x.endswith((".list",".sources"))]
        except OSError: pass
        text=""
        for f in files:
            try:text+=f"### {f}\n"+open(f,encoding="utf-8",errors="replace").read()+"\n"
            except OSError:pass
        english = self.language == "en"
        d=QDialog(self); d.setWindowTitle("Repositories" if english else "Paketquellen"); d.resize(800,500); lay=QVBoxLayout(d); t=QTextEdit(); t.setReadOnly(True); t.setPlainText(text or ("No repositories found." if english else "Keine Paketquellen gefunden.")); lay.addWidget(t); b=QDialogButtonBox(QDialogButtonBox.Close); b.rejected.connect(d.reject); lay.addWidget(b); d.exec()
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
