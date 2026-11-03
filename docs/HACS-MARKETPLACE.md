# HACS → Marketplace: Übergang und Erkennung

Der Hub ist für den angekündigten Wechsel zum eingebauten Marketplace vorbereitet.
Die Auswahl erfolgt anhand der **lokal laufenden Home-Assistant-Installation**.
Eine Ankündigung, das Kalenderdatum oder ein neues GitHub-Release allein schaltet
einen bestehenden HA-Server nicht um.

## Offizieller Stand und Grenzen

Laut [Ankündigung von HACS](https://github.com/hacs/integration/issues/5590) und
[Marketplace-Dokumentation](https://contributors.home-assistant.io/marketplace/)
ist der Übergang für HA 2026.11 vorgesehen. Beim Abgleich am 3. November 2026 war
HA 2026.10.4 die neueste auf PyPI veröffentlichte stabile Version.

Die Vorbereitung basiert auf Core-Commit
[`25b9c24443ec056582a1b17a27b32602ddb766e9`](https://github.com/home-assistant/core/tree/25b9c24443ec056582a1b17a27b32602ddb766e9).
Der geprüfte Quellstand ist damit nachvollziehbar, auch wenn `dev` später geändert wird.
Eine stabile öffentliche API für das Hinzufügen von Repositories durch andere
Integrationen ist dadurch nicht zugesichert. Der Adapter bleibt experimentell.
Vertragstests und simulierte zukünftige Versionsnummern ersetzen keinen vollständigen
Lauf mit dem später veröffentlichten Home Assistant 2026.11.

## Verbindliche Auswahlregeln

Die Grenze `MARKETPLACE_FROM = "2026.11.0"` steht zentral in
[`hacs_bridge.py`](../custom_components/seb5594_integration_catalog/hacs_bridge.py).
Versionsnummern werden mit Home Assistants `AwesomeVersion` verglichen, nicht als Text.

| Lokaler Befund | Auswahl | Verhalten |
| --- | --- | --- |
| HA ab 2026.11.0, unabhängig vom Einrichtungsstand | Marketplace zwingend | Fehlende Einrichtung melden; kein Rückfall auf HACS |
| Core erklärt HACS als durch `marketplace` ersetzt | Marketplace zwingend | Gilt auch vor der Versionsgrenze |
| HA liefert eine eingebaute `marketplace`-Integration mit | Marketplace zwingend | Erkennt beispielsweise Betas oder Rückportierungen |
| Ein Marketplace-Konfigurationseintrag existiert | Marketplace zwingend | Auch ein deaktivierter oder noch startender Eintrag verhindert den Rückfall |
| Keiner dieser Befunde liegt vor | Bisheriges HACS | Manager aus `hass.data["hacs"]` verwenden |

Ein Marketplace-Manager wird ausschließlich aus `runtime_data` eines **geladenen,
nicht deaktivierten** Eintrags übernommen. Eine bloße Versionsnummer erzeugt keinen
Manager. Ist er noch nicht bereit, bleibt die automatische Registrierung aus und
wird später erneut versucht. Ein noch vorhandener HACS-Manager wird dann nicht verwendet.

Präreleases unterhalb von 2026.11.0 werden über ihre tatsächlich vorhandenen
Integrationen und die Ersetzungsregel erkannt. Unbekannte Versionsformate verlassen
sich ebenfalls auf diese Befunde. Ein HA-Fork mit Versionsnummer ab 2026.11.0, aber
ohne Marketplace, erhält bewusst keinen automatischen Legacy-Fallback.

## Geprüfter Schnittstellenvertrag

Der Core-Quellstand legt den Manager im geladenen Konfigurationseintrag ab:
[`async_get_marketplace`](https://github.com/home-assistant/core/blob/25b9c24443ec056582a1b17a27b32602ddb766e9/homeassistant/components/marketplace/base.py).
Die Ersetzungsregel steht in
[`BLOCKED_CUSTOM_INTEGRATIONS`](https://github.com/home-assistant/core/blob/25b9c24443ec056582a1b17a27b32602ddb766e9/homeassistant/loader.py).

Vor einer Registrierung prüft der Hub:

- Store nicht deaktiviert und Startphase abgeschlossen.
- Kategorie `integration` verfügbar.
- Asynchrone Registrierung mit `repository_full_name`, `category` und `check=True`.
- Synchroner Lookup über `repositories.get_by_full_name(repository)` mit passender Signatur.
- Asynchrones Speichern über `data.async_write()` ohne zusätzliche Pflichtargumente.

Die normale Store-Validierung und seine Sperr-/Umbenennungsregeln bleiben aktiv.
Bei einer inkompatiblen Signatur wird vor der ersten Registrierung abgebrochen.
Der Hub importiert keinen Marketplace-Komponentencode, editiert keine Store-Dateien
direkt, migriert keine HACS-Installation und installiert keine Integrationsdateien.
Installation und Updates bleiben bei HACS beziehungsweise Marketplace.

## Laufende Erkennung und Diagnose

Die Auswahl wird bei **jedem Abruf** neu ermittelt: beim Start, nach einer Minute,
stündlich sowie über **Katalog aktualisieren**. Ein zwischenzeitlich gestarteter
Marketplace wird beim nächsten Abruf verwendet. Dafür muss weder der Hub aktualisiert
noch seine Konfiguration neu angelegt werden. Ein HA-Upgrade selbst benötigt weiterhin
seinen regulären Neustart.

Am Hub-Eintrag unter Geräte & Dienste **Diagnosedaten herunterladen** wählen.
`repository_store` enthält:

| Feld | Bedeutung |
| --- | --- |
| `backend` | `HACS` oder `Marketplace` |
| `home_assistant_version` | Lokal erkannte HA-Version |
| `marketplace_from` | Angekündigte stabile Versionsgrenze |
| `signals` | `ha_version`, `core_replacement`, `builtin_integration`, `config_entry` |
| `available` | Manager und benötigte API einsatzbereit |
| `reason` | Fehlende Einrichtung, Startphase, deaktivierter Store oder API-Abweichung |

Die Diagnose ruft keine Registrierung und keinen Speichervorgang auf. Sie exportiert
weder Managerobjekte noch Token oder Einrichtungsdaten des Stores. Neue Projekte
werden weiterhin über den Katalogfeed erkannt. Katalogänderungen erzeugen kein Hub-Release.

## Prüfung beim tatsächlichen Release

1. Offiziellen Release-Stand und Versionsgrenze mit den oben verlinkten Quellen abgleichen.
   Bei einer Verschiebung `MARKETPLACE_FROM` vor dem betroffenen HA-Upgrade anpassen.
2. Einen zu dieser HA-Version passenden Test-Plugin-Stand zur CI-Matrix hinzufügen.
   Die bisherigen fünf realen HA-Testversionen bleiben erhalten.
3. Einrichtung, Discovery, Optionen und Katalogabruf unter der veröffentlichten Version prüfen.
4. Registrierung eines veröffentlichten Katalogrepos im echten Marketplace prüfen:
   einmal hinzufügen, wiederholten Abruf ohne Duplikat prüfen und Persistenz nach Neustart prüfen.
5. Nicht eingerichteten, startenden, deaktivierten und inkompatiblen Marketplace prüfen.
   Keine dieser Situationen darf die alte HACS-Instanz verwenden.
6. Erst nach diesem Lauf die neue HA-Version als vollständig laufzeitgetestet dokumentieren.

Aktuell sichern Tests die Versionsgrenze, Voraberkennung, Wiederaufnahme nach Start,
fehlenden Legacy-Fallback, API-Abweichungen vor Schreibzugriffen und den Diagnoseexport ab.
