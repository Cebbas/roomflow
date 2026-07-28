<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

[🇬🇧 English](README.md) | [🇸🇪 Svenska](README.sv.md) | [🇳🇴 Norsk](README.no.md) | [🇫🇮 Suomi](README.fi.md) | [🇩🇰 Dansk](README.da.md) | **🇩🇪 Deutsch** | [🇫🇷 Français](README.fr.md) | [🇳🇱 Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

Steuert Lampen und Steckdosen raumweise basierend auf der Tageszeit — mit
optionalen Wochenend-/Abwesenheits-Ausnahmen, Übergangszeiten, physischen
Tastenbindungen und bewegungs-/schwellenwertbasierter Automatisierung. Für
Home Assistant gebaut als eigenständige Integration plus einer begleitenden
Lovelace-Karte, die auch als vollständige Seitenleisten-Seite funktioniert.

## Warum

Die meisten "Tageszeit"-basierten Beleuchtungs-Setups enden als ein Haufen
Automatisierungen, die mühsam anzupassen sind. RoomFlow gibt dir einen
einzigen Ort, um pro Raum und pro Gerät festzulegen: *Was soll diese
Lampe/Steckdose morgens, tagsüber, abends, nachts tun — und ändert sich das
am Wochenende oder wenn niemand zu Hause ist?* Darauf aufbauend kommen
physische Tasten und Bewegungs-/Sensor-Trigger.

## Funktionen

- **Tageszeit-Zeitplanung** — definiere Verhalten (an/aus, Helligkeit,
  Farbtemperatur) pro Gerät für so viele Zeiträume, wie du möchtest.
  Zeiträume (standardmäßig Morgen/Tag/Nachmittag/Abend/Nacht) sind eine
  vollständig benutzerbearbeitbare, priorisierte Liste: füge sie frei über
  die Karte hinzu, entferne, benenne um oder ordne sie neu an. Jeder
  Zeitraum kann beliebig viele der 5 Quellen gleichzeitig kombinieren,
  unabhängig angekreuzt: einen eingebauten **Uhrzeitplan** (eine
  Startzeit), die **Sonnenposition** (ein Sonnenereignis -
  Morgendämmerung/Sonnenaufgang/Mittag/Sonnenuntergang/Abenddämmerung -
  plus Versatz), einen **Helligkeitssensor** (ein Lux-Schwellenwert), einen
  **vorhandenen Boolean** (zeigt auf einen bereits vorhandenen
  `binary_sensor`/`input_boolean` — "an" bedeutet, dass er aktiv ist), oder
  einen **vorhandenen Sensor** (ordnet einen seiner Zustandswerte zu, damit
  dies mit jedem Tageszeit-Sensor in jeder Sprache funktioniert. Ein
  Zeitraum ist aktiv, wenn IRGENDEINE seiner aktivierten Quellen dies
  gerade sagt (ODER-Logik). Welcher Zeitraum "aktuell" ist, wird nach
  Priorität entschieden: der erste aktive Zeitraum in der Liste (oben =
  höchste Priorität) gewinnt — so kannst du Quelltypen frei mischen (z. B.
  einen helligkeitsbasierten Zeitraum über einem zeitplanbasierten, damit
  Dunkelheit die Uhr außer Kraft setzen kann).
- **Wochenend- und Abwesenheits-Ausnahmen** (optional) — für jede wählst du
  einen vorhandenen Sensor (ein einfacher an/aus-`binary_sensor`
  funktioniert auch — sag RoomFlow einfach, welche Polarität "an" für
  Werktag/Wochenende bedeutet), eine eingebaute Option (wähle, welche
  Wochentage als Wochenende zählen; wähle eine oder mehrere
  `person.*`-Entitäten für zu Hause/abwesend), oder lass es ungenutzt.
  Diese beiden Entscheidungen und die Tageszeit-Quelle oben sind völlig
  unabhängig — mische frei. Setze das Standardverhalten für bestimmte
  Geräte am Wochenende oder bei Abwesenheit außer Kraft. Priorität:
  **abwesend > Wochenende > Standard**.
- **Raumspezifische benutzerdefinierte Bedingungen** — über die
  hausweiten Wochenend-/Abwesenheits-Achsen hinaus kann jeder Raum seine
  eigene geordnete Liste von Bedingungen definieren (ein Name + eine
  Entität + der Zustand, der bedeutet, dass sie aktiv ist), geprüft in
  Prioritätsreihenfolge *über* abwesend/Wochenende/Standard. Jede
  Bedingung erhält ihre eigene Verhaltensvariante pro Zeitraum
  (Morgen/Tag/Nachmittag/Abend/Nacht) und Gerät, genau wie
  Wochenende/abwesend — nützlich für Verhalten, das an etwas Spezifisches
  für diesen Raum gebunden ist (z. B. die Anwesenheit einer bestimmten
  Person), statt an den Zustand des gesamten Hauses.
- **Übergangszeiten** — ein globaler Standardwert pro Zeitraum, pro
  Gerät/Zeitraum überschreibbar.
- **Physische Tasten** — binde eine beliebige Entität (z. B. eine
  Zigbee-Taste, die als `event`- oder `sensor`-Entität erscheint) an eine
  Aktion: Raum umschalten, ausschalten, das geplante Verhalten sofort
  ausführen, oder einen bestimmten Zeitraum unabhängig von der
  tatsächlichen Uhrzeit erzwingen.
- **Bewegungs- und Schwellenwert-Trigger pro Raum** — kombiniere mehrere
  Bedingungen mit ODER-Logik: Bewegungssensoren und/oder numerische
  Schwellenwertsensoren (z. B. "Luftfeuchtigkeit über 65%"). Der Raum gilt
  als "aktiv", sobald eine Bedingung wahr ist, führt sein geplantes
  Verhalten sofort aus, und jedes bewegungsaktivierte Gerät (pro Gerät
  ausgewählt, mit eigener Ausschaltverzögerung, die den Raumstandard
  überschreibt) schaltet sich wieder aus, sobald nichts mehr wahr ist —
  optional durch vorheriges Dimmen auf eine niedrige Helligkeit als
  Warnung (Bewegung während dieses Fensters stellt die volle Helligkeit
  wieder her, statt auszuschalten). Ein physischer Tastendruck sperrt
  dieses Gerät bis zum nächsten frischen Bewegungszyklus von der
  Bewegungssteuerung aus, sodass es nicht sofort überschrieben wird.
- **Karten-Oberfläche** — verwalte *alles* (Räume, Geräte, Tasten,
  Bewegung und alle oben genannten Tageszeit-/Werktag-Wochenende-/
  zu-Hause-abwesend-Einstellungen) über eine eigene, in Tabs organisierte
  Karte, entweder eingebettet in ein Dashboard oder als eigene, automatisch
  registrierte Seitenleisten-Seite. Nichts wird über Home Assistants
  eingebauten "Integration hinzufügen"-Assistenten konfiguriert — dieser
  Schritt fügt RoomFlow nur mit einem einzigen Klick hinzu; alles andere
  befindet sich im Einstellungen-Tab der Karte und gilt sofort, kein
  Neustart nötig.
- **Live-Status & manueller Test** — sieh den tatsächlichen aktuellen
  Zustand jedes Geräts und löse "Jetzt testen" pro Raum oder für alles auf
  einmal aus.
- **Diagnose** — lade eine Diagnosedatei herunter (Einstellungen → Geräte
  & Dienste → RoomFlow → Diagnose herunterladen) für Fehlerberichte, ohne
  deine spezifischen Geräte-entity_ids offenzulegen.
- **Als echte Entitäten verfügbar** — RoomFlow erstellt drei gewöhnliche
  Sensor-Entitäten (aktueller Zeitraum, Tagestyp, Zuhause-Status) plus
  einen binary_sensor pro Zeitraum (Morgen/Tag/Nachmittag/Abend/Nacht —
  "an" genau dann, wenn dieser Zeitraum der aktuell geltende ist,
  unabhängig davon, welche Quelle(n) das entschieden haben), die wie jede
  andere Entität erscheinen: nutzbar in deinen eigenen
  Automatisierungen/Dashboards. Ihr Gerätename und Bereich werden über den
  Einstellungen-Tab der Karte gesetzt, kein Suchen unter Entitäten danach
  nötig.
- **Robust** — ein fehlerhaftes Gerät protokolliert eine Warnung, statt
  den Rest des Raums zu blockieren.

## Installation

### Über HACS (benutzerdefiniertes Repository)

1. HACS → Integrationen → Drei-Punkte-Menü → **Benutzerdefinierte
   Repositories**
2. Füge die URL dieses Repositorys hinzu, Kategorie **Integration**
3. Installiere "RoomFlow", starte Home Assistant neu

### Manuell

1. Kopiere `custom_components/roomflow` nach `config/custom_components/`
   (die Karte ist darin enthalten, unter
   `custom_components/roomflow/www/` — kein separates Kopieren nötig)
2. Starte Home Assistant neu

### Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen →
   RoomFlow** — es gibt nichts auszufüllen, nur bestätigen. Alles andere
   geschieht in der Karte.

   RoomFlow stellt seine eigene Karte bereit und registriert sie
   automatisch — kein `config/www`-Kopieren und kein manueller Eintrag
   unter **Einstellungen → Dashboards → Ressourcen** nötig. Es fügt sich
   außerdem selbst als Seite in der Seitenleiste hinzu. Du kannst die Karte
   auch manuell zu einem Dashboard hinzufügen:
   ```yaml
   type: custom:roomflow-card
   ```
2. Öffne die RoomFlow-Karte (Seitenleiste oder Dashboard) → **⚙
   Einstellungen**-Tab, und konfiguriere:
   - **Tageszeit-Zeiträume** — eine geordnete Liste (oben = höchste
     Priorität), ausgehend von den 5 Standardwerten
     (Morgen/Tag/Nachmittag/Abend/Nacht). Füge frei hinzu, entferne,
     benenne um oder ordne neu an (↑/↓). Jeder Zeitraum kann eine beliebige
     Kombination der 5 Quellen ankreuzen — er ist aktiv, wenn IRGENDEINE
     angekreuzte gerade zutrifft (ODER-Logik):
     - Zeitplan: eine Startzeit.
     - Sonnenposition: ein Sonnenereignis (Morgendämmerung/Sonnenaufgang/
       Mittag/Sonnenuntergang/Abenddämmerung) + ein optionaler
       +/- Minuten-Versatz.
     - Helligkeit: ein Lux-Sensor + ein Lux-Schwellenwert.
     - Vorhandener Boolean: ein `binary_sensor`/`input_boolean`, der genau
       dann "an" ist, wenn dieser Zeitraum aktiv sein soll.
     - Vorhandener Sensor: eine Entität + der Zustandswert, der bedeutet,
       dass dieser Zeitraum aktiv ist (funktioniert mit jedem
       Tageszeit-Sensor, in jeder Sprache).
     Der aktuelle Zeitraum ist derjenige, der in der Liste am höchsten
     steht und gerade aktiv ist.
   - **Werktag/Wochenende** und **Zu Hause/Abwesend** — jeweils entweder
     "nicht verwendet", ein vorhandener Sensor, oder eine eingebaute Option
     (Wochentagsauswahl; eine oder mehrere `person.*`-Entitäten),
     unabhängig von allem anderen.
   - **Gerät** — Name und Bereich für RoomFlows eigene Sensoren.

   Jede Änderung hier gilt sofort — kein Neustart, nichts separat zu
   speichern.

## Funktionsweise

Jeder Raum enthält Geräte (Lampen/Steckdosen). Jedes Gerät hat ein
Verhalten pro Zeitraum, ausgewählt in dieser Reihenfolge, wenn RoomFlow es
anwendet:

1. **Abwesend**-Ausnahme, falls für diesen Zeitraum aktiviert und die
   Zuhause-/Abwesend-Quelle gerade "abwesend" meldet
2. **Wochenende**-Ausnahme, falls für diesen Zeitraum aktiviert und die
   Werktag-/Wochenende-Quelle gerade einen Wochenendwert meldet
3. **Standard**-Verhalten

RoomFlow wendet Änderungen automatisch erneut an, sobald sich eine
konfigurierte Quelle ändert: sensorbasierte Eingaben reagieren auf
Zustandsänderungen, eingebaute reagieren auf ihre eigene Uhr (eine
Zeitplangrenze oder Mitternacht für die Wochentagsauswahl) — und es
reagiert auch sofort auf Tastendrücke und die von dir konfigurierten
Bewegungs-/Schwellenwert-Trigger.

## Mitwirken

Fehlerberichte und Pull Requests sind willkommen. Dies ist ein relativ
junges Projekt — erwarte einige raue Kanten, besonders bei fortgeschritteneren
Bedingungskombinationen und zusätzlichen Gerätetypen (climate,
media_player usw. sind naheliegende nächste Schritte).

## Unterstützte Sprachen

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl)

## Lizenz

MIT — siehe [LICENSE](LICENSE).
