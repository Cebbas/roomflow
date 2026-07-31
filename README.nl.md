<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

[🇬🇧 English](README.md) | [🇸🇪 Svenska](README.sv.md) | [🇳🇴 Norsk](README.no.md) | [🇫🇮 Suomi](README.fi.md) | [🇩🇰 Dansk](README.da.md) | [🇩🇪 Deutsch](README.de.md) | [🇫🇷 Français](README.fr.md) | **🇳🇱 Nederlands**

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

> ⚠️ **Vroege fase:** deze integratie is in actieve ontwikkeling — verwacht
> wat ruwe randjes en af en toe breaking changes tussen releases.

Bedien verlichting en stopcontacten per kamer op basis van het tijdstip van
de dag — met optionele weekend-/afwezigheidsoverrides, overgangstijden,
fysieke knopkoppelingen en beweging-/drempelwaardegebaseerde automatisering.
Gebouwd voor Home Assistant als een aangepaste integratie plus een
bijbehorende Lovelace-kaart die ook als volledige zijpaneelpagina werkt.

## Waarom

De meeste "tijdstip van de dag"-verlichtingsopstellingen eindigen als een
stapel automatiseringen die lastig aan te passen zijn. RoomFlow geeft je
één plek om, per kamer en per apparaat, te bepalen: *wat moet deze
lamp/stopcontact 's ochtends, overdag, 's avonds, 's nachts doen — en
verandert dat in het weekend of als er niemand thuis is?* Daarbovenop komen
fysieke knoppen en beweging-/sensortriggers.

## Functies

- **Planning op basis van tijdstip van de dag** — definieer gedrag
  (aan/uit, helderheid, kleurtemperatuur) per apparaat voor zoveel
  periodes als je wilt. Periodes (standaard ochtend/dag/middag/avond/nacht)
  vormen een volledig door de gebruiker bewerkbare, op prioriteit
  geordende lijst: voeg vrij toe, verwijder, hernoem en herschik ze vanuit
  de kaart. Elke periode kan meerdere van de 5 bronnen tegelijk combineren,
  onafhankelijk aangevinkt: een ingebouwd **klokschema** (een starttijd),
  de **zonpositie** (een zonnegebeurtenis - dageraad/zonsopgang/
  zonnemiddag/zonsondergang/schemering - plus verschuiving), een
  **lichtsterktesensor** (een luxdrempel), een **bestaande boolean** (wijs
  naar een `binary_sensor`/`input_boolean` die je al hebt — "aan" betekent
  dat hij actief is), of een **bestaande sensor** (koppel een van zijn
  statuswaarden eraan, zodat dit werkt met elke tijdstip-van-de-dag-sensor
  in elke taal). Een periode is actief als OM HET EVEN WELKE van zijn
  ingeschakelde bronnen dat op dit moment aangeeft (OF-logica). Welke
  periode "huidig" is, wordt bepaald op basis van prioriteit: de eerste
  actieve periode in de lijst (bovenaan = hoogste prioriteit) wint — je
  kunt dus vrij brontypes mengen (bijv. een op lichtsterkte gebaseerde
  periode boven een op schema gebaseerde, zodat duisternis de klok kan
  overrulen). Zodra doordeweeks/weekend is ingesteld (zie hieronder), kunnen
  de schema- en zonbronnen elk een afwijkende tijd/zonnegebeurtenis voor het
  weekend instellen — bijv. de ochtend kan op zaterdag en zondag later
  beginnen — zonder dat daar een hele aparte periode voor nodig is.
- **Weekend- en afwezigheidsoverrides** (optioneel) — voor elk kies je een
  bestaande sensor (een gewone aan/uit-`binary_sensor` werkt ook — vertel
  RoomFlow gewoon welke polariteit "aan" betekent voor doordeweeks/weekend),
  een ingebouwde optie (kies welke weekdagen als weekend tellen; kies een
  of meer `person.*`-entiteiten voor thuis/afwezig), of laat het ongebruikt.
  Deze twee keuzes, en de tijdstip-van-de-dag-bron hierboven, zijn volledig
  onafhankelijk — combineer vrij. Overschrijf het standaardgedrag voor
  specifieke apparaten in het weekend of bij afwezigheid. Prioriteit:
  **afwezig > weekend > standaard**.
