<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

[🇬🇧 English](README.md) | **🇸🇪 Svenska** | [🇳🇴 Norsk](README.no.md) | [🇫🇮 Suomi](README.fi.md) | [🇩🇰 Dansk](README.da.md) | [🇩🇪 Deutsch](README.de.md) | [🇫🇷 Français](README.fr.md) | [🇳🇱 Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

Styr lampor och uttag per rum baserat på tid på dygnet — med valfria
helg-/borta-undantag, transitionstider, fysiska knappbindningar och
rörelse-/tröskelvärdesbaserad automation. Byggd för Home Assistant som en
egen integration plus ett medföljande Lovelace-kort som även fungerar som en
egen sidopanelssida.

## Varför

De flesta "tid på dygnet"-baserade ljusuppsättningar slutar som en hög
automationer som är jobbiga att justera. RoomFlow ger dig en enda plats att
säga, per rum och per enhet: *vad ska den här lampan/uttaget göra på
morgonen, under dagen, på kvällen, på natten — och ändras det på helger
eller när ingen är hemma?* Sedan lägger den till fysiska knappar och
rörelse-/sensortriggers ovanpå det.

## Funktioner

- **Schemaläggning för tid på dygnet** — definiera beteende (på/av,
  ljusstyrka, färgtemperatur) per enhet för hur många perioder du vill.
  Perioder (morgon/dag/eftermiddag/kväll/natt som standard) är en helt
  användarredigerbar, prioritetsordnad lista: lägg till, ta bort, döp om och
  ändra ordning fritt från kortet. Varje period kan kombinera valfritt antal
  av 5 källor samtidigt, oberoende ikryssade: ett inbyggt **klockschema**
  (en starttid), **solens position** (en soleventyp - gryning/soluppgång/
  solmiddag/solnedgång/skymning - plus offset), en **luxsensor** (ett
  ljusstyrketröskelvärde), en **befintlig boolean** (peka på en
  `binary_sensor`/`input_boolean` du redan har — "på" betyder att den är
  aktiv), eller en **befintlig sensor** (mappa ett av dess tillståndsvärden
  till den, så det fungerar med vilken tid-på-dygnet-sensor som helst på
  vilket språk som helst). En period är aktiv om NÅGON av dess aktiverade
  källor just nu säger det (ELLER-logik). Vilken period som är "aktuell"
  avgörs av prioritetsordning: den första aktiva perioden i listan (överst =
  högst prioritet) vinner — så du kan fritt blanda källtyper (t.ex. en
  luxbaserad period ovanför en schemabaserad för att låta mörker
  åsidosätta klockan).
- **Helg- och borta-undantag** (valfritt) — för vardera väljer du en
  befintlig sensor (en vanlig på/av-`binary_sensor` funkar också — tala bara
  om för RoomFlow vilken polaritet "på" betyder för vardag/helg), ett
  inbyggt alternativ (välj vilka veckodagar som räknas som helg; välj en
  eller flera `person.*`-entiteter för hemma/borta), eller lämna det oanvänt.
  De här två valen, och tid-på-dygnet-källan ovan, är helt oberoende av
  varandra — blanda fritt. Åsidosätt standardbeteendet för specifika enheter
  under helger eller när ingen är hemma. Prioritetsordning:
  **borta > helg > standard**.
- **Rumsspecifika egna villkor** — utöver de husövergripande helg-/borta-
  axlarna kan varje rum definiera sin egen ordnade lista av villkor (ett
  namn + en entitet + tillståndet som betyder att det är aktivt), kontrollerade
  i prioritetsordning *ovanför* borta/helg/standard. Varje villkor får sin
  egen per-period (morgon/dag/eftermiddag/kväll/natt) beteendevariant per
  enhet, precis som helg/borta — praktiskt för beteende kopplat till något
  specifikt för det rummet (t.ex. en viss persons närvaro) snarare än hela
  husets helg-/borta-tillstånd.
- **Transitionstider** — ett globalt standardvärde per period, kan
  åsidosättas per enhet/period.
- **Fysiska knappar** — bind valfri entitet (t.ex. en Zigbee-knapp som visas
  som en `event`- eller `sensor`-entitet) till en åtgärd: växla rummet,
  stäng av det, kör det schemalagda beteendet nu, eller tvinga fram en
  specifik period oavsett vad klockan är.
- **Rörelse- och tröskelvärdestriggers per rum** — kombinera flera villkor
  med ELLER-logik: rörelsesensorer och/eller numeriska tröskelvärdessensorer
  (t.ex. "luftfuktighet över 65%"). Rummet räknas som "aktivt" så fort något
  villkor är sant, kör sitt schemalagda beteende direkt, och varje
  rörelseaktiverad enhet (vald per enhet, med sin egen fördröjning som
  åsidosätter rummets standard) stängs av igen när inget längre är sant —
  valfritt genom att dimra till en låg ljusstyrka först som en varning
  (rörelse under det fönstret återställer full ljusstyrka istället för att
  stänga av). Ett fysiskt knapptryck låser den enheten ute från
  rörelsekontroll fram till nästa nya rörelsecykel, så den inte omedelbart
  åsidosätts.
- **Kortgränssnitt** — hantera *allt* (rum, enheter, knappar, rörelse och
  alla tid-på-dygnet-/vardag-helg-/hemma-borta-inställningar ovan) från ett
  flikat eget kort, antingen inbäddat i en instrumentpanel eller som sin
  egen automatiskt registrerade sidopanelssida. Ingenting konfigureras via
  Home Assistants inbyggda "Lägg till integration"-guide — det steget lägger
  bara till RoomFlow med ett enda klick; allt annat finns i kortets
  Inställningar-flik och gäller direkt, ingen omstart behövs.
- **Live-status & manuellt test** — se varje enhets faktiska aktuella
  tillstånd, och trigga "testa nu" per rum eller för allt på en gång.
- **Diagnostik** — ladda ner en diagnostikfil (Inställningar → Enheter &
  tjänster → RoomFlow → Ladda ner diagnostik) för buggrapporter, utan att
  exponera dina specifika enhets-entity_id:n.
- **Exponeras som riktiga entiteter** — RoomFlow skapar tre vanliga
  sensor-entiteter (aktuell period, dagstyp, hemma-status) plus en
  binary_sensor per period (morgon/dag/eftermiddag/kväll/natt — "på" precis
  när den perioden är den just nu gällande, oavsett vilken/vilka källor som
  avgjorde det) som visas precis som vilken annan entitet som helst:
  användbara i dina egna automationer/instrumentpaneler. Deras enhetsnamn
  och area sätts från kortets Inställningar-flik, ingen anledning att leta
  reda på dem under Entiteter efteråt.
- **Feltolerant** — en enhet som fallerar loggar en varning istället för att
  blockera resten av rummet.

## Installation

### Via HACS (anpassat arkiv)

1. HACS → Integrationer → tre-punktsmenyn → **Anpassade arkiv**
2. Lägg till URL:en till det här arkivet, kategori **Integration**
3. Installera "RoomFlow", starta om Home Assistant

### Manuell

1. Kopiera `custom_components/roomflow` till `config/custom_components/`
   (kortet är inbakat i den, på `custom_components/roomflow/www/` — ingen
   separat kopiering behövs)
2. Starta om Home Assistant

### Konfigurering

1. **Inställningar → Enheter & tjänster → Lägg till integration → RoomFlow**
   — det finns inget att fylla i, bara bekräfta. Allt annat sker i kortet.

   RoomFlow serverar sitt eget kort och registrerar det automatiskt — ingen
   `config/www`-kopiering och ingen manuell post under **Inställningar →
   Instrumentpaneler → Resurser** behövs. Den lägger också till sig själv
   som en sida i sidopanelen. Du kan även lägga till kortet i en
   instrumentpanel manuellt:
   ```yaml
   type: custom:roomflow-card
   ```
2. Öppna RoomFlow-kortet (sidopanel eller instrumentpanel) → **⚙
   Inställningar**-fliken, och konfigurera:
   - **Tid-på-dygnet-perioder** — en ordnad lista (överst = högst
     prioritet), med de 5 standardvärdena som utgångspunkt
     (morgon/dag/eftermiddag/kväll/natt). Lägg till, ta bort, döp om eller
     ändra ordning (↑/↓) fritt. Varje period kan kryssa i valfri kombination
     av 5 källor — den är aktiv om NÅGON ikryssad just nu säger det
     (ELLER-logik):
     - Schema: en starttid.
     - Solens position: en soleventyp (gryning/soluppgång/solmiddag/
       solnedgång/skymning) + en valfri +/- minutoffset.
     - Luxsensor: en luxsensor + ett luxtröskelvärde.
     - Befintlig boolean: en `binary_sensor`/`input_boolean` som är "på"
       precis när den här perioden ska vara aktiv.
     - Befintlig sensor: en entitet + tillståndsvärdet som betyder att den
       här perioden är aktiv (fungerar med vilken tid-på-dygnet-sensor som
       helst, på vilket språk som helst).
     Den aktuella perioden är den som ligger högst upp i listan och som är
     aktiv just nu.
   - **Vardag/helg** och **Hemma/borta** — vardera antingen "används inte",
     en befintlig sensor, eller ett inbyggt alternativ (veckodagskryssruta;
     en eller flera `person.*`-entiteter), oberoende av allt annat.
   - **Enhet** — namn och area för RoomFlows egna sensorer.

   Varje ändring här gäller direkt — ingen omstart, inget att spara separat.

## Så fungerar det

Varje rum innehåller enheter (lampor/uttag). Varje enhet har ett beteende
per period, valt i den här ordningen när RoomFlow tillämpar det:

1. **Borta**-undantag, om aktiverat för den perioden och hemma-/borta-källan
   just nu rapporterar "borta"
2. **Helg**-undantag, om aktiverat för den perioden och vardag-/helg-källan
   just nu rapporterar ett helgvärde
3. **Standard**-beteende

RoomFlow tillämpas automatiskt igen närhelst en konfigurerad källa ändras:
sensorbaserade indata reagerar på tillståndsändringar, inbyggda reagerar på
sin egen klocka (en schemagräns, eller midnatt för veckodagsvalet) — och den
reagerar också direkt på knapptryckningar och rörelse-/tröskelvärdestriggers
du har konfigurerat.

## Bidra

Buggrapporter och pull requests är välkomna. Det här är ett relativt ungt
projekt — förvänta dig en del skavanker, särskilt kring mer avancerade
villkorskombinationer och fler enhetstyper (climate, media_player osv. är
naturliga nästa steg).

## Språk som stöds

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl)

## Licens

MIT — se [LICENSE](LICENSE).
