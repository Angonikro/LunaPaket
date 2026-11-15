## 0.1.36
- Fehlerhafte doppelte Maskierung in den DPKG-Auswertungsmustern behoben; Erstinstallationen, erneute Installationen, Entfernungen, vollständige Entfernungen und Upgrades werden dadurch zuverlässig erkannt.
- Paketverlauf schreibt wieder echte Zeilenumbrüche statt sichtbarer `\n`-Sequenzen.
- Der Bereich „Aufräumen“ wird über dieselbe DPKG-Ereigniserfassung protokolliert; tatsächlich entfernte Pakete erscheinen als Verlaufseinträge.
- Paketverlauf auf tatsächliche DPKG-Ereignisse umgestellt: Installationen, Neuinstallationen (auch gleiche Version), Upgrades, Entfernungen und vollständige Entfernungen werden direkt aus `/var/log/dpkg.log` erfasst.
- Erkennung shell-quotierter APT-Aufrufe korrigiert; damit werden auch gebündelte vorgemerkte Aktionen protokolliert.
- Neuinstallationen derselben Paketversion werden jetzt ebenfalls als „Erneut installiert“ erfasst, auch wenn sich die Versionsnummer vor und nach der Aktion nicht ändert.
- Paketverlauf korrigiert: Auch APT-Aktionen, die LunaPaket als Shell-Kette für vorgemerkte Änderungen ausführt, werden jetzt erkannt und protokolliert.
- Paketverlauf in der Oberfläche ergänzt: über „Datei → Paketverlauf anzeigen …“ lassen sich zuletzt installierte, entfernte und aktualisierte Pakete einsehen.
- Der Verlauf erfasst Paketnamen, Versionen, Zeitstempel, ausgeführten APT-Befehl und Ergebnis; auch teilweise Paketänderungen bei fehlgeschlagenen APT-Aktionen werden festgehalten.
- Paketverlauf unter `~/.local/share/LunaPaket/logs/package-history.log`, auf maximal 1 MiB begrenzt; bei Platzbedarf werden die ältesten Einträge verworfen.
- APT-Aufrufe in LunaPaket konsequent von `apt-get` auf `apt` umgestellt, einschließlich Systemaktualisierung, Sicherheitsupdates, Paketquellenprüfung, Installation und Aufräumen.
- Systemaktualisierung verwendet `apt upgrade`, damit erforderliche zusätzliche Pakete (z. B. neue Kernelpakete) mitinstalliert werden können.
- Fehlgeschlagene APT-Aufrufe werden mit Zeitstempel, Befehl, Exit-Code und Ausgabe protokolliert.
- Fehlerprotokoll unter `~/.local/share/LunaPaket/logs/apt-errors.log`; Begrenzung auf 512 KB plus eine rotierte Sicherung.
- Erfolgreiche APT-Aktionen erzeugen keine eigenen Fehlerprotokolleinträge.

# Änderungsprotokoll LunaPaket

## 0.1.35
- Im Bereich „Aufräumen“ ein sichtbares Sammelkästchen „Alle Pakete vormerken“ ergänzt. Es merkt alle von APT erkannten entbehrlichen, installierten Pakete gemeinsam zur Entfernung vor; erneutes Abwählen nimmt diese Sammelvormerkungen zurück.
- Sammelvormerkung arbeitet direkt auf den bereits geladenen Tabellenzeilen und startet keine zusätzliche Paketabfrage.
- Checkbox „Fenster nach erfolgreicher Aktion schließen“ zusätzlich in den Bestätigungsdialog für vorgemerkte Paketaktionen und in den Dialog „Verfügbare Aktualisierungen“ aufgenommen.
- Die Auswahl wird an das jeweilige Fortschrittsfenster weitergegeben; standardmäßig aktiviert.
- Bei Fehlern bleibt das Fortschrittsfenster einschließlich Protokoll geöffnet.

## 0.1.34
- „Goldisoft 2026“ in den Dialog „Über LunaPaket“ integriert; separater Hilfe-Menüeintrag entfernt.
- Sprachwechsel funktioniert jetzt direkt in beide Richtungen (Deutsch/Englisch), ohne Neustart; Fenstertitel, Menüs, Tabellenstatus und Untertitel werden mit umgestellt.
- Einstellungsfenster: Checkbox-Texte, Tooltip und Schließen-Schaltfläche werden bei englischer Sprache zuverlässig auf Englisch gesetzt.
- Korrekturpaket für die vollständige englische Übersetzung des Einstellungsdialogs.
- Versionsnummer erhöht, damit Debian das aktualisierte Paket eindeutig als neuere Version installiert.
- Letzte deutsche Texte im Einstellungsfenster werden bei englischer Sprache ebenfalls übersetzt; einschließlich Fensteroptionen, Tooltip und Schließen-Schaltfläche.
- Englische Oberfläche vervollständigt: Untertitel, Paketstatus und Lade-/Filterstatus werden ebenfalls übersetzt.
- Im Menü „Hilfe“ den Eintrag „Goldisoft 2026“ mit Infofenster ergänzt.
- Englische Oberflächensprache ergänzt; Deutsch bleibt Standardsprache.
- Hell- und Dunkel-Theme ergänzt.
- Sprache und Theme werden in `~/.config/LunaPaket/LunaPaket.conf` gespeichert.
- Versionsnummer in Programm, Debian-Metadaten, Build-Skript und Dokumentation auf 0.1.34 angehoben.


