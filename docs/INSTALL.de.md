# seb5594's Integration Hub

Einmal das Sammelrepo hinzufügen, danach die einzelnen Integrationen direkt in HACS entdecken:
Der Hub registriert die Repositories automatisch und meldet neue Projekte mit ihrem Anzeigenamen
und einem direkten HACS-Link. HACS verwaltet die Downloads und späteren Updates jeder Integration.

## Einrichten

1. In **HACS → ⋮ → Benutzerdefinierte Repositories** die URL `https://github.com/seb5594/Home-Assistant-Integrations` als **Integration** hinzufügen.
2. **seb5594's Integration Hub** herunterladen und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **seb5594's Integration Hub** suchen.
4. Automatisches Hinzufügen zu HACS und Benachrichtigungen aktiviert lassen oder die Einstellungen anpassen.
5. HACS öffnen: Die Einzelrepositories aus dem Katalog werden automatisch hinzugefügt. Die gewünschten Integrationen dort herunterladen und entsprechend ihrer eigenen Anleitung einrichten.

Das Hinzufügen eines Repositorys installiert noch keine Komponente und verändert keine Konfiguration.
Neustarts werden nicht automatisch ausgelöst. Der Hub benötigt Home Assistant **2025.1.0** oder neuer.
Für die automatische Registrierung muss HACS eingerichtet sein; dessen GitHub-Verbindung wird mitbenutzt.
Ein zusätzlicher Token, Git oder Terminalzugriff sind nicht erforderlich.

Die Registrierung verwendet eine **interne HACS-Laufzeitschnittstelle** und ist daher experimentell.
Sie nutzt die reguläre HACS-Validierung und schreibt nicht selbst in HACS-Speicherdateien. Wenn HACS
fehlt oder die Schnittstelle inkompatibel ist, meldet der Hub den Fehler und versucht es später erneut.
Die direkten HACS-Links funktionieren weiterhin. Registrierungen laden keine Komponentendateien herunter.

## Neue Integrationen und Benachrichtigungen

Der Hub lädt stündlich die öffentliche `catalog-feed.json` von `raw.githubusercontent.com`.
Der Repository-Workflow aktualisiert diese Liste ebenfalls stündlich sowie nach Release-Benachrichtigungen
der Integrationsrepos. Für neu im Katalog auftauchende Projekte erstellt der Hub eine Home-Assistant-
Benachrichtigung mit Anzeigename, Version und HACS-Link. Wenn möglich, fügt er das Repository vorher
bereits zu HACS hinzu. Dafür muss der Hub selbst nicht erst in HACS aktualisiert werden.

Die erste Prüfung bildet den Ausgangsstand: Bereits vorhandene Projekte werden nicht alle als neu gemeldet.
Bekannte Repositories werden über Neustarts hinweg gespeichert. Neue Versionen eines bekannten Projekts
erzeugen keine weitere „neue Integration“-Meldung; Updates installierter Komponenten verwaltet HACS.
Bei einem Netzwerkfehler bleibt der letzte bekannte Katalog erhalten. Es wird nichts entfernt.

Über **Konfigurieren → Hub-Einstellungen** lassen sich automatische Registrierung und Benachrichtigungen
getrennt abschalten. Der Button **Katalog aktualisieren** prüft sofort. Nach dem Start erfolgt außerdem
ein Versuch nach einer Minute, damit HACS seine Startaufgaben abschließen kann.

Abschalten oder Entfernen des Hubs entfernt keine bereits hinzugefügten Repositories aus HACS.

## Optional: Snapshots direkt installieren

Der bisherige Datei-Installer bleibt unter **Konfigurieren → Snapshots installieren (erweitert)** erhalten.
Er installiert die fest gepinnten Komponenten des lokal installierten Hub-Stands mit SHA-256-Prüfung.
Diese Komponenten verwaltet dann der Datei-Installer. Eine Komponente sollte immer nur durch einen
Manager installiert werden. Für den normalen Betrieb ist die automatische HACS-Registrierung vorgesehen.

Für Snapshot-Updates den Hub in HACS aktualisieren, Home Assistant neu starten und den Snapshot-Dialog
erneut ausführen. Nach Änderungen ist ein weiterer Neustart nötig. Abwählen deinstalliert nichts.
Der Snapshot-Installer prüft die Mindestversionen und lehnt vorhandene Installationen aus anderen Quellen
sowie lokal veränderte Dateien ab. Er benötigt Internetzugriff auf `codeload.github.com`.

Ersetzte Versionen liegen unter `<config>/.integration_catalog_backups/<domain>-<UTC-Zeitstempel>/`.
Zur Wiederherstellung Home Assistant stoppen, den aktuellen Komponentenordner beiseitelegen und die
Sicherung nach `custom_components/<domain>/` zurückschieben. Konfigurationsmigrationen können zusätzlich
die Wiederherstellung eines vollständigen Home-Assistant-Backups erfordern.

Nach einem Prozessabbruch kann `<config>/.integration-catalog.lock` zurückbleiben. Diese Datei nur entfernen,
wenn keine Installation mehr läuft, am besten bei gestopptem Home Assistant. Ein abgebrochener Dialog kann
seinen Download noch kurz im Hintergrund ausführen. Bei einem Abbruch zwischen den beiden Umbenennungen
muss gegebenenfalls der gesicherte Komponentenordner zurückgeschoben werden.

Bei einer Migration zwischen Datei-Installer und direktem HACS-Download zuerst ein vollständiges Backup
erstellen. Die bestehende Komponentendomain bleibt erhalten; Details zu Besitzprüfung, Migration und
Wiederherstellung stehen in der [englischen Anleitung](INSTALL.md).
