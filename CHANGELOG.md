## 0.1.42
- Snap-Verwaltung als dritten Paketmodus neben APT und Flathub ergänzt.
- Snap-Store-Suche und Store-Bereiche über `snap find`; installierte Anwendungen über `snap list`.
- Installationsstatus, Vormerkungen, gemeinsames Anwenden, Installieren und Entfernen integriert.
- Snap-Details über `snap info` sowie Updateprüfung über `snap refresh --list`; ausgewählte oder alle Updates können installiert werden.
- Snap-Empfehlungsliste wird lokal zwischengespeichert; Cache-Aufbewahrung ist separat in den Einstellungen konfigurierbar. Such- und Kategorieabfragen nutzen `snap find`.
- `snapd` bleibt optionale Laufzeitvoraussetzung und wird bei fehlender Installation verständlich gemeldet.
- APT- und Flathub-Abläufe unverändert gelassen.
- Hinweis: Die Snap-Kommandozeile liefert keine Screenshot-Galerie wie AppStream bei Flathub.
- Flathub-Katalog wird nach dem Programmstart zeitversetzt im Hintergrund vorgeladen, ohne den Aufbau der Oberfläche oder die aktive APT-Ansicht zu blockieren; ein Klick während des Ladens verwendet denselben laufenden Ladevorgang.
- Snap-Aufräumen verwendet jetzt ebenfalls das gemeinsame Fortschrittsfenster mit Live-Konsolenausgabe, aktuellem Eintrag und Fortschrittsanzeige (Deutsch/Englisch).
- Neuer Bereich „Snap aufräumen“ direkt unter „Nicht installiert“: deaktivierte alte Revisionen und gespeicherte Snap-Sicherungen prüfen und einzeln auswählen/entfernen; Oberfläche vollständig deutsch/englisch.
- APT-Symbole werden beim Anzeigen explizit auf 44 × 44 px skaliert, damit sie in der Paketliste ähnlich groß wie Flathub-Symbole erscheinen.
- APT-Paketzeilen reservieren jetzt wie Flathub und Snap einen Symbolpfad.
- Debian-AppStream-Metadaten werden lokal ausgewertet und den APT-Paketnamen zugeordnet.
- Vorhandene Symbole aus `/var/lib/swcatalog/icons` und den üblichen AppStream-Cache-Verzeichnissen werden verwendet.
- Symbole werden nur für sichtbare APT-Zeilen nachgeladen; die Index-Erstellung läuft im Hintergrund und verwendet einen lokalen 7-Tage-Cache.
- Es werden für diese Symbolzuordnung keine zusätzlichen Metadaten aus dem Internet geladen.
- Die lange APT-Installationsvorschau wird in einem scrollbaren Textfeld angezeigt.
- Der Bestätigungsdialog passt seine Größe an den verfügbaren Bildschirm an; Installieren und Abbrechen bleiben sichtbar.
- APT-Versionstabellen werden mit korrekten regulären Ausdrücken ausgewertet; Kandidatenversionen und ihre Sicherheitsquellen werden erkannt.
- Nach erfolgreicher oder fehlgeschlagener Prüfung wird die Statusleiste nicht mehr dauerhaft auf „Suche läuft“ stehen gelassen.

## 0.1.41 – Flathub-Testversion
- Umschalter in der Oberfläche zwischen APT (Debian) und Flathub (Flatpak).
- Separater Flathub-Katalog mit installierten und verfügbaren Anwendungen.
- Flatpak-Anwendungen können benutzerspezifisch installiert und entfernt werden.
- App-Symbole werden aus dem lokalen Flatpak-Appstream-Cache geladen, wenn vorhanden.
- Die bestehende APT-Verwaltung bleibt als eigener Modus erhalten.
- Apt App-Stream hinzugefügt. Leider haben die wenigsten Apps Bilder aber 0AD z.B. hat welche.
- Der App-Stream wird beim ersten start runter geladen und dann gespeichert.

