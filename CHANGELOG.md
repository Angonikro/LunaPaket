# Änderungsprotokoll

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
