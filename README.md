# LunaPaket 0.1.35

Grafische Paketverwaltung für Debian 13 (Trixie) und kompatible Debian-Systeme.
LunaPaket verwaltet APT-Pakete, Paketquellen und Sicherheitsupdates über eine
grafische Oberfläche auf Basis von Python 3 und PySide6.

![LunaPaket](lunapaket.png)

[Github Seite](https://github.com/Angonikro/LunaPaket/)

## Funktionen

- Paketübersicht mit installierten und nicht installierten Paketen
- Paketsuche und Paketdetails
- Pakete zur Installation oder Entfernung vormerken
- Systemaktualisierung und Aktualisierung der APT-Paketlisten
- Paketquellen verwalten
- Sicherheitsupdates anzeigen und einzeln bearbeiten
- Lokale DEB-Dateien auswählen und installieren
- Gemeinsames Anwenden vorgemerkter Installationen und Entfernungen
- Einstellbare Schriftgröße
- Oberflächensprache Deutsch/Englisch
- Hell-/Dunkel-Theme
- Deutsch/Englisch

## Einstellungen

Die Einstellungen werden im Benutzerprofil gespeichert:

```text
~/.config/LunaPaket/LunaPaket.conf
```

Dort speichert LunaPaket unter anderem Sprache, Farbschema, Schriftgröße
und Fensterposition. Auch bei einer Rechteabfrage über `pkexec` wird das
Profil des angemeldeten Desktop-Benutzers verwendet.

## Voraussetzungen

Empfohlen ist Debian 13 (Trixie) mit einer grafischen Desktop-Sitzung
(z. B. Raspberry Pi OS, XFCE, GNOME oder KDE).

Benötigt werden Python 3, PySide6, Python-APT (`python3-apt`), APT, dpkg,
PolicyKit (`pkexec` und `polkitd`) sowie die Qt-XCB-Laufzeitbibliotheken.

## Abhängigkeiten installieren

```bash
sudo apt update
sudo apt install python3 python3-apt python3-pyside6.qtcore \
  python3-pyside6.qtgui python3-pyside6.qtwidgets \
  libxcb-cursor0 libxkbcommon-x11-0 libxcb-xinerama0 \
  apt dpkg pkexec polkitd desktop-file-utils shared-mime-info
```

## LunaPaket direkt aus der ZIP starten

ZIP-Datei entpacken und in den Projektordner wechseln:

```bash
mkdir -p ~/Programme
unzip LunaPaket_0.1.35_GITHUB.zip -d ~/Programme
cd ~/Programme/LunaPaket
```

Start über das mitgelieferte Skript:

```bash
chmod +x run.sh
./run.sh
```

Alternativ:

```bash
python3 lunapaket/main.py
```

Für den ZIP-Start bitte `run.sh` oder `python3 lunapaket/main.py` verwenden.
Der Launcher `lunapaket/lunapaket` ist für die installierte DEB-Version
vorgesehen und verweist auf `/usr/share/lunapaket/main.py`.

LunaPaket fordert Administratorrechte bei Bedarf über PolicyKit (`pkexec`) an.
Daher zunächst normal aus der grafischen Sitzung starten und nicht mit `sudo`.

## Debian-Paket installieren

```bash
cd ~/Downloads
sudo apt install ./lunapaket_0.1.35_all.deb
```

Anschließend über das Anwendungsmenü oder mit `lunapaket` starten.
Der Desktop-Eintrag registriert LunaPaket außerdem als Öffnen-mit-Anwendung
für Debian-Paketdateien (`.deb`).

## Debian-Paket selbst aus dem ZIP bauen

Im entpackten Projektordner:

```bash
cd ~/Programme/LunaPaket
chmod +x build_deb.sh
./build_deb.sh
```

Das Skript erstellt `dist/lunapaket_0.1.35_all.deb`.
Zum Bauen wird `dpkg-deb` benötigt.



## Fehlerbehebung

**PySide6 fehlt:**

```bash
sudo apt install python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
```

**Python-APT fehlt:**

```bash
sudo apt install python3-apt
```

**Keine PolicyKit-Rechteabfrage:**

```bash
sudo apt install pkexec polkitd
```

LunaPaket aus der normalen Desktop-Sitzung starten, nicht mit `sudo`.

## Deinstallation

```bash
sudo apt remove lunapaket
```

Für eine vollständige Entfernung einschließlich systemweiter Paketkonfiguration:

```bash
sudo apt purge lunapaket
```

Persönliche Einstellungen unter `~/.config/LunaPaket/` bleiben bei einer
normalen Deinstallation erhalten.

---

73 de DO2QG Andreas