## 0.1.40 Purge-Vormerkung und Kontextmenü
- Fehler behoben: Beim programmatischen Aktualisieren der Paket-Checkbox wurde eine ausdrücklich vorgemerkte Purge-Aktion als normales Entfernen überschrieben.
- Programmatische Checkbox-Synchronisierung wird jetzt von echten Benutzereingaben getrennt.
- Das native Kontextmenü aus 0.1.39 bleibt erhalten; die Menüzeilen und Abstände sind für zuverlässiges Anklicken vergrößert.
- APT-Aktionen und übrige Bedienabläufe bleiben unverändert.

## 0.1.39 Schriftgröße und anpassbare Fensteraufteilung
- Linke Seitenleiste standardmäßig um etwa 2 cm verbreitert.
- Seitenleiste und Paketbereich lassen sich über einen horizontalen Teiler nach links/rechts in der Breite verändern.
- Paketliste und unterer Detailbereich lassen sich über einen vertikalen Teiler in der Höhe verändern.
- Beide Teilerpositionen werden gespeichert und beim nächsten Start wiederhergestellt.
- Fehler behoben: Die fest in den Themes hinterlegte Schriftgröße von 11 pt hat die gespeicherte bzw. ausgewählte Schriftgröße überschrieben.
- Die Theme-Stylesheets verwenden jetzt die eingestellte Schriftgröße.
- Nach einer Änderung über „Einstellungen → Schriftgröße …“ wird das aktive Theme mit der neuen Größe erneut angewendet.
- Die gewählte Schriftgröße bleibt wie bisher in `~/.config/LunaPaket/LunaPaket.conf` gespeichert.
- Keine Änderungen an Paketkatalog, Filtern oder APT-Abläufen.

## 0.1.38 Thematische Softwarebereiche - Performance Update
- Neue Seitenleisten-Kategorien: Amateurfunk, Internet & Netzwerk, Audio & Musik, Video & Multimedia, Grafik & Design, Programmierung, System & Verwaltung, Sicherheit, Elektronik & Hardware, Büro & Bildung, Spiele sowie Wissenschaft & Navigation.
- Kategorienamen vollständig auf Deutsch und Englisch übersetzt.
- Kategorien filtern den bereits geladenen Paketbestand anhand von Paketnamen und Kurzbeschreibungen; der APT-Katalog wird dafür nicht erneut geladen.
- Mehrfachzuordnungen sind möglich, weil die Bereiche unabhängig voneinander filtern.
- Bestehende Bereiche, Installationsstatus, Vormerkungen und APT-Abläufe bleiben erhalten.
- Vertikale und horizontale Scrollleisten der Themenbereiche in der linken Seitenleiste ausgeblendet; Mausradbedienung bleibt erhalten.
- Thematische Paketbereiche in der linken Seitenleiste ergänzt (Deutsch/Englisch).
- Bereiche filtern den vorhandenen Paketbestand; Pakete können mehreren Bereichen zugeordnet sein.

