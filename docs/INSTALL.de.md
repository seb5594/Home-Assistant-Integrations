# Ein Sammelrepo für die Installation

HACS unterstützt pro Repository eine Integration. Deshalb enthält dieses Repo den experimentellen
**Home Assistant Integration Catalog**: HACS installiert diesen Katalog, und dessen Einrichtungsdialog
installiert die ausgewählten Integrationen. Die ursprünglichen Domains und Anzeigenamen bleiben erhalten.

## Einrichten

1. In **HACS → ⋮ → Benutzerdefinierte Repositories** die URL `https://github.com/seb5594/Home-Assistant-Integrations` als **Integration** hinzufügen.
2. **Home Assistant Integration Catalog (experimental installer)** herunterladen und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Home Assistant Integration Catalog** suchen.
4. Die gewünschten Integrationen auswählen, den Hinweis zum Installer bestätigen und das Ergebnis abwarten.
5. Nach einer Installation Home Assistant neu starten. Danach die gewünschten Integrationen unter ihren ursprünglichen Namen einrichten. Falls eine Integration YAML benötigt, gilt weiterhin deren Anleitung.

Der Katalog benötigt mindestens Home Assistant **2025.1.0**. Neuere Mindestversionen der einzelnen Integrationen
werden vor der Installation geprüft. Für den Download wird Internetzugriff auf `codeload.github.com` benötigt.
Ein GitHub-Token, Git oder ein Terminal sind für die normale Installation nicht erforderlich.

## Aktualisieren

Den Katalog in HACS aktualisieren und Home Assistant neu starten. Danach beim Katalog **Konfigurieren** öffnen,
die gewünschten Komponenten auswählen und installieren. Bei Änderungen ist ein weiterer Neustart erforderlich.
Der Dialog zeigt die Versionen des aktuellen Katalogs. HACS verwaltet ausschließlich den Katalog; für die
einzelnen Komponenten gibt es dabei keine eigenen HACS-Update-Einträge.

Der Katalog verwendet fest gepinnte Commits der Standardbranches. Darin können auch noch nicht veröffentlichte
Änderungen enthalten sein. Wer einzelne Releases auswählen möchte, nutzt die jeweiligen Einzelrepos in HACS.
Beim normalen Start verändert der Katalog keine Komponenten. Abwählen bedeutet **nicht deinstallieren**.

## Vorhandene Installationen und Sicherungen

Vorhandene manuell oder separat über HACS installierte Komponenten werden abgelehnt. Auch lokal veränderte
Dateien werden nicht überschrieben. Eine Komponente sollte immer nur durch einen der beiden Wege verwaltet werden.
Für eine Migration zuerst ein Home-Assistant-Backup erstellen, Home Assistant stoppen und den bisherigen
Komponentenordner außerhalb von `custom_components/` sichern. Den separaten HACS-Download gegebenenfalls entfernen.
Danach Home Assistant starten, über den Katalog installieren und erneut starten. Der Konfigurationseintrag der
ursprünglichen Integration kann erhalten bleiben, da ihre Domain unverändert bleibt.

Ersetzte Versionen liegen unter `<config>/.integration_catalog_backups/<domain>-<UTC-Zeitstempel>/`.
Zur Wiederherstellung Home Assistant stoppen, den aktuellen Komponentenordner beiseitelegen und die Sicherung
nach `custom_components/<domain>/` zurückschieben. Abhängigkeiten und Konfigurationsmigrationen können zusätzlich
die Wiederherstellung eines vollständigen Home-Assistant-Backups erfordern.

Nach einem Prozessabbruch kann `<config>/.integration-catalog.lock` zurückbleiben. Diese Datei nur entfernen,
wenn keine Installation mehr läuft, am besten bei gestopptem Home Assistant. Ein abgebrochener Dialog kann
seinen Download noch kurz im Hintergrund ausführen. Bei einem Abbruch zwischen den beiden Umbenennungen
muss gegebenenfalls der gesicherte Komponentenordner zurückgeschoben werden.

Wird der Katalog entfernt, bleiben installierte Komponenten und Backups bestehen. Einzelne Komponenten über
ihre Home-Assistant-Konfiguration entfernen, Home Assistant stoppen und anschließend den zugehörigen
`custom_components/<domain>/`-Ordner entfernen. YAML-Konfigurationen entsprechend der Projektanleitung aufräumen.

Dateien werden vor der Installation gegen die SHA-256-Prüfsummen des Katalogs geprüft. Downloads und Vorprüfungen
aller ausgewählten Komponenten erfolgen vor der ersten Änderung. Scheitert später ein Dateisystemzugriff beim
Anwenden, können zuvor abgearbeitete Komponenten bereits installiert sein; die Fehlermeldung nennt sie.

Weitere Details: [English installation and recovery guide](INSTALL.md).