## 0.1.33
- Menüaktion „DEB-Pakete öffnen …“ korrigiert: Qt-Signalparameter wird nicht mehr versehentlich als Dateiliste an den Dateiauswahldialog übergeben.
- Vormerkliste wird beim Anwenden nochmals aus sämtlichen Kontrollkästchen mit dem Installationsstatus abgeglichen; verhindert verlorene Checkbox-Klicks und berücksichtigt Installieren sowie Entfernen gemeinsam.
- Hauptoberfläche vereinfacht: Einzelbuttons „Installieren“ und „Entfernen“ entfernt.
- „Vormerkung löschen“ und „Vorgemerkte Änderungen anwenden“ bleiben als zentrale Aktionen erhalten.
- Der Anwenden-Button führt ausschließlich bereits vorgemerkte Aktionen aus und markiert nicht unbeabsichtigt das aktuell ausgewählte Paket.
- Eintrag „Paketquellen verwalten“ aus dem Menü „Einstellungen“ entfernt; die Verwaltung bleibt im eigenen Menü „Paketquellen“ erreichbar.
- Vorgemerkte Installationen und Entfernungen werden gemeinsam über die bestehende APT-Simulation und Bestätigung ausgeführt.

## 0.1.32
- Paketliste verwendet wieder exakt die eindeutigen Paketnamen aus `apt-cache pkgnames` als Referenz (70518 laut Systemmessung); Paketdetails werden über python-apt/libapt-pkg gelesen. Architekturvarianten werden nicht zusätzlich gezählt.

0.1.31
- Paketliste auf native Systemarchitektur und architekturunabhängige Pakete (all) begrenzt. Fremdarchitektur-Varianten werden in der normalen Paketübersicht nicht mehr zusätzlich gezählt.

0.1.30
- Paketliste auf direkten Zugriff über python-apt/libapt-pkg umgestellt. Installierte und verfügbare Versionen stammen jetzt aus demselben APT-Cache; Paketnamen werden nicht mehr aus großen apt-cache-Ausgaben zusammengesetzt.
- Paketstatus, Upgrade-Kandidaten und automatisch entfernbaren Pakete werden direkt aus dem APT-Cache ermittelt.

0.1.29
- Erkennung bereits installierter lokaler DEB-Pakete korrigiert: dpkg-query-Ausgabe wird anhand des echten Tabulators ausgewertet. Dadurch werden Status und Schaltfläche „Erneut installieren“ korrekt angezeigt.

0.1.28
- Im Fenster „Sicherheitsupdates verwalten“ die Schaltfläche „Jetzt nach Updates suchen“ ergänzt. Sie startet unmittelbar eine neue Sicherheitsupdate-Prüfung und zeigt anschließend die aktualisierte Ergebnisliste.

0.1.27
- Caja-/Dateimanager-Integration für Debian-Pakete korrigiert: expliziter Datei-Aufruf über `--open-deb %f`.
- MIME-Zuordnung für `.deb` mit gängigen Debian-MIME-Aliasnamen ergänzt.
- MIME- und Desktop-Datenbanken werden nach Installation aktualisiert.

 LunaPaket

## 0.1.26
- Fehlerkorrektur für „Öffnen mit → LunaPaket“ bei Debian-Paketen.
- MIME-Zuordnung für `.deb` einschließlich des Alias `application/x-deb` ergänzt.
- MIME- und Desktop-Datenbank werden bei Installation und Entfernung aktualisiert.
- Normaler Programmstart bleibt unverändert: Die Paketübersicht öffnet sich ohne Dateiauswahl.
- Versionsnummer bleibt 0.1.26.

### Korrektur am Infofenster (Version bleibt 0.1.34)
- Fehlerhafte sichtbare `\\n`-Zeichen im Dialog „Über LunaPaket“ beseitigt.
- Infofenster übersichtlicher mit Programmname, Versionsnummer, Goldisoft 2026 und Beschreibung formatiert.
- Keine Änderung der Versionsnummer.