## 0.1.37
- Paketübersicht für 70.549 Pakete optimiert; der vollständige Paketbestand bleibt im Speicher.
- Kategorie- und Statusfilter für „Alle Pakete“, „Installiert“, „Nicht installiert“, „Aufräumen“ und „Vorgemerkt“ beschleunigt.
- Tabellenmodell für die große Paketliste überarbeitet, um unnötige Zeilen- und Zellaktualisierungen zu vermeiden.
- Bedienung und Darstellung der Paket-Checkboxen korrigiert; weiße Kontrollkästchen im dunklen Theme wiederhergestellt.
- Kontextmenü und Paketvormerkungen in der modellbasierten Tabelle korrigiert.
- Englische Oberfläche weiter vervollständigt: Hauptfenster, Statusmeldungen, Paketaktionen, Sicherheitsupdates und Paketquellen.
- Paketdialoge für installierte Dateien, Abhängigkeitsanalyse und Paketeigenschaften sprachabhängig überarbeitet.
- Versionsauswahldialog übersetzt; Fenstertitel und Versionsbeschriftung werden passend zur gewählten Sprache angezeigt.
- Dynamische Status- und Fortschrittsmeldungen sowie Bestätigungsdialoge auf feste deutsche Textzuweisungen geprüft und sprachabhängig korrigiert.
- Aktionsfortschrittsdialog: Fenstertitel und dynamische Beschreibung werden jetzt abhängig von der gewählten Sprache angezeigt (Englisch/Deutsch).
- Englische Übersetzungen der Dialoge für Sicherheitsupdates, Paketquellen und Distributionseinstellungen ergänzt.
- Paketverlauf, Schriftgrößendialog, Statusmeldungen und zugehörige Menüeinträge ins Englische übertragen.
- Bestehende Paketverwaltungsfunktionen unverändert gelassen.
- Die Haupt-Paketliste verwendet `QTableView` mit einem eigenen `QAbstractTableModel`.
- Der vollständige Katalog wird als Datenmodell übernommen; Qt muss dadurch nicht mehr
- für jede Zelle ein separates `QTableWidgetItem` erzeugen. Checkboxen und vorgemerkte
- Aktionen bleiben mit der Paketliste synchronisiert. Die Anzeige bleibt vollständig.

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

## 0.1.37 – Qt-Tabellenumbau
- Haupt-Paketliste von `QTableWidget` auf `QTableView` mit eigenem `QAbstractTableModel` umgestellt.
- Paketkatalog wird mit einem Modell-Reset übernommen, statt für jede Tabellenzelle einzelne `QTableWidgetItem`-Objekte anzulegen.
- Checkbox-Zustände, Vormerkungen, Auswahl, Kontextmenü, Suche und Kategorienfilter an das Datenmodell angebunden.
- Die vollständige Paketliste bleibt erhalten; es gibt kein Seitenlimit und keine gekürzte Anzeige.
- Versionsnummer bleibt wie beauftragt bei 0.1.37.


## 0.1.37 – Hauptfenster-Sprachkorrektur
- Tabellenüberschriften und Paketstatus werden im englischen UI korrekt angezeigt.
- Warteschlangenmeldung und Warteschlangenaktionen folgen der gewählten Sprache.

## 0.1.37 – zusätzliche Sprachkorrekturen
- Weitere englische Übersetzungen für Hauptfenster, Kontextmenüs sowie Paketaktions- und Aufräumdialoge ergänzt.
- Dynamisch erzeugte Bestätigungsdialoge werden vor der Anzeige durch die Dialogübersetzung geführt.
- Paketbestand, Ladeablauf und übrige Paketverwaltungslogik unverändert gelassen.

### Sprachkorrektur – Aktionsfenster (0.1.37)
- Dynamische Texte des Aktionsfortschritts werden im englischen Modus konsequent englisch dargestellt.
- Bestätigungsdialog, Aktionsbezeichnungen, APT-Prüfhinweis und Statusmeldung sind sprachabhängig.
- Paketbestand, Lade-/Zählverhalten und Paketverarbeitung unverändert.

## 0.1.37 – Sprachkorrektur
- Korrigiert die Statusmeldung nach Abbruch der Paketaktions-Bestätigung: Sie folgt jetzt der aktiven Spracheinstellung.

## 0.1.37 – Filter performance
- Kategorie- und Suchfilter arbeiten jetzt über eine kompakte sichtbare Zeilenliste im bestehenden Tabellenmodell.
- Beim Wechsel zwischen Alle Pakete, Installiert, Nicht installiert, Aufräumen und Vorgemerkt entfallen die zehntausenden einzelnen `setRowHidden()`-Aufrufe.
- Der vollständige Paketbestand, Checkbox-Zustände und Vormerkungen bleiben im Quellmodell erhalten.

## 0.1.37 – Sprachkorrekturen (16.11.2026)
- Weitere englische Übersetzungen für Statusmeldungen beim APT-Hintergrundlauf und beim Aktualisieren der Paketquellen ergänzt.
- Sicherheitsupdate-Dialog: Fenstertitel und dynamische Zusammenfassung werden jetzt abhängig von der gewählten Sprache angezeigt.
- Dynamische Statusmeldungen für Sicherheitsprüfungen und abgeschlossene/fehlgeschlagene Paketaktionen sprachabhängig gemacht.

