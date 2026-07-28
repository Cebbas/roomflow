<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

[🇬🇧 English](README.md) | [🇸🇪 Svenska](README.sv.md) | [🇳🇴 Norsk](README.no.md) | **🇫🇮 Suomi** | [🇩🇰 Dansk](README.da.md) | [🇩🇪 Deutsch](README.de.md) | [🇫🇷 Français](README.fr.md) | [🇳🇱 Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

Ohjaa valoja ja pistorasioita huoneittain vuorokaudenajan perusteella —
valinnaisilla viikonloppu-/poissa-poikkeuksilla, siirtymäajoilla, fyysisillä
painikesidonnoilla ja liike-/kynnysarvopohjaisella automaatiolla. Rakennettu
Home Assistantille omana integraationa sekä sen mukana tulevana
Lovelace-kortilla, joka toimii myös täytenä sivupaneelisivuna.

## Miksi

Useimmat vuorokaudenaikaan perustuvat valaistusratkaisut päätyvät kasaksi
automaatioita, joita on hankala säätää. RoomFlow antaa sinulle yhden
paikan, jossa voit huoneittain ja laitteittain määrittää: *mitä tämän
lampun/pistorasian pitäisi tehdä aamulla, päivällä, illalla, yöllä — ja
muuttuuko se viikonloppuisin tai kun kukaan ei ole kotona?* Sen päälle
tulevat vielä fyysiset painikkeet ja liike-/anturilaukaisimet.

## Ominaisuudet

- **Vuorokaudenaika-ajastus** — määritä toiminta (päällä/pois, kirkkaus,
  värilämpötila) laitteittain niin monelle jaksolle kuin haluat. Jaksot
  (aamu/päivä/iltapäivä/ilta/yö oletuksena) muodostavat täysin
  käyttäjän muokattavan, tärkeysjärjestyksessä olevan listan: lisää,
  poista, nimeä uudelleen ja järjestä uudelleen vapaasti kortista. Jokainen
  jakso voi yhdistää minkä tahansa 5 lähteestä kerralla, itsenäisesti
  valittuna: sisäänrakennetun **kelloaikataulun** (aloitusaika), **auringon
  aseman** (auringon tapahtuma - sarastus/auringonnousu/keskipäivä/
  auringonlasku/hämärä - plus siirtymä), **valaistusanturin** (luksiraja-
  arvo), **olemassa olevan totuusarvon** (osoita jo olemassa olevaan
  `binary_sensor`/`input_boolean`-entiteettiin — "päällä" tarkoittaa, että
  se on aktiivinen), tai **olemassa olevan anturin** (yhdistä jokin sen
  tila-arvoista siihen, jolloin tämä toimii minkä tahansa
  vuorokaudenaika-anturin kanssa millä tahansa kielellä). Jakso on
  aktiivinen, jos MIKÄ TAHANSA sen käytössä olevista lähteistä sanoo niin
  juuri nyt (TAI-logiikka). Se, mikä jakso on "nykyinen", ratkaistaan
  tärkeysjärjestyksen mukaan: ensimmäinen aktiivinen jakso listassa
  (ylimpänä = korkein prioriteetti) voittaa — voit siis vapaasti sekoittaa
  lähdetyyppejä (esim. valaistuspohjainen jakso aikataulupohjaisen yläpuolella,
  jotta pimeys voi ohittaa kellon).
- **Viikonloppu- ja poissa-poikkeukset** (valinnainen) — kummallekin
  valitset olemassa olevan anturin (tavallinen päällä/pois-`binary_sensor`
  toimii myös — kerro vain RoomFlow'lle, kumpi napaisuus "päällä" tarkoittaa
  arki-/viikonloppupäivälle), sisäänrakennetun vaihtoehdon (valitse mitkä
  viikonpäivät lasketaan viikonlopuksi; valitse yksi tai useampi
  `person.*`-entiteetti kotona/poissa-tilaa varten), tai jätä käyttämättä.
  Nämä kaksi valintaa, ja yllä oleva vuorokaudenaikalähde, ovat täysin
  toisistaan riippumattomia — sekoita vapaasti. Ohita oletustoiminta
  tietyille laitteille viikonloppuisin tai kun kukaan ei ole kotona.
  Tärkeysjärjestys: **poissa > viikonloppu > oletus**.
- **Huonekohtaiset omat ehdot** — talon laajuisten viikonloppu-/poissa-
  akselien lisäksi jokainen huone voi määrittää oman järjestetyn listansa
  ehtoja (nimi + entiteetti + tila, joka tarkoittaa, että se on aktiivinen),
  tarkistettuna tärkeysjärjestyksessä *poissa/viikonloppu/oletus*-arvojen
  yläpuolella. Jokainen ehto saa oman jaksokohtaisen
  (aamu/päivä/iltapäivä/ilta/yö) toimintavariantin laitteittain, aivan kuten
  viikonloppu/poissa — hyödyllinen toiminnalle, joka liittyy johonkin
  tietylle huoneelle ominaiseen (esim. tietyn henkilön läsnäolo)
  koko talon tilan sijaan.
- **Siirtymäajat** — yleinen oletusarvo jaksoa kohti, ohitettavissa
  laite-/jaksokohtaisesti.
- **Fyysiset painikkeet** — sido mikä tahansa entiteetti (esim. Zigbee-
  painike, joka näkyy `event`- tai `sensor`-entiteettinä) toimintoon:
  vaihda huoneen tila, sammuta se, aja ajastettu toiminta heti, tai pakota
  tietty jakso riippumatta todellisesta kellonajasta.
- **Liike- ja kynnysarvolaukaisimet huoneittain** — yhdistä useita ehtoja
  TAI-logiikalla: liikeantureita ja/tai numeerisia kynnysarvoantureita
  (esim. "ilmankosteus yli 65%"). Huone lasketaan "aktiiviseksi" heti, kun
  jokin ehto on tosi, ajaa ajastetun toimintansa heti, ja jokainen
  liikeohjattu laite (valittu laitteittain, omalla sammutusviiveellään,
  joka ohittaa huoneen oletuksen) sammuu taas, kun mikään ei enää ole tosi —
  valinnaisesti himmentäen ensin matalaan kirkkauteen varoitukseksi (liike
  tuona aikana palauttaa täyden kirkkauden sammuttamisen sijaan). Fyysinen
  painikkeen painallus lukitsee kyseisen laitteen pois liikeohjauksesta
  seuraavaan tuoreeseen liikejaksoon asti, jotta se ei ohitu heti.
- **Korttikäyttöliittymä** — hallitse *kaikkea* (huoneet, laitteet,
  painikkeet, liike ja kaikki yllä olevat vuorokaudenaika-/arki-viikonloppu-
  /koti-poissa-asetukset) välilehdellisestä omasta kortista, joko
  upotettuna kojelautaan tai omana automaattisesti rekisteröitynä
  sivupaneelisivuna. Mitään ei määritetä Home Assistantin sisäänrakennetun
  "Lisää integraatio" -ohjatun toiminnon kautta — se vaihe vain lisää
  RoomFlow'n yhdellä klikkauksella; kaikki muu on kortin
  Asetukset-välilehdellä ja tulee voimaan välittömästi, ei uudelleenkäynnistystä
  tarvita.
- **Reaaliaikainen tila ja manuaalinen testaus** — näe jokaisen laitteen
  todellinen nykyinen tila, ja laukaise "testaa nyt" huoneittain tai
  kaikelle kerralla.
- **Diagnostiikka** — lataa diagnostiikkatiedosto (Asetukset → Laitteet ja
  palvelut → RoomFlow → Lataa diagnostiikka) vikailmoituksia varten,
  paljastamatta tarkkoja laite-entity_id-tunnuksiasi.
- **Näkyy oikeina entiteetteinä** — RoomFlow luo kolme tavallista
  sensor-entiteettiä (nykyinen jakso, päivätyyppi, kotitila) sekä yhden
  binary_sensorin jaksoa kohti (aamu/päivä/iltapäivä/ilta/yö — "päällä"
  juuri silloin, kun se jakso on parhaillaan voimassa, riippumatta siitä,
  mikä lähde/lähteet sen ratkaisivat), jotka näkyvät kuten mikä tahansa muu
  entiteetti: käytettävissä omissa automaatioissasi/kojelaudoissasi. Niiden
  laitenimi ja alue asetetaan kortin Asetukset-välilehdeltä, ei tarvetta
  etsiä niitä jälkikäteen Entiteetit-osiosta.
- **Vikasietoinen** — laite, joka epäonnistuu, kirjaa varoituksen sen
  sijaan, että estäisi huoneen muun toiminnan.

## Asennus

### HACS:n kautta (mukautettu tietovarasto)

1. HACS → Integraatiot → kolmen pisteen valikko → **Mukautetut
   tietovarastot**
2. Lisää tämän tietovaraston URL-osoite, kategoria **Integration**
3. Asenna "RoomFlow", käynnistä Home Assistant uudelleen

### Manuaalisesti

1. Kopioi `custom_components/roomflow` kansioon
   `config/custom_components/` (kortti on sisällytetty siihen, polussa
   `custom_components/roomflow/www/` — erillistä kopiointia ei tarvita)
2. Käynnistä Home Assistant uudelleen

### Käyttöönotto

1. **Asetukset → Laitteet ja palvelut → Lisää integraatio → RoomFlow** —
   mitään ei tarvitse täyttää, vahvista vain. Kaikki muu tapahtuu kortissa.

   RoomFlow tarjoilee oman korttinsa ja rekisteröi sen automaattisesti —
   erillistä `config/www`-kopiointia tai manuaalista merkintää kohdassa
   **Asetukset → Kojelaudat → Resurssit** ei tarvita. Se lisää itsensä
   myös sivupaneelin sivuksi. Voit lisätä kortin myös manuaalisesti mihin
   tahansa kojelautaan:
   ```yaml
   type: custom:roomflow-card
   ```
2. Avaa RoomFlow-kortti (sivupaneeli tai kojelauta) → **⚙
   Asetukset**-välilehti, ja määritä:
   - **Vuorokaudenajan jaksot** — järjestetty lista (ylin = korkein
     prioriteetti), lähtökohtana 5 oletusjaksoa
     (aamu/päivä/iltapäivä/ilta/yö). Lisää, poista, nimeä uudelleen tai
     järjestä uudelleen (↑/↓) vapaasti. Jokainen jakso voi valita minkä
     tahansa yhdistelmän 5 lähteestä — se on aktiivinen, jos MIKÄ TAHANSA
     valituista sanoo niin juuri nyt (TAI-logiikka):
     - Aikataulu: aloitusaika.
     - Auringon asema: auringon tapahtuma (sarastus/auringonnousu/
       keskipäivä/auringonlasku/hämärä) + valinnainen +/- minuutin siirtymä.
     - Valaistusanturi: luksianturi + luksiraja-arvo.
     - Olemassa oleva totuusarvo: `binary_sensor`/`input_boolean`, joka on
       "päällä" juuri silloin, kun tämän jakson pitäisi olla aktiivinen.
     - Olemassa oleva anturi: entiteetti + tila-arvo, joka tarkoittaa, että
       tämä jakso on aktiivinen (toimii minkä tahansa
       vuorokaudenaika-anturin kanssa, millä tahansa kielellä).
     Nykyinen jakso on se, joka on korkeimmalla listassa ja on aktiivinen
     juuri nyt.
   - **Arki/viikonloppu** ja **Koti/poissa** — kumpikin joko "ei käytössä",
     olemassa oleva anturi, tai sisäänrakennettu vaihtoehto
     (viikonpäivävalinta; yksi tai useampi `person.*`-entiteetti),
     riippumatta kaikesta muusta.
   - **Laite** — RoomFlow'n omien anturien nimi ja alue.

   Jokainen muutos tulee voimaan välittömästi — ei uudelleenkäynnistystä,
   ei mitään erikseen tallennettavaa.

## Miten se toimii

Jokainen huone sisältää laitteita (valoja/pistorasioita). Jokaisella
laitteella on toiminta jaksoa kohti, valittuna tässä järjestyksessä, kun
RoomFlow soveltaa sitä:

1. **Poissa**-poikkeus, jos käytössä kyseiselle jaksolle ja koti-/poissa-
   lähde raportoi juuri nyt "poissa"
2. **Viikonloppu**-poikkeus, jos käytössä kyseiselle jaksolle ja
   arki-/viikonloppulähde raportoi juuri nyt viikonloppuarvon
3. **Oletus**-toiminta

RoomFlow soveltaa muutokset automaattisesti aina, kun määritetty lähde
muuttuu: anturipohjaiset syötteet reagoivat tilamuutoksiin,
sisäänrakennetut reagoivat omaan kelloonsa (aikataulun raja-arvo, tai
keskiyö viikonpäivävalinnalle) — ja se reagoi myös välittömästi
painikkeenpainalluksiin ja liike-/kynnysarvolaukaisimiin, jotka olet
määrittänyt.

## Osallistuminen

Vikailmoitukset ja pull requestit ovat tervetulleita. Tämä on suhteellisen
nuori projekti — odota joitakin kulmikkuuksia, erityisesti
edistyneempien ehtoyhdistelmien ja lisälaitetyyppien osalta (climate,
media_player jne. ovat luonnollisia seuraavia askelia).

## Tuetut kielet

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl)

## Lisenssi

MIT — katso [LICENSE](LICENSE).
