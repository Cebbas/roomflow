<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

[🇬🇧 English](README.md) | [🇸🇪 Svenska](README.sv.md) | [🇳🇴 Norsk](README.no.md) | [🇫🇮 Suomi](README.fi.md) | **🇩🇰 Dansk** | [🇩🇪 Deutsch](README.de.md) | [🇫🇷 Français](README.fr.md) | [🇳🇱 Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

Styr lys og stikkontakter per rum baseret på tid på dagen — med valgfrie
weekend-/væk-undtagelser, overgangstider, fysiske knapbindinger og
bevægelses-/tærskelbaseret automatisering. Bygget til Home Assistant som en
brugerdefineret integration plus et medfølgende Lovelace-kort, der også
fungerer som en fuld sidepanelside.

## Hvorfor

De fleste "tid på dagen"-opsætninger til lys ender som en bunke
automatiseringer, der er besværlige at justere. RoomFlow giver dig ét sted
at sige, per rum og per enhed: *hvad skal denne lampe/stikkontakt gøre om
morgenen, i løbet af dagen, om aftenen, om natten — og ændrer det sig i
weekender, eller når ingen er hjemme?* Derefter lægger den fysiske knapper
og bevægelses-/sensortriggere oven i det.

## Funktioner

- **Tid-på-dagen-planlægning** — definer adfærd (til/fra, lysstyrke,
  farvetemperatur) per enhed for lige så mange perioder, du vil. Perioder
  (morgen/dag/eftermiddag/aften/nat som standard) er en fuldt
  brugerredigerbar, prioritetsordnet liste: tilføj, fjern, omdøb og
  omorganiser dem frit fra kortet. Hver periode kan kombinere en hvilken som
  helst af 5 kilder på én gang, uafhængigt afkrydset: en indbygget
  **urplan** (et starttidspunkt), **solens position** (en solbegivenhed -
  daggry/solopgang/middag/solnedgang/skumring - plus offset), en
  **lyssensor** (en lux-tærskel), en **eksisterende boolean** (peg på en
  `binary_sensor`/`input_boolean`, du allerede har — "til" betyder, at den
  er aktiv), eller en **eksisterende sensor** (map en af dens
  tilstandsværdier til den, så dette fungerer med enhver
  tid-på-dagen-sensor på ethvert sprog). En periode er aktiv, hvis NOGEN af
  dens aktiverede kilder lige nu siger det (ELLER-logik). Hvilken periode
  der er "aktuel" afgøres af prioritet: den første aktive periode i listen
  (øverst = højeste prioritet) vinder — så du frit kan blande kildetyper
  (f.eks. en lux-baseret periode over en tidsplan-baseret, så mørke kan
  tilsidesætte uret).
- **Weekend- og væk-undtagelser** (valgfrit) — for hver vælger du en
  eksisterende sensor (en almindelig til/fra-`binary_sensor` virker også —
  bare fortæl RoomFlow, hvilken polaritet "til" betyder for
  hverdag/weekend), en indbygget mulighed (vælg hvilke ugedage der tæller
  som weekend; vælg en eller flere `person.*`-entiteter til hjemme/væk),
  eller lad den stå ubrugt. Disse to valg, og tid-på-dagen-kilden ovenfor,
  er helt uafhængige — bland frit. Tilsidesæt standardadfærden for
  specifikke enheder i weekender eller når ingen er hjemme. Prioritet:
  **væk > weekend > standard**.
- **Rumspecifikke brugerdefinerede betingelser** — ud over de husomfattende
  weekend-/væk-akser kan hvert rum definere sin egen ordnede liste af
  betingelser (et navn + en entitet + tilstanden der betyder, at den er
  aktiv), tjekket i prioriteret rækkefølge *over* væk/weekend/standard.
  Hver betingelse får sin egen per-periode
  (morgen/dag/eftermiddag/aften/nat) adfærdsvariant per enhed, ligesom
  weekend/væk — nyttigt til adfærd knyttet til noget specifikt for det rum
  (f.eks. en bestemt persons tilstedeværelse) frem for hele husets
  tilstand.
- **Overgangstider** — en global standardværdi per periode, kan
  tilsidesættes per enhed/periode.
- **Fysiske knapper** — bind en hvilken som helst entitet (f.eks. en
  Zigbee-knap der vises som en `event`- eller `sensor`-entitet) til en
  handling: skift rummet, sluk det, kør den planlagte adfærd nu, eller
  gennemtving en bestemt periode uanset det faktiske klokkeslæt.
- **Bevægelses- og tærskeltriggere per rum** — kombiner flere betingelser
  med ELLER-logik: bevægelsessensorer og/eller numeriske tærskelsensorer
  (f.eks. "luftfugtighed over 65%"). Rummet betragtes som "aktivt", i det
  øjeblik en betingelse er sand, kører sin planlagte adfærd med det samme,
  og hver bevægelsesaktiveret enhed (valgt per enhed, med sin egen
  slukforsinkelse der tilsidesætter rummets standard) slukkes igen, når
  intet længere er sandt — valgfrit ved at dæmpe til en lav lysstyrke
  først som en advarsel (bevægelse i det vindue genopretter fuld lysstyrke
  i stedet for at slukke). Et fysisk knaptryk låser den enhed ude fra
  bevægelseskontrol indtil næste friske bevægelsescyklus, så den ikke
  straks bliver tilsidesat.
- **Kort-brugerflade** — administrer *alt* (rum, enheder, knapper,
  bevægelse og alle tid-på-dagen-/hverdag-weekend-/hjemme-væk-indstillinger
  ovenfor) fra et faneopdelt brugerdefineret kort, enten indlejret i et
  dashboard eller som sin egen automatisk registrerede sidepanelside.
  Intet konfigureres via Home Assistants indbyggede "Tilføj
  integration"-guide — det trin tilføjer bare RoomFlow med et enkelt klik;
  alt andet ligger i kortets Indstillinger-fane og gælder med det samme,
  ingen genstart nødvendig.
- **Live-status og manuel test** — se hver enheds faktiske aktuelle
  tilstand, og udløs "test nu" per rum eller for det hele på én gang.
- **Diagnostik** — download en diagnostikfil (Indstillinger → Enheder &
  tjenester → RoomFlow → Download diagnostik) til fejlrapporter, uden at
  eksponere dine specifikke enheds-entity_id'er.
- **Eksponeret som rigtige entiteter** — RoomFlow opretter tre almindelige
  sensor-entiteter (aktuel periode, dagstype, hjemme-status) plus én
  binary_sensor per periode (morgen/dag/eftermiddag/aften/nat — "til"
  præcis når den periode er den aktuelt gældende, uanset hvilken(e)
  kilde(r) der afgjorde det), som vises ligesom enhver anden entitet:
  brugbare i dine egne automatiseringer/dashboards. Deres enhedsnavn og
  område sættes fra kortets Indstillinger-fane, ingen grund til at lede
  dem op under Entiteter bagefter.
- **Robust** — en fejlende enhed logger en advarsel i stedet for at
  blokere resten af rummet.

## Installation

### Via HACS (brugerdefineret repository)

1. HACS → Integrationer → tre-prikkers-menuen → **Brugerdefinerede
   repositories**
2. Tilføj URL'en til dette repository, kategori **Integration**
3. Installer "RoomFlow", genstart Home Assistant

### Manuel

1. Kopier `custom_components/roomflow` til `config/custom_components/`
   (kortet er indbygget i den, i `custom_components/roomflow/www/` — ingen
   separat kopiering nødvendig)
2. Genstart Home Assistant

### Opsætning

1. **Indstillinger → Enheder & tjenester → Tilføj integration → RoomFlow**
   — der er intet at udfylde, bare bekræft. Alt andet sker i kortet.

   RoomFlow serverer sit eget kort og registrerer det automatisk — ingen
   `config/www`-kopiering og ingen manuel post under **Indstillinger →
   Dashboards → Ressourcer** nødvendig. Den tilføjer sig også selv som en
   side i sidepanelet. Du kan også tilføje kortet til et dashboard manuelt:
   ```yaml
   type: custom:roomflow-card
   ```
2. Åbn RoomFlow-kortet (sidepanel eller dashboard) → **⚙
   Indstillinger**-fanen, og konfigurer:
   - **Tid-på-dagen-perioder** — en ordnet liste (øverst = højeste
     prioritet), med de 5 standardværdier som udgangspunkt
     (morgen/dag/eftermiddag/aften/nat). Tilføj, fjern, omdøb eller
     omorganiser (↑/↓) frit. Hver periode kan afkrydse en hvilken som
     helst kombination af 5 kilder — den er aktiv, hvis NOGEN afkrydset
     lige nu siger det (ELLER-logik):
     - Tidsplan: et starttidspunkt.
     - Solens position: en solbegivenhed (daggry/solopgang/middag/
       solnedgang/skumring) + en valgfri +/- minutoffset.
     - Lyssensor: en lyssensor + en lux-tærskel.
     - Eksisterende boolean: en `binary_sensor`/`input_boolean`, der er
       "til" præcis når denne periode skal være aktiv.
     - Eksisterende sensor: en entitet + tilstandsværdien, der betyder, at
       denne periode er aktiv (fungerer med enhver tid-på-dagen-sensor, på
       ethvert sprog).
     Den aktuelle periode er den, der ligger højest i listen, og som er
     aktiv lige nu.
   - **Hverdag/weekend** og **Hjemme/væk** — hver enten "ikke brugt", en
     eksisterende sensor, eller en indbygget mulighed
     (ugedagsafkrydsning; en eller flere `person.*`-entiteter), uafhængigt
     af alt andet.
   - **Enhed** — navn og område for RoomFlows egne sensorer.

   Hver ændring her gælder med det samme — ingen genstart, intet at gemme
   separat.

## Sådan fungerer det

Hvert rum indeholder enheder (lys/stikkontakter). Hver enhed har en adfærd
per periode, valgt i denne rækkefølge, når RoomFlow anvender den:

1. **Væk**-undtagelse, hvis aktiveret for den periode, og hjemme-/væk-kilden
   lige nu rapporterer "væk"
2. **Weekend**-undtagelse, hvis aktiveret for den periode, og
   hverdag-/weekend-kilden lige nu rapporterer en weekendværdi
3. **Standard**-adfærd

RoomFlow anvender automatisk ændringer igen, når en konfigureret kilde
ændres: sensorbaserede input reagerer på tilstandsændringer, indbyggede
reagerer på deres eget ur (en tidsplangrænse, eller midnat for
ugedagsvalget) — og den reagerer også med det samme på knaptryk og
bevægelses-/tærskeltriggere, du har konfigureret.

## Bidrag

Fejlrapporter og pull requests er velkomne. Dette er et relativt ungt
projekt — forvent nogle ru kanter, især omkring mere avancerede
betingelseskombinationer og flere enhedstyper (climate, media_player osv.
er naturlige næste skridt).

## Understøttede sprog

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl)

## Licens

MIT — se [LICENSE](LICENSE).