## 0.1.41 – APT-AppStream-Bildquelle korrigiert
- Aktuelle Debian-AppStream-Generator-Metadaten werden für die erkannte Debian-Version und Architektur im Hintergrund geladen und lokal zwischengespeichert.
- Die aktuellen Metadaten werden gegenüber den möglicherweise veralteten APT-DEP-11-Metadaten bevorzugt.
- Screenshot-Quellen aus `source-image.url` werden korrekt ausgewertet; lokale APT-Metadaten bleiben als Rückfall erhalten.
- Flathub-Funktionen und Versionsnummer unverändert.

## 0.1.41 – Flathub-Updateverwaltung (Deutsch/Englisch)
- Eigene Schaltfläche zum Suchen nach verfügbaren Flatpak-Updates in der Flathub-Ansicht ergänzt.
- Prüfung der Benutzer- und Systeminstallation getrennt, damit Updates aus beiden Bereichen erkannt werden.
- Verfügbare App- und Runtime-Updates werden einzeln aufgeführt und können ausgewählt oder gesammelt installiert werden.
- Installation nutzt die passende Flatpak-Installation; Systemupdates fragen bei Bedarf Root-Rechte über pkexec an.
- Oberfläche, Rückmeldungen und Bestätigungen sind auf Deutsch und Englisch verfügbar.
- APT-Updatefunktionen und Versionsnummer 0.1.41 bleiben unverändert.

## 0.1.42 – Snap-Hintergrundimport und sauberes Beenden
- Snap-Katalog wird beim Öffnen sofort aus dem lokalen Cache angezeigt; Aktualisierungen laufen im Hintergrund.
- Ein Klick auf Kategorien während eines laufenden Imports startet keinen zweiten parallelen Kataloglauf.
- SnapUpdates speichert den Importstand nach jeder gelesenen Seite atomar, damit ein Abbruch keine bereits geladenen Seiten verliert.
- Beim Beenden werden laufende Snap-Katalogjobs kooperativ unterbrochen; Netzwerk- und snapd-Aufrufe haben begrenzte Laufzeiten.
- APT- und Flathub-Funktionen wurden nicht geändert.

### 0.1.42 – Korrektur der Fortschrittsfenster-Einstellung
- Die Auswahl „Fenster nach erfolgreicher Aktion schließen“ wird jetzt beim Ändern sowohl im gemeinsamen Einstellungsschlüssel als auch im Aktionsschlüssel gespeichert.
- Verhindert, dass Installationsabläufe die gespeicherte Auswahl beim Öffnen des Fortschrittsfensters durch den Standardwert überschreiben.

### 0.1.42 – Architekturabhängige Paketkataloge
- APT zeigt native Pakete der Debian-Systemarchitektur sowie architekturunabhängige Pakete (`all`); fremde Multiarch-Varianten werden aus dem normalen Katalog ausgeschlossen.
- Flathub-Katalog und installierte Anwendungen werden mit der von Flatpak ermittelten Host-Architektur (`aarch64`, `x86_64` usw.) abgefragt. Der Katalogcache ist je Architektur getrennt.
- Snap-Suchergebnisse aus der öffentlichen Store-Suche werden gegen die Ergebnisse der lokalen snapd-Suche geprüft, damit nur auf dem Gerät verfügbare Snaps angezeigt werden. Der Snap-Cache ist je Debian-Architektur getrennt.
- Versionsnummer bleibt 0.1.42.

## 0.1.42 – Flathub-Status und Kontextmenü
- Nach Flatpak-Installationen und -Deinstallationen zeigt die Statuszeile den laufenden Flathub-Katalogabgleich und anschließend dessen Abschluss bzw. einen Fehler an.
- Kontextmenüeinträge für Flathub werden im englischen UI-Modus jetzt ebenfalls auf Englisch angezeigt.