- **Kamerspecifieke aangepaste voorwaarden** — naast de huisbrede weekend-/
  afwezigheidsassen kan elke kamer zijn eigen geordende lijst met
  voorwaarden definiëren (een naam + een entiteit + de status die betekent
  dat hij actief is), gecontroleerd op volgorde van prioriteit *boven*
  afwezig/weekend/standaard. Elke voorwaarde krijgt zijn eigen
  gedragsvariant per periode (ochtend/dag/middag/avond/nacht) en per
  apparaat, net als weekend/afwezig — handig voor gedrag dat gekoppeld is
  aan iets specifieks voor die kamer (bijv. de aanwezigheid van een
  bepaalde persoon) in plaats van de status van het hele huis.
- **Overgangstijden** — een globale standaardwaarde per periode, per
  apparaat/periode overschrijfbaar.
- **Fysieke knoppen** — koppel een willekeurige entiteit (bijv. een
  Zigbee-knop die verschijnt als een `event`- of `sensor`-entiteit) aan een
  actie: kamer omschakelen, uitschakelen, het geplande gedrag nu
  uitvoeren, of een specifieke periode forceren ongeacht de werkelijke
  tijd.
- **Beweging- en drempelwaardetriggers per kamer** — combineer meerdere
  voorwaarden met OF-logica: bewegingssensoren en/of numerieke
  drempelwaardesensoren (bijv. "vochtigheid boven 65%"). De kamer wordt als
  "actief" beschouwd zodra een voorwaarde waar is, voert onmiddellijk zijn
  geplande gedrag uit, en elk bewegingsgeactiveerd apparaat (per apparaat
  gekozen, met zijn eigen uitschakelvertraging die de standaardwaarde van
  de kamer overschrijft) schakelt weer uit zodra niets meer waar is —
  optioneel door eerst te dimmen naar een lage helderheid als
  waarschuwing (beweging tijdens dat venster herstelt volledige
  helderheid in plaats van uit te schakelen). Een fysieke knopdruk sluit
  dat apparaat uit van bewegingscontrole tot de volgende verse
  bewegingscyclus, zodat het niet meteen wordt overschreven.
- **Kaartinterface** — beheer *alles* (kamers, apparaten, knoppen,
  beweging en alle bovenstaande tijdstip-van-de-dag-/doordeweeks-weekend-/
  thuis-afwezig-instellingen) vanuit een eigen kaart met tabbladen, hetzij
  ingebed in een dashboard, hetzij als eigen automatisch geregistreerde
  zijpaneelpagina. Niets wordt geconfigureerd via de ingebouwde "Integratie
  toevoegen"-wizard van Home Assistant — die stap voegt RoomFlow slechts
  met één klik toe; al het andere staat in het Instellingen-tabblad van de
  kaart en geldt onmiddellijk, geen herstart nodig.
- **Live status & handmatige test** — bekijk de werkelijke huidige status
  van elk apparaat, en activeer "nu testen" per kamer of voor alles
  tegelijk.
- **Diagnostiek** — download een diagnostiekbestand (Instellingen →
  Apparaten & diensten → RoomFlow → Diagnostiek downloaden) voor
  bugrapporten, zonder je specifieke apparaat-entity_id's bloot te leggen.
- **Beschikbaar als echte entiteiten** — RoomFlow maakt drie gewone
  sensor-entiteiten aan (huidige periode, dagtype, thuisstatus) plus één
  binary_sensor per periode (ochtend/dag/middag/avond/nacht — "aan" precies
  wanneer die periode de huidig geldende is, ongeacht welke bron(nen) dat
  bepaalden) die verschijnen als elke andere entiteit: bruikbaar in je
  eigen automatiseringen/dashboards. Hun apparaatnaam en gebied worden
  ingesteld vanuit het Instellingen-tabblad van de kaart, geen noodzaak om
  ze achteraf op te zoeken onder Entiteiten.
- **Veerkrachtig** — een falend apparaat logt een waarschuwing in plaats
  van de rest van de kamer te blokkeren.

## Installatie

### Via HACS (aangepaste repository)

1. HACS → Integraties → menu met drie stippen → **Aangepaste
   repositories**
2. Voeg de URL van deze repository toe, categorie **Integration**
3. Installeer "RoomFlow", herstart Home Assistant

### Handmatig

