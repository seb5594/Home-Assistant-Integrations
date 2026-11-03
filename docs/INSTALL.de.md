# seb5594's Integration Hub

Der Hub fügt veröffentlichte Integrationsrepos zu HACS hinzu und meldet neue Projekte.
**Installation, Updates und Deinstallation bleiben vollständig bei HACS.** Es gibt keinen eigenen Installer.

## Einrichten

1. In **HACS → ⋮ → Benutzerdefinierte Repositories** die URL `https://github.com/seb5594/Home-Assistant-Integrations` als **Integration** hinzufügen.
2. Das neueste Release von **seb5594's Integration Hub** herunterladen und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste** bei der entdeckten Karte **seb5594's Integration Hub** auf **Konfigurieren** klicken. Fehlt die Karte, über **Integration hinzufügen** nach dem Hub suchen.
4. Automatisches Hinzufügen zu HACS und Benachrichtigungen aktivieren oder die Einstellungen anpassen.
5. HACS öffnen und dort die gewünschten Integrationen herunterladen. Anschließend den Neustart- und Einrichtungshinweisen von HACS und der jeweiligen Integration folgen.

Voraussetzungen: Home Assistant **2025.1.0** oder neuer und ein eingerichtetes HACS für die automatische
Registrierung. Die GitHub-Verbindung von HACS wird mitbenutzt; ein zusätzlicher Token oder Terminalzugriff
ist nicht nötig. Der öffentliche Katalog wird von `raw.githubusercontent.com` geladen.

Die automatische Entdeckung nutzt die mDNS-Ankündigung der eigenen Home-Assistant-Instanz.
Zeroconf ist in der Standardkonfiguration aktiv. Nach der Installation ist ein Neustart nötig.
Bereits eingerichtete oder ignorierte Hubs werden nicht erneut vorgeschlagen. Ohne Zeroconf oder
bei blockiertem mDNS bleibt das manuelle Hinzufügen möglich.

Die technische Domain des Hubs lautet `seb5594_integration_catalog`.
Bei einer bestehenden Installation mit der bisherigen Domain `integration_catalog` den alten Hub-Eintrag
unter Geräte & Dienste entfernen, den Hub über HACS aktualisieren beziehungsweise erneut herunterladen,
Home Assistant neu starten und den Hub erneut hinzufügen. Die einzelnen Integrationen und ihre
HACS-Repositories bleiben dabei bestehen. Die beiden Hub-Einstellungen danach erneut setzen.

## Ausschließlich veröffentlichte Release-Pakete

Der Katalog verwendet jeweils das **neueste veröffentlichte GitHub-Release**. Entwürfe und als Prerelease
markierte Veröffentlichungen werden ausgelassen. Aus dem hochgeladenen Integrations-ZIP werden Anzeigename
und Manifest-Version gelesen. Die Version muss zum Release-Tag passen; das übliche vorangestellte `v` ist erlaubt.

Versionsbadges, Release-Seite, ZIP-Download und Benachrichtigung verweisen auf dieses Release. Die Submodule
werden auf den Commit des Release-Tags gepinnt. Ein Repo ohne geeignetes Release-ZIP wird erst aufgenommen,
wenn eines veröffentlicht ist. Unveröffentlichte Branch-Stände werden nicht als Ersatz angeboten.

HACS behält seine reguläre Release- und Update-Verwaltung. Der Hub überschreibt keine bereits vom Nutzer
gewählten Versionen und pinnt HACS nicht dauerhaft auf einen veralteten Tag.
Auch der Hub selbst wird als getaggtes Release mit `seb5594_integration_catalog.zip` verteilt.
Reine Katalogänderungen erzeugen weder eine neue Hub-Version noch ein Hub-Release. Sie werden
über den öffentlichen Feed geladen. Neue Hub-Versionen sind Änderungen an der Integration selbst vorbehalten.

## Benachrichtigungen und Einstellungen

Der Hub prüft den Katalog stündlich. Der Repository-Workflow aktualisiert ihn ebenfalls stündlich sowie nach
Release-Benachrichtigungen. Für neu aufgenommene Projekte erscheint eine Home-Assistant-Benachrichtigung mit
Anzeigename, Release-Tag, ZIP-Download und HACS-Link. Wenn möglich, ist das Repository dann bereits in HACS.
Es wird nichts automatisch installiert oder neu gestartet.

Die erste Prüfung bildet den Ausgangsstand. Bekannte Repositories werden über Neustarts hinweg gespeichert.
Versionsupdates vorhandener Projekte verwaltet HACS. Bei Netzwerkfehlern bleibt der letzte bekannte
Release-Katalog erhalten. **Konfigurieren** schaltet Registrierung und Benachrichtigungen getrennt ab;
**Katalog aktualisieren** prüft sofort. Nach dem Start erfolgt ein zusätzlicher Versuch nach einer Minute.

Die automatische Registrierung verwendet eine **interne HACS-Laufzeitschnittstelle** und ist experimentell.
Die normale HACS-Validierung bleibt aktiv. Der Hub verändert keine HACS-Speicherdateien direkt und patcht HACS
nicht. Bei fehlendem oder inkompatiblem HACS meldet er den Fehler und versucht es später erneut.

## Entfernen und vorhandene Installationen

Beim Abschalten oder Entfernen des Hubs bleiben hinzugefügte HACS-Repositories und installierte Integrationen
bestehen. Diese wie gewohnt über HACS und Home Assistant verwalten. Der Hub übernimmt oder verändert keine
manuell installierten Komponentendateien.

Der frühere Datei-Installer aus dem Entwicklungsbranch wurde entfernt. Falls du ihn bereits getestet hast,
manuelle Installationen vor einer Migration zu HACS sichern; eine automatische Übernahme findet nicht statt.
