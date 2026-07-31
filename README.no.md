<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

[🇬🇧 English](README.md) | [🇸🇪 Svenska](README.sv.md) | **🇳🇴 Norsk** | [🇫🇮 Suomi](README.fi.md) | [🇩🇰 Dansk](README.da.md) | [🇩🇪 Deutsch](README.de.md) | [🇫🇷 Français](README.fr.md) | [🇳🇱 Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

> ⚠️ **Tidlig fase:** denne integrasjonen er under aktiv utvikling — forvent
> noen ru kanter og enkelte brytende endringer mellom versjoner.

Styr lys og stikkontakter per rom basert på tid på døgnet — med valgfrie
helg-/borte-unntak, overgangstider, fysiske knappbindinger og
bevegelses-/terskelbasert automasjon. Bygget for Home Assistant som en egen
integrasjon pluss et medfølgende Lovelace-kort som også fungerer som en
egen sidepanelside.

## Hvorfor

De fleste "tid på døgnet"-baserte lysoppsett ender som en haug med
automasjoner som er tungvinte å justere. RoomFlow gir deg ett sted å si, per
rom og per enhet: *hva skal denne lampen/stikkontakten gjøre om morgenen, på
dagtid, på kvelden, om natten — og endrer det seg i helger eller når ingen
er hjemme?* Deretter legger den fysiske knapper og bevegelses-/sensor-
triggere på toppen av det.

## Funksjoner

- **Tid-på-døgnet-planlegging** — definer atferd (på/av, lysstyrke,
  fargetemperatur) per enhet for så mange perioder du vil. Perioder
  (morgen/dag/ettermiddag/kveld/natt som standard) er en helt
  brukerredigerbar, prioritetsordnet liste: legg til, fjern, gi nytt navn
  og endre rekkefølge fritt fra kortet. Hver periode kan kombinere
  hvilken som helst av 5 kilder samtidig, uavhengig avkrysset: en innebygd
  **klokkeplan** (et starttidspunkt), **solens posisjon** (en solhendelse -
  demring/soloppgang/middag/solnedgang/skumring - pluss offset), en
  **lyssensor** (en luks-terskel), en **eksisterende boolsk** (pek på en
  `binary_sensor`/`input_boolean` du allerede har — "på" betyr at den er
  aktiv), eller en **eksisterende sensor** (map en av dens tilstandsverdier
  til den, så dette fungerer med hvilken som helst tid-på-døgnet-sensor på
  hvilket som helst språk). En periode er aktiv hvis NOEN av dens aktiverte
  kilder for øyeblikket sier det (ELLER-logikk). Hvilken periode som er
  "gjeldende" avgjøres av prioritet: den første aktive perioden i listen
  (øverst = høyest prioritet) vinner — så du kan fritt blande kildetyper
  (f.eks. en luks-basert periode over en tidsplan-basert for å la mørke
  overstyre klokken). Når hverdag/helg er konfigurert (se nedenfor), kan
  tidsplan- og sol-kildene hver for seg sette et annet tidspunkt/en annen
  solhendelse for helger — f.eks. at morgenen starter senere på lørdager og
  søndager — uten å trenge en helt egen periode for det.
- **Helg- og borte-unntak** (valgfritt) — for hver velger du en eksisterende
  sensor (en vanlig på/av-`binary_sensor` fungerer også — bare fortell
  RoomFlow hvilken polaritet "på" betyr for hverdag/helg), et innebygd
  alternativ (velg hvilke ukedager som teller som helg; velg én eller flere
  `person.*`-entiteter for hjemme/borte), eller la det stå ubrukt. Disse to
  valgene, og tid-på-døgnet-kilden over, er helt uavhengige — bland fritt.
  Overstyr standardatferden for spesifikke enheter i helger eller når ingen
  er hjemme. Prioritet: **borte > helg > standard**.
- **Rombaserte egendefinerte betingelser** — utover de husomfattende
  helg-/borte-aksene kan hvert rom definere sin egen ordnede liste med
  betingelser (et navn + en entitet + tilstanden som betyr at den er aktiv),
  sjekket i prioritert rekkefølge *over* borte/helg/standard. Hver betingelse
  får sin egen per-periode (morgen/dag/ettermiddag/kveld/natt) atferdsvariant
  per enhet, akkurat som helg/borte — nyttig for atferd knyttet til noe
  spesifikt for det rommet (f.eks. en bestemt persons tilstedeværelse)
  fremfor hele husets tilstand.
- **Overgangstider** — en global standardverdi per periode, kan overstyres
  per enhet/periode.
- **Fysiske knapper** — bind hvilken som helst entitet (f.eks. en
  Zigbee-knapp som vises som en `event`- eller `sensor`-entitet) til en
  handling: veksle rommet, slå det av, kjør den planlagte atferden nå, eller
  tving frem en bestemt periode uansett hva klokken er.
- **Bevegelses- og terskeltriggere per rom** — kombiner flere betingelser
  med ELLER-logikk: bevegelsessensorer og/eller numeriske terskelsensorer
  (f.eks. "luftfuktighet over 65%"). Rommet regnes som "aktivt" i det
  øyeblikket en betingelse er sann, kjører sin planlagte atferd umiddelbart,
  og hver bevegelsesaktiverte enhet (valgt per enhet, med sin egen
  avslåingsforsinkelse som overstyrer romstandarden) slås av igjen når
  ingenting lenger er sant — valgfritt ved å dimme til en lav lysstyrke
  først som en advarsel (bevegelse i det vinduet gjenoppretter full
  lysstyrke i stedet for å slå av). Et fysisk knappetrykk låser den enheten
  ute fra bevegelseskontroll til neste ferske bevegelsessyklus, slik at den
  ikke umiddelbart overstyres.
- **Kort-grensesnitt** — administrer *alt* (rom, enheter, knapper, bevegelse
  og alle tid-på-døgnet-/hverdag-helg-/hjemme-borte-innstillingene over) fra
  et faneinndelt eget kort, enten innebygd i et dashbord eller som sin egen
  automatisk registrerte sidepanelside. Ingenting konfigureres via Home
  Assistants innebygde "Legg til integrasjon"-veiviser — det steget legger
  bare til RoomFlow med ett klikk; alt annet ligger i kortets
  Innstillinger-fane og gjelder umiddelbart, ingen omstart nødvendig.
- **Live-status og manuell test** — se hver enhets faktiske gjeldende
  tilstand, og utløs "test nå" per rom eller for alt på én gang.
- **Diagnostikk** — last ned en diagnostikkfil (Innstillinger → Enheter og
  tjenester → RoomFlow → Last ned diagnostikk) for feilrapporter, uten å
  eksponere dine spesifikke enhets-entity_id-er.
- **Eksponert som ekte entiteter** — RoomFlow oppretter tre vanlige
  sensor-entiteter (gjeldende periode, dagstype, hjemme-status) pluss en
  binary_sensor per periode (morgen/dag/ettermiddag/kveld/natt — "på" nøyaktig
  når den perioden er den gjeldende, uansett hvilken(e) kilde(r) som avgjorde
  det) som vises akkurat som hvilken som helst annen entitet: brukbare i
  dine egne automasjoner/dashbord. Enhetsnavn og område settes fra kortets
  Innstillinger-fane, ingen grunn til å lete dem opp under Entiteter
  etterpå.
- **Robust** — en enhet som feiler logger en advarsel i stedet for å
  blokkere resten av rommet.

## Installasjon

### Via HACS (egendefinert repository)

1. HACS → Integrasjoner → tre-punktsmenyen → **Egendefinerte repositorier**
2. Legg til URL-en til dette repositoriet, kategori **Integration**
3. Installer "RoomFlow", start Home Assistant på nytt

### Manuelt

1. Kopier `custom_components/roomflow` til `config/custom_components/`
   (kortet er pakket inn i den, i `custom_components/roomflow/www/` — ingen
   separat kopiering nødvendig)
2. Start Home Assistant på nytt

### Oppsett

1. **Innstillinger → Enheter og tjenester → Legg til integrasjon →
   RoomFlow** — det er ingenting å fylle ut, bare bekreft. Alt annet skjer
   i kortet.

   RoomFlow serverer sitt eget kort og registrerer det automatisk — ingen
   `config/www`-kopiering og ingen manuell oppføring under **Innstillinger
   → Dashbord → Ressurser** nødvendig. Den legger også til seg selv som en
   side i sidepanelet. Du kan også legge til kortet i et dashbord manuelt:
   ```yaml
   type: custom:roomflow-card
   ```
2. Åpne RoomFlow-kortet (sidepanel eller dashbord) → **⚙
   Innstillinger**-fanen, og konfigurer:
   - **Tid-på-døgnet-perioder** — en ordnet liste (øverst = høyest
     prioritet), med de 5 standardverdiene som utgangspunkt
     (morgen/dag/ettermiddag/kveld/natt). Legg til, fjern, gi nytt navn
     eller endre rekkefølge (↑/↓) fritt. Hver periode kan krysse av for
     hvilken som helst kombinasjon av 5 kilder — den er aktiv hvis NOEN
     avkrysset for øyeblikket sier det (ELLER-logikk):
     - Tidsplan: et starttidspunkt.
     - Solens posisjon: en solhendelse (demring/soloppgang/middag/
       solnedgang/skumring) + en valgfri +/- minutt-offset.
     - Lyssensor: en lyssensor + en luks-terskel.
     - Eksisterende boolsk: en `binary_sensor`/`input_boolean` som er "på"
       nøyaktig når denne perioden skal være aktiv.
     - Eksisterende sensor: en entitet + tilstandsverdien som betyr at
       denne perioden er aktiv (fungerer med hvilken som helst
       tid-på-døgnet-sensor, på hvilket som helst språk).
     Gjeldende periode er den som ligger høyest i listen og som er aktiv
     akkurat nå. Når Hverdag/helg nedenfor er konfigurert, får Tidsplan og
     Solens posisjon hvert sitt valgfrie helgeunntak — et eget starttidspunkt
     eller en egen solhendelse bare for helgedager.
   - **Hverdag/helg** og **Hjemme/borte** — hver enten "ikke i bruk", en
     eksisterende sensor, eller et innebygd alternativ (ukedagsavkrysning;
     én eller flere `person.*`-entiteter), uavhengig av alt annet.
   - **Enhet** — navn og område for RoomFlows egne sensorer.

   Hver endring her gjelder umiddelbart — ingen omstart, ingenting å lagre
   separat.

## Slik fungerer det

Hvert rom inneholder enheter (lys/stikkontakter). Hver enhet har en atferd
per periode, valgt i denne rekkefølgen når RoomFlow bruker den:

1. **Borte**-unntak, hvis aktivert for den perioden og hjemme-/borte-kilden
   for øyeblikket rapporterer "borte"
2. **Helg**-unntak, hvis aktivert for den perioden og hverdag-/helg-kilden
   for øyeblikket rapporterer en helgeverdi
3. **Standard**-atferd

RoomFlow tar i bruk endringer automatisk når en konfigurert kilde endres:
sensorbaserte innganger reagerer på tilstandsendringer, innebygde reagerer
på sin egen klokke (en tidsplangrense, eller midnatt for ukedagsvalget) — og
den reagerer også umiddelbart på knappetrykk og bevegelses-/terskeltriggere
du har konfigurert.

## Bidra

Feilrapporter og pull requests er velkomne. Dette er et relativt ungt
prosjekt — forvent noen ru kanter, spesielt rundt mer avanserte
betingelseskombinasjoner og flere enhetstyper (climate, media_player osv.
er naturlige neste steg).

## Støttede språk

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl) —
denne READMEen, kortets eget grensesnitt og config flow følger alle de
samme 8 språkene. Kortet velger språk automatisk ut fra Home Assistants
språkinnstilling.

## Lisens

MIT — se [LICENSE](LICENSE).