1. Kopieer `custom_components/roomflow` naar `config/custom_components/`
   (de kaart zit erin gebundeld, in `custom_components/roomflow/www/` —
   geen aparte kopie nodig)
2. Herstart Home Assistant

### Instellen

1. **Instellingen → Apparaten & diensten → Integratie toevoegen →
   RoomFlow** — er is niets in te vullen, gewoon bevestigen. Al het andere
   gebeurt in de kaart.

   RoomFlow serveert zijn eigen kaart en registreert deze automatisch —
   geen `config/www`-kopie en geen handmatige invoer onder **Instellingen
   → Dashboards → Bronnen** nodig. Het voegt zichzelf ook toe als pagina
   in het zijpaneel. Je kunt de kaart ook handmatig aan een dashboard
   toevoegen:
   ```yaml
   type: custom:roomflow-card
   ```
2. Open de RoomFlow-kaart (zijpaneel of dashboard) → tabblad **⚙
   Instellingen**, en configureer:
   - **Tijdstip-van-de-dag-periodes** — een geordende lijst (bovenaan =
     hoogste prioriteit), startend met de 5 standaardwaarden
     (ochtend/dag/middag/avond/nacht). Voeg vrij toe, verwijder, hernoem
     of herschik (↑/↓). Elke periode kan een willekeurige combinatie van
     5 bronnen aanvinken — hij is actief als OM HET EVEN WELKE aangevinkte
     bron dat op dit moment aangeeft (OF-logica):
     - Schema: een starttijd.
     - Zonpositie: een zonnegebeurtenis (dageraad/zonsopgang/
       zonnemiddag/zonsondergang/schemering) + een optionele
       +/- minuutverschuiving.
     - Lichtsterkte: een luxsensor + een luxdrempel.
     - Bestaande boolean: een `binary_sensor`/`input_boolean` die precies
       "aan" is wanneer deze periode actief moet zijn.
     - Bestaande sensor: een entiteit + de statuswaarde die betekent dat
       deze periode actief is (werkt met elke tijdstip-van-de-dag-sensor,
       in elke taal).
     De huidige periode is degene die het hoogst in de lijst staat en op
     dit moment actief is. Zodra Doordeweeks/weekend hieronder is ingesteld,
     krijgen Schema en Zonpositie elk een optionele weekend-override — een
     aparte starttijd of zonnegebeurtenis, alleen voor weekenddagen.
   - **Doordeweeks/weekend** en **Thuis/afwezig** — elk ofwel "niet
     gebruikt", een bestaande sensor, of een ingebouwde optie
     (weekdagselectie; een of meer `person.*`-entiteiten), onafhankelijk
     van al het andere.
   - **Apparaat** — naam en gebied voor RoomFlows eigen sensoren.

   Elke wijziging hier geldt onmiddellijk — geen herstart, niets apart op
   te slaan.

## Hoe het werkt

Elke kamer bevat apparaten (lampen/stopcontacten). Elk apparaat heeft een
gedrag per periode, gekozen in deze volgorde wanneer RoomFlow het
toepast:

1. **Afwezig**-override, indien ingeschakeld voor die periode en de
   thuis-/afwezigheidsbron op dit moment "afwezig" meldt
2. **Weekend**-override, indien ingeschakeld voor die periode en de
   doordeweeks-/weekendbron op dit moment een weekendwaarde meldt
3. **Standaard**-gedrag

RoomFlow past wijzigingen automatisch opnieuw toe zodra een
geconfigureerde bron verandert: sensorgebaseerde invoer reageert op
statuswijzigingen, ingebouwde reageren op hun eigen klok (een
schemagrens, of middernacht voor de weekdagselectie) — en het reageert
ook onmiddellijk op knopdrukken en de door jou geconfigureerde beweging-/
drempelwaardetriggers.

## Bijdragen

Bugmeldingen en pull requests zijn welkom. Dit is een relatief jong
project — verwacht wat ruwe randjes, vooral rond geavanceerdere
combinaties van voorwaarden en extra apparaattypes (climate,
media_player enz. zijn voor de hand liggende volgende stappen).

## Ondersteunde talen

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl) —
deze README, de eigen interface van de kaart en de config flow volgen
allemaal dezelfde 8 talen. De kaart kiest automatisch zijn taal op basis
van de taalinstelling van Home Assistant.

## Licentie

MIT — zie [LICENSE](LICENSE).
