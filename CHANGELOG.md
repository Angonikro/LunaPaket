# Änderungsprotokoll

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
