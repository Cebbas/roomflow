<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

🌍 [English](README.md) | [Svenska](README.sv.md) | [Norsk](README.no.md) | **Suomi** | [Dansk](README.da.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

> ⚠️ **Varhainen vaihe:** tämä integraatio on aktiivisen kehityksen alla —
> odota joitakin kulmikkuuksia ja satunnaisia rikkovia muutoksia julkaisujen
> välillä. Edellyttää Home Assistant -versiota 2024.7.0 tai uudempaa.

Ohjaa valoja ja pistorasioita huoneittain vuorokaudenajan perusteella —
viikonloppu-/poissa-poikkeuksilla, fyysisillä painikkeilla (mukaan lukien
raa'at Zigbee-/Shelly-tyyliset tapahtumat ilman taustalla olevaa
entiteettiä), liike-/kynnysarvolaukaisimilla sekä huonekohtaisilla omilla
ehdoilla. Kaikki määritetään yhdestä siihen kuuluvasta Lovelace-kortista;
itse integraatioon ei tarvitse täyttää mitään.

## Miksi

Useimmat "vuorokaudenajan mukaiset" valaistusratkaisut päätyvät kasaksi
erillisiä automaatioita, joita on tuskallista säätää — yksi aikataulua
varten, yksi per liiketunnistin, yksi per painike, kaikki riitelemässä
keskenään heti, kun teet käsin muutoksen. RoomFlow antaa sinulle yhden
paikan, jossa voit huoneittain ja laitteittain määrittää: *mitä tämän
valon/pistorasian pitäisi tehdä aamulla, päivällä, illalla, yöllä — ja
muuttuuko se viikonloppuisin, kun kukaan ei ole kotona, tai kun jokin
tälle huoneelle määritetty oma ehto on tosi?* Sen päälle kerrostuvat
vielä fyysiset painikkeet sekä liike-/anturilaukaisimet, jolloin kaikki
pysyy synkronissa saman aikataulun kanssa sen sijaan, että ne ohittaisivat
toisensa huomaamatta.

## Yhdellä silmäyksellä

- **Niin monta itsenäistä aikataulua kuin haluat** — useimmat huoneet
  jakavat yhden, mutta esimerkiksi ulkovalaistus voi noudattaa omaa
  yksinkertaista hämärästä sarastukseen -aikatauluaan sotkematta kaikkien
  muiden jaksolistaa.
- **Ehtolistasta rakennetut jaksot** — kellonaika, auringon asema,
  numeerisen anturin raja-arvo, anturin tila, arki/viikonloppu,
  koti/poissa — yhdisteltynä JA/TAI-logiikalla, tärkeysjärjestyksessä.
- **Viikonloppu-, poissa- ja huonekohtaiset omat ehtopoikkeukset**, joilla
  kullakin on oma laitekohtainen toimintansa, tarkistettuna kiinteässä
  tärkeysjärjestyksessä.
- **Koko laitteelle yhteinen oletuspoissaolokäytös**, jotta
  poissaolokäytöstä ei tarvitse määrittää jakso kerrallaan, ellei jokin
  yksittäinen jakso todella tarvitse poikkeavaa käytöstä.
- **Jaksokohtainen ohjaustapa** — aikataulupohjainen,
  liiketunnistinpohjainen tai painike-/manuaalitila, valittavissa
  itsenäisesti jokaiselle laitteelle ja jaksolle.
- **Liiketunnistimet jaettuna, uudelleenkäytettävänä kirjastona** —
  rakenna triggeri kerran ja osoita niin moni laite kuin haluat siihen,
  missä tahansa huoneessa.
- **Painikkeetkin jaettuna, uudelleenkäytettävänä kirjastona** — mukaan
  lukien raa'at Zigbee-/Shelly-tyyliset laitetapahtumat ilman
  minkäänlaista taustaentiteettiä, painallustyypin tunnistus
  (yksittäinen/kaksois-/pitkä) sekä toimivan painikeasetuksen jakaminen
  kopioimalla ja liittämällä.
- **Käsin tehty muutos pysyy voimassa** — jonkin päälle/pois kytkeminen
  käsin ei peruunnu huomaamatta minuutin päästä, vaan sitä kunnioitetaan,
  kunnes aikataulun oma tavoite todella muuttuu.
- **Reaaliaikainen tila, tapahtumalokit ja painikekohtainen
  tapahtumaloki** vastaamaan kysymykseen "tekikö tämä todella sen, mitä
  odotin" ilman arvailua.
- **Korttikäyttöliittymä kaikelle** — mitään ei määritetä Home
  Assistantin sisäänrakennetun integraation asennuksen kautta, lukuun
  ottamatta yhtä vahvistusklikkausta.

## Asennus

### HACS:n kautta (mukautettu tietovarasto)

1. HACS → Integrations → the three-dot menu → **Custom repositories**
2. Lisää tämän tietovaraston URL-osoite, kategoria **Integration**
3. Asenna "RoomFlow", käynnistä Home Assistant uudelleen

### Manuaalisesti

1. Kopioi `custom_components/roomflow` kansioon `config/custom_components/`
   (kortti on sisällytetty siihen, polussa `custom_components/roomflow/www/`
   — erillistä kopiointia ei tarvita)
2. Käynnistä Home Assistant uudelleen

### Ensimmäinen käyttöönotto

**Settings → Devices & services → Add integration → RoomFlow** — mitään ei
tarvitse täyttää, vahvista vain. RoomFlow tarjoilee oman korttinsa ja
rekisteröi sen automaattisesti: ei `config/www`-kopiointia, ei manuaalista
**Settings → Dashboards → Resources** -merkintää, ja se lisää itsensä
sivupaneeliin omana sivunaan. Voit toki lisätä kortin myös manuaalisesti
mihin tahansa kojelautaan:

```yaml
type: custom:roomflow-card
```

Kaikki tästä eteenpäin tapahtuu kortin sisällä. Jokainen muutos
autotallentuu (noin puoli sekuntia sen jälkeen, kun lopetat kirjoittamisen
tai klikkaamisen) ja tulee voimaan välittömästi — ei tarvetta ladata
mitään uudelleen.

## Opas

### Huoneet ja laitteet

**Huone** sisältää yhden tai useamman **laitteen** (minkä tahansa
`light.*`- tai `switch.*`-entiteetin — sama entiteetti voidaan lisätä
useampaan kuin yhteen huoneeseen, jos haluat). Lisää huone **+ Huone**
-välilehdeltä, joko linkitettynä olemassa olevaan Home Assistantin
alueeseen (sen valot/kytkimet lisätään automaattisesti) tai pelkällä
nimellä. Lisää huoneeseen lisää laitteita milloin tahansa kyseisen
huoneen välilehden alareunassa olevasta **+ Lisää laite** -valitsimesta.

Jokainen laite on avattavissa/suljettavissa; avaa se nähdäksesi sen
jaksovälilehdet (yksi per jakso siinä aikataulussa, jota huone noudattaa)
ja niiden alapuolella sen ohjaustavan, oletuspoissaolokäytöksen ja omat
sidotut painikkeensa.

### Aikataulut ja jaksot

**Aikataulu** on nimetty, tärkeysjärjestyksessä oleva lista **jaksoja**
(oletuksena Aamu, Päivä, Iltapäivä, Ilta, Yö, mutta voit nimetä
uudelleen, järjestää uudelleen, lisätä tai poistaa vapaasti). Aikatauluja
voi olla useampi kuin yksi — useimmat kodit tarvitsevat vain yhden
jaetun sisätilojen aikataulun, mutta esimerkiksi ulkovalaistus haluaa
yleensä oman yksinkertaisen aikaikkunansa sen sijaan, että se
pakotettaisiin samaan aamu/päivä/iltapäivä/ilta/yö-muottiin. Hallitse
aikatauluja kohdasta **⚙ Settings → Schedules**; valitse, mitä
aikataulua huone noudattaa, kun lisäät huoneen (ohitetaan, jos sinulla
on vain yksi aikataulu).

Jokainen jakso rakennetaan **ehtolistasta**: valitse ehtotyyppi
valikosta lisätäksesi sen, ja yhdistele vapaasti niin monta kuin haluat
käyttäen kahta logiikkatasoa — **JA** ryhmän sisällä (kaikkien on
oltava tosia), **TAI** ryhmien välillä (riittää, että yksikin ryhmä on
kokonaan tosi). Käytettävissä olevat ehtotyypit:

- **Kellonaika** — ennen/jälkeen kiinteän kellonajan.
- **Auringon asema** — ennen/jälkeen auringon tapahtuman (sarastus,
  auringonnousu, keskipäivä, auringonlasku, hämärä), valinnaisella +/-
  minuutin siirtymällä sekä valinnaisilla varhaisin/myöhäisin-rajoilla,
  jotta auringon tapahtuma ei koskaan ratkea ennen tai jälkeen kiinteän
  kellonajan minään päivänä (hyödyllinen pitämään "ilta" järkevänä sekä
  keskikesällä että keskitalvella).
- **Numeerinen anturi** — yli/alle/yhtä suuri kuin -kynnysarvo
  verrattuna minkä tahansa anturin tilaan (näin ilmaiset esimerkiksi
  "ulkona on pimeää" luksianturilla, tai minkä tahansa muun numeerisen
  ehdon).
- **Anturin tila** — on/ei ole tietty tila-arvo, verrattuna mihin
  tahansa entiteettiin — toimii `binary_sensor`-, `input_boolean`- tai
  minkä tahansa muun entiteetin kanssa millä tahansa kielellä, koska
  kirjoitat tarkan tila-arvon itse.
- **Arki/viikonloppu** ja **Koti/poissa** — käytä uudelleen sitä, mitä
  olet määrittänyt kohdissa Arki/viikonloppu ja Koti/poissa (katso
  alla), suoraan jakson omissa ehdoissa, jos haluat esimerkiksi jakson
  pätevän vain arkisin.

Kun olet rakentanut kunkin jakson ehtoryhmät, järjestyksellä on väliä:
**listan ensimmäinen jakso, jonka ehdot ovat juuri nyt tosia, voittaa**
— sijoita siis tarkemmat/ohittavat jaksot yleisempien yläpuolelle
(esimerkiksi manuaalinen "hyvää yötä" -ohitus tavallisen ilta/yö-jaon
yläpuolelle).

Jokaisella aikataululla on myös oma **oletussiirtymäaika** jaksoa kohti
(kuinka kauan valon himmentyminen uuteen arvoon kestää), joka voidaan
ohittaa laite-/jaksokohtaisesti, jos jonkin valon pitäisi siirtyä eri
tavalla kuin muiden.

### Miten laite valitsee toimintansa

Jokaiselle jaksolle laitteella voi olla enintään neljä
toimintavarianttia — kullakin oma päällä/pois-tila, kirkkaus ja
värilämpötila — jotka tarkistetaan tässä järjestyksessä, ylin voittaa:

1. Mikä tahansa tämän **huoneen omista ehdoista**, joka on juuri nyt
   tosi (katso alla), kyseisen huoneen tärkeysjärjestyksessä.
2. Tämän **jakson oma "Poissa"-ohitus**, jos olet ottanut sen käyttöön
   juuri tälle jaksolle.
3. **Koko laitteelle yhteinen oletuspoissaolokäytös** (katso seuraava
   kappale) — käytetään vain silloin, kun tällä jaksolla ei ole omaa
   Poissa-ohitusta käytössä.
4. Tämän **jakson oma "Viikonloppu"-ohitus**, jos olet ottanut sen
   käyttöön.
5. Tämän jakson tavallinen **Oletus**-toiminta.

**Koko laitteelle yhteinen oletuspoissaolokäytös** sijaitsee laitteen
jaksovälilehtien vieressä (ei minkään yksittäisen välilehden sisällä) ja
määrittää yhden päällä/pois-/kirkkaus-/väriarvon, joka pätee poissa
ollessasi *jokaisen* jakson yli kerralla — jotta sinun ei tarvitse
määrittää "pois päältä poissa ollessa" viittä kertaa erikseen, ellei
jokin tietty jakso todella tarvitse erilaista poissaolokäytöstä, jolloin
kyseisen jakson oma Poissa-ohitus (kohta 2 yllä) yksinkertaisesti
ohittaa sen tärkeysjärjestyksessä.

### Ohjaustapa: aikataulu, liiketunnistin vai painike

Jokaiselle laitteelle, jokaiselle jaksolle valitset **miten sitä
ohjataan** — tämä ei muuta itse toimintavarvoja, vaan ainoastaan sitä,
saako aikataulu (tai liike) soveltaa niitä automaattisesti:

- **Aikataulu** — tavallinen tapaus: RoomFlow pitää tämän laitteen
  synkronissa sen kanssa, mikä toimintavariantti kulloinkin pätee,
  automaattisesti aina, kun jotain olennaista muuttuu.
- **Liiketunnistin** — tavallinen aikataulu ei koske tätä laitetta,
  vaan sitä ohjaa liiketunnistinmääritys, jonka valitset juuri siinä
  (katso alla), erillisillä kytkimillä sille, pitäisikö laitteen mennä
  **päälle**, kun liike alkaa, ja/tai **pois**, kun liike loppuu —
  jolloin laite voi reagoida vain toiseen puoleen, jos niin haluat.
- **Painike/manuaalitila** — tavallista jaksokohtaista toimintaa ei
  koskaan sovelleta automaattisesti; tämä laite muuttuu vain, kun
  painat sidottua fyysistä painiketta (tai painat erikseen "Testaa
  nyt"). Poissa-/viikonloppu-/omat ehdot -ohitukset pätevät silti
  automaattisesti, jos olet ottanut ne käyttöön tälle jaksolle — vain
  tavallinen Oletus-arvo jää manuaalisen ohjauksen varaan. Tämä on
  luonnollinen valinta laitteelle, jota haluat aina ohjata käsin, mutta
  jonka *syttymiskirkkauden* haluat silti riippuvan vuorokaudenajasta —
  katso [Painikkeet](#painikkeet) alla: painikkeenpainallus ratkaisee
  todellisen nykyisen toiminnan, ei sokeaa päälle/pois-kytkentää.

### Liiketunnistimet

Liiketunnistimet elävät omalla **Liiketunnistimet**-välilehdellään
jaettuna, uudelleenkäytettävänä kirjastona, riippumattomana mistään
yksittäisestä huoneesta. Lisää määritys, anna sille nimi, ja lisää
siihen yksi tai useampi triggeri:

- **Liikeanturi** — `binary_sensor` (tai vastaava), joka on "päällä",
  kun liikettä havaitaan.
- **Kynnysarvo** — mikä tahansa numeerinen anturi asettamasi arvon
  yläpuolella (esim. ilmankosteus, jotta kylpyhuoneen tuuletin/valo voi
  reagoida suihkuun pelkän PIR-liiketunnistuksen sijaan).

Määritys on "aktiivinen" aina, kun *mikä tahansa* sen triggereistä on
tosi. Aseta sen sammutusviive (kuinka kauan viimeisen triggerin
poistuttua kestää ennen sammutusta) ja valinnaisesti **himmennys
varoituksena** -vaihe — himmennä ensin valittuun kirkkauteen, odota
vielä muutama minuutti, ja vasta sitten sammuta kokonaan; liikkeen
palaaminen kummalla tahansa odotusjaksolla palauttaa laitteen
normaaliin nykyiseen toimintaansa sammuttamisen sijaan.

Aseta sitten laite- ja jaksokohtaisesti ohjaustavaksi **Liiketunnistin**
ja valitse, mihin määritykseen sen tulisi reagoida. Samaa määritystä
voi käyttää niin moni laite kuin haluat, niin monessa huoneessa kuin
haluat — rakenna triggeri kerran (esim. "Kylpyhuoneen PIR +
ilmankosteus") ja osoita jokainen valo, jonka pitäisi reagoida siihen,
tuohon yhteen määritykseen, sen sijaan että määrittelisit samat anturit
uudelleen ja uudelleen.

### Painikkeet

Liiketunnistimien tapaan painikkeetkin elävät omalla **Painikkeet**
-välilehdellään jaettuna, uudelleenkäytettävien **triggereiden**
kirjastona, erillään siitä, *mitä* ne tekevät — liität triggerin
toimintoon siitä huoneesta tai laitteesta, jota sen pitäisi ohjata, ja
samaa triggeriä voi käyttää useammassa paikassa yhtä aikaa (esim. yksi
fyysinen kanava sekä himmentää tiettyä valoa *että* vaihtaa koko
huoneen tilaa, kahdesta erillisestä liitoksesta samaan triggeriin).

Triggeriä lisätessäsi valitset kahden tyypin väliltä:

- **Entiteetti** — yleisin tapaus: osoita se mihin tahansa
  entiteettiin, joka vaihtaa tilaa painalluksesta (Zigbee2MQTT/ZHA:n
  `event.*`-entiteetti, tavallinen `binary_sensor`, tai johdettu
  "painallustila"-anturi, jos integraatiosi tarjoaa sellaisen).
- **Laitetapahtuma** — laitteistolle, joka lähettää raa'an Home
  Assistant -tapahtuman **ilman minkäänlaista taustaentiteettiä**
  (Shelly gen1 -releet/tulot ovat sisäänrakennettu esimerkki: ne
  lähettävät `shelly.click`-tapahtuman, eivät mitään entiteetin
  tilamuutosta). Valitse laiteprofiili (Shelly gen1 on
  sisäänrakennettu) ja täytä kentät, jotka yksilöivät juuri sinun
  fyysisen laitteesi/kanavasi — katso
  [BUTTON_PROFILES.md](BUTTON_PROFILES.md), josta selviää tarkalleen,
  miten löydät nuo arvot omalle laitteistollesi, ja miten voit lisätä
  profiilin laitteistolle, jota ei vielä ole sisäänrakennettuna.

Kumpikin tyyppi voidaan valinnaisesti rajata **painallustyyppiin** —
mikä tahansa painallus (oletus), yksittäinen, kaksois- tai pitkä
painallus — jolloin yksi fyysinen painike voi ohjata useampaa eri
triggeriä, joista kukin tekee eri asian riippuen siitä, miten sitä
painetaan, jos laitteistosi raportoi tämän eron.

Saitko triggerin toimimaan ja haluat käyttää samaa fyysistä asetusta
uudelleen muualla (toisessa asennuksessa, tai vain dokumentoidaksesi
sen itsellesi)? Käytä triggerin **kopiointi**-kuvaketta kopioidaksesi
sen pienenä tekstipätkänä, ja **liitä triggeri** -toimintoa luodaksesi
sen uudelleen tuosta pätkästä.

**Triggerin liittäminen**:

- **Laitteeseen** (kyseisen laitteen omassa kortissa, sen
  jaksovälilehtien alapuolella) — Vaihda, Sammuta, tai (valoille) säädä
  kirkkautta ylös-/alaspäin kiinteällä askeleella joka painalluksella.
  Vaihto-/päälle-painallus ratkaisee laitteen todellisen, juuri nyt
  voimassa olevan toiminnan (oikean kirkkauden/värin vuorokaudenajalle,
  mukaan lukien poissa/viikonloppu, jos ne ovat olennaisia) — ei
  sokeaa päälle-kytkentää, joten pelkästään painikkeella ohjattu
  laitekin himmenee oikein päivän mittaan.
- **Huoneeseen** (kyseisen huoneen omalla välilehdellä, "Huoneen
  painikkeet") — Vaihda päälle/pois tai sammuta kaikki huoneen
  laitteet yhdessä, aja huoneen ajastettu toiminta nyt, tai pakota
  huone tiettyyn jaksoon riippumatta todellisesta kellonajasta (kätevä
  läpikävelyyn/esittelyyn, tai "juhlatila"-ohitukseen).

Jos fyysinen painike ei näytä tekevän mitään, tarkista
**Painikeaktiivisuus**-loki Painikkeet-välilehden alareunasta ennen
kuin oletat sen olevan väärin määritetty — katso
[Kun painike "ei tee mitään"](#kun-painike-ei-tee-mitään) alla.

### Huonekohtaiset omat ehdot

Talon laajuisten Viikonloppu-/Poissa-ohitusten lisäksi jokainen huone
voi määrittää oman järjestetyn ehtolistansa kyseisen huoneen omalta
välilehdeltä — nimen, entiteetin ja tilan, joka tarkoittaa, että ehto
on aktiivinen. Nämä tarkistetaan *ensin*, Poissa-/Viikonloppu-/
Oletus-arvojen yläpuolella (katso
[Miten laite valitsee toimintansa](#miten-laite-valitsee-toimintansa)),
huoneen omassa tärkeysjärjestyksessä. Jokainen ehto saa oman
jaksokohtaisen toimintansa laitteittain, aivan kuten Viikonloppu/Poissa
— hyödyllinen mille tahansa, mikä on ominaista juuri sille huoneelle
koko talon sijaan (tietyn henkilön läsnäolo, manuaalinen
"siivoustila"-kytkin, TV:n/mediasoittimen tila, ja niin edelleen).

### Arki/viikonloppu ja koti/poissa

Määritetään kerran, globaalisti, kohdasta **⚙ Asetukset**, ja käytetään
kaikkialla, missä Viikonloppu-/Poissa-ohitukset ja jaksojen ehdot
viittaavat niihin:

- **Arki/viikonloppu** — "ei käytössä" (aina arki), olemassa oleva
  anturi (millä tahansa napaisuudella, millä tahansa kielellä — kerrot
  itse RoomFlow'lle, mikä arvo tarkoittaa viikonloppua), tai
  sisäänrakennettu viikonpäivävalinta (valitse, mitkä päivät lasketaan
  viikonlopuksi).
- **Koti/poissa** — "ei käytössä" (aina kotona), olemassa oleva
  anturi, tai sisäänrakennettu vaihtoehto: valitse yksi tai useampi
  `person.*`-entiteetti, jolloin tila on "poissa" vasta, kun *kaikki*
  niistä raportoivat poissaoloa.

### Käsin tehty muutos pysyy voimassa

Jos sytytät tai sammutat valon itse (sovelluksesta, äänellä tai
sidotulla painikkeella), vaikka sitä normaalisti ohjaa aikataulu,
RoomFlow ei taistele sitä vastaan: taustalla tapahtuva tarkistus
soveltaa laitteeseen muutoksen uudelleen vain, kun aikataulun *oma*
tavoite todella muuttuu (uusi jakso alkaa, ehto kääntyy,
viikonloppu-/poissaolotila muuttuu) — ei jokaisella
rutiinitarkistuksella. Käsin tehty muutoksesi pysyy voimassa
seuraavaan todelliseen muutokseen asti, sen sijaan että se peruuntuisi
huomaamatta minuutin sisällä. Nimenomaiset toiminnot — "Testaa nyt"/
"Testaa kaikki", tai painikkeen "aja nyt"/"pakota jakso" — pätevät aina
riippumatta tästä, koska ne ovat nimenomaisia pyyntöjä ajaa aikataulu
uudelleen.

### Yleiskatsaus-välilehti ja tapahtumalokit

**Yleiskatsaus**-välilehti näyttää yhdellä silmäyksellä: jokaisen
huoneen nykyisen jakson ja rivin reaaliaikaisia tilakuvakkeita sen
laitteille, sekä kaksi lokia — jokaisen laitemuutoksen, jonka RoomFlow
itse teki (mikä huone/laite, mitä se teki, mikä jakso, ja *miksi* —
aikataulu, liike, tietty painike, jne.) ja jokaisen kerran, kun
aikataulun ratkaistu jakso todella muuttui. **Painikkeet**-välilehdellä
on oma erillinen lokinsa, kuvattu seuraavaksi.

#### Kun painike "ei tee mitään"

**Painikeaktiivisuus**-loki (Painikkeet-välilehti) tallentaa
*jokaisen* tunnistetun painalluksen sidotusta triggeristä, teki se
sitten mitään tai ei — joten näet tarkalleen, missä kohtaa vika on:

- **Lokiin ei ilmesty mitään lainkaan**, ei edes usean painalluksen
  jälkeen → Home Assistant ei näe painallusta siinä
  entiteetissä/tapahtumassa, jonka määritit. Raakojen laitetapahtumien
  kohdalla (Shelly ja vastaavat) tarkista laiteprofiilin kentät
  Developer Tools → Events -näkymästä sitä vasten, mitä fyysinen
  laitteesi todella lähettää — katso
  [BUTTON_PROFILES.md](BUTTON_PROFILES.md).
- **"Ohitettu (painallustyyppi ei täsmännyt)"** → tunnistus toimii,
  mutta valitsemasi painallustyyppi (yksittäinen/kaksois-/pitkä) ei
  täsmää siihen, mitä tämä painallus todella raportoi — kokeile "Mikä
  tahansa painallus" varmistaaksesi, ja rajaa sitten tarkemmaksi.
- **"Ei liitetty mihinkään"** → tunnistus ja painallustyyppi ovat
  molemmat kunnossa; tätä triggeriä ei vain ole vielä liitetty
  mihinkään laitteen tai huoneen toimintoon — lisää liitos laitteen
  tai huoneen omalta välilehdeltä.
- **"Suoritettiin"** → kaikki toimi; jos laite ei silti näkyvästi
  muuttunut, ongelma on RoomFlow'n jälkeisessä ketjussa (itse
  valoentiteetissä, ei painikkeessa).

### Asetukset-välilehti

Kaikki, mikä ei ole ominaista yhdelle huoneelle, painikkeelle tai
liiketunnistinmääritykselle: Arki/viikonloppu- ja Koti/poissa-lähteet
(yllä), aikataulujen hallinta, sekä RoomFlow'n oman laitteen nimi/alue
(jota käytetään ryhmittämään sen omat Päivätyyppi-/Kotitila-anturit —
katso alla).

### RoomFlow'n luomat entiteetit

Kaikki tavallisia Home Assistant -entiteettejä, käytettävissä omissa
automaatioissasi ja kojelaudoissasi ihan kuten mitkä tahansa muutkin:

- **Päivätyyppi**- ja **Kotitila**-anturit, ryhmiteltynä RoomFlow'n
  oman laitteen alle (nimetty/sijoitettu Asetuksista).
- Per huone, **tila-anturi** (ryhmiteltynä kyseisen huoneen oman
  alueen alle), joka näyttää voittavan oman ehdon, "Poissa"/
  "Viikonloppu", tai nykyisen jakson nimen.
- Per aikataulu, **Nykyinen jakso** -anturi sekä yksi `binary_sensor`
  jaksoa kohti ("päällä" juuri silloin, kun kyseinen jakso on
  parhaillaan ratkaistu) — ulotettuna aikataulukohtaisesti, jotta
  kahdella aikataululla voi kummallakin olla jakso nimeltä "aamu"
  ilman, että ne törmäävät keskenään.

### Diagnostiikka

**Settings → Devices & services → RoomFlow → Download diagnostics**
antaa sinulle rakenteellisen tilannekuvan (määrät, ehto-/triggerityypit,
aikakatkaisut, tärkeysjärjestysasetukset) vikailmoituksia varten,
sisältämättä tarkkoja laitteidesi `entity_id`-tunnuksia, omien ehtojen
kohteita, tai painiketriggerien entiteettejä/tapahtumadataa.

## Osallistuminen

Vikailmoitukset ja pull requestit ovat tervetulleita. Tämä on
suhteellisen nuori projekti — odota joitakin kulmikkuuksia, erityisesti
kehittyneempien ehtoyhdistelmien ja lisälaitetyyppien osalta (climate,
media_player jne. ovat luonnollisia seuraavia askelia). Jos olet
varmistanut raa'an tapahtuman painikeprofiilin (esim. Shelly gen1) omaa
laitteistoasi vasten, tai haluat lisätä uuden, katso
[BUTTON_PROFILES.md](BUTTON_PROFILES.md).

## Tuetut kielet

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl) —
tämä README, kortin oma käyttöliittymä ja config flow noudattavat kaikki
samoja 8 kieltä. Kortti valitsee kielensä automaattisesti Home
Assistantin kieliasetuksen perusteella.

## Lisenssi

MIT — katso [LICENSE](LICENSE).
