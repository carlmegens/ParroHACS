# Parro voor Home Assistant

Schoolmededelingen en foto's op je Home Assistant-dashboard, met accountkeuze, toegang per gebruiker en compacte statussensoren. Eén HACS-installatie levert de Parro-integratie en de bijbehorende dashboardkaart.

[![Open Parro in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=carlmegens&repository=ParroHACS&category=integration)

**Versie 0.2.0 voegt de kaart voor mededelingen en foto's toe.** Installatie via HACS, aanmelding en de samenvatting met tellers zijn met versie 0.1.2 door de gebruiker bevestigd. Versie 0.2.0 is lokaal gecontroleerd met **374 Python-tests en 14 browsercontroles**, op Home Assistant Core 2026.8.3 met een gemockte Parro-server en uitsluitend fictieve schoolgegevens. De kaart is visueel gecontroleerd op desktop en mobiel, in lichte en donkere weergave. Praktijkcontroles staan in de [releasechecklist](RELEASE_CHECKLIST.md).

## Installeren via HACS

Vereist: Home Assistant Core **2026.8.3 of nieuwer**, HACS en een Parro-/ParnasSys-account met de gewenste schoolinformatie. De knop hierboven opent deze repository in je eigen HACS-installatie.

1. Open **Parro** in HACS en download de integratie. Handmatig toevoegen kan via **Aangepaste repositories**, adres **https://github.com/carlmegens/ParroHACS**, type **Integratie**.
2. Herstart Home Assistant.
3. Ga naar **Instellingen → Apparaten en diensten → Integratie toevoegen**, zoek **Parro** en meld je aan.
4. Kies de juiste identiteit wanneer het account meerdere ParnasSys-identiteiten aanbiedt.
5. Open je dashboard en herlaad de pagina om de meegeleverde kaart te laden.

Dit is een aangepaste HACS-repository. HACS gebruikt de bestanden op `main`; opname in de standaardcatalogus is niet aangevraagd. Zie de [officiële HACS-instructies](https://www.hacs.xyz/docs/faq/custom_repositories/).

## De kaart toevoegen

1. Kies op je dashboard **Dashboard bewerken → Kaart toevoegen** en zoek **Parro**.
2. Kies in de visuele editor het gekoppelde Parro-account.
3. Stel de titel, het aantal mededelingen en de fotoweergave in en sla de kaart op.

De kaart toont standaard vijf mededelingen met beschikbare foto's. Je kunt 1–20 mededelingen kiezen en desgewenst op één groep filteren. De lijst is begrensd en is geen volledig schoolarchief. De kaart toont mededelingen; gesprekken blijven beschikbaar via de bestaande leesacties verderop.

Voor handmatig toevoegen kun je beginnen met onderstaande configuratie en daarna het account in de visuele editor kiezen:

```yaml
type: custom:parro-card
```

Het account is vereist voordat de kaart inhoud kan ophalen. Voor een los dashboard staat een generiek [voorbeeld met toelichting](examples/README.md) klaar. Het voorbeeld gebruikt uitsluitend invulvelden voor de eigen configuratie.

## Andere gebruikers toegang geven

Home Assistant-beheerders hebben standaard toegang tot de kaartinhoud. Om een andere gebruiker mee te laten lezen, open je **Instellingen → Apparaten en diensten → Parro → Configureren** en selecteer je die gebruiker bij **Toegang tot mededelingen en foto’s**.

Toegang geldt per gekoppeld Parro-account. De kaart biedt alleen accounts aan die de ingelogde Home Assistant-gebruiker mag lezen. Het delen van een dashboard of het invullen van een account-ID verleent op zichzelf geen toegang. Een beheerder kan de geselecteerde gebruikers later weer verwijderen. De bestaande vier leesacties blijven voor beheerders en automatiseringen beschikbaar; de nieuwe instelling geeft daarop geen extra rechten.

## Kaartresource controleren

Bij dashboardresources die Home Assistant via de interface beheert, registreert of actualiseert de integratie haar eigen kaartresource automatisch. Als **Parro** niet verschijnt of je **Custom element doesn't exist: parro-card** ziet, herlaad dan eerst de browserpagina.

Controleer zo nodig onder **Instellingen → Dashboards → menu → Resources / Bronnen** of deze resource eenmaal aanwezig is:

- URL: `/parro_static/parro-card.js?v=0.2.0`
- Type: **JavaScript-module**

Beheer je dashboardresources in YAML, voeg dan dit item toe aan de bestaande lijst met resources:

```yaml
- url: /parro_static/parro-card.js?v=0.2.0
  type: module
```

Zie de [officiële uitleg over resources](https://developers.home-assistant.io/docs/frontend/custom-ui/registering-resources/). De kaartcode staat in `custom_components/parro/frontend/parro-card.js` en wordt door de integratie aangeboden; je hoeft geen bestand naar `www` te kopiëren.

## Aanmelding, verversing en foto's

Voer het wachtwoord alleen in de Home Assistant-aanmeldflow in. Het blijft tijdelijk in het geheugen tijdens het aanmelden en wordt niet als instelling opgeslagen. Toegangs- en ververstokens worden in de Home Assistant-config entry bewaard; de Parro-CLI schrijft hiervoor geen tokenbestand. Behandel Home Assistant-back-ups als privégegevens.

De gekozen identiteit wordt aan de echte Parro-account-ID gekoppeld. Hetzelfde account kan niet dubbel worden toegevoegd. De integratie ververst tokens automatisch en herstelt een API-lezing na een 401 eenmaal met tokenverversing. Bij ingetrokken toegang vraagt Home Assistant om opnieuw aan te melden met hetzelfde account.

Via **Parro → Configureren** stel je het interval voor de statussensoren in: standaard **30 minuten**, toegestaan **15–240 minuten**. De kaart haalt haar mededelingen op aanvraag op en ververst elke **vijf minuten** zolang zij zichtbaar is. De server hergebruikt de opgehaalde lijst vijf minuten, zodat meerdere kaarten niet voortdurend dezelfde schoolinformatie opvragen. Bij een verbindingsfout kan de laatst opgehaalde lijst nog maximaal één uur worden getoond, met een melding dat de gegevens mogelijk verouderd zijn.

Foto's worden via een beveiligde Home Assistant-route aangeboden en tijdelijk in een begrensde privé-cache bewaard. De kaart krijgt geen originele school- of bijlage-URL's. Per mededeling worden maximaal drie foto's voorbereid; de kaart toont maximaal twaalf foto's tegelijk. Afbeeldingen worden als JPEG met maximaal 1600 pixels aan de langste zijde aangeboden. Dit is geen algemene bijlagedownloader.

Home Assistant heeft internettoegang nodig naar `inloggen.parnassys.net`, `rest-v2.parro.com` en de door Parro gebruikte, gecontroleerde afbeeldingsbestemmingen. De vastgezette afhankelijkheid is `parro==1.1.0`.

## Statussensoren

| Sensor | Betekenis |
| --- | --- |
| Verbinding | Verbindingsstatus van de statussynchronisatie. Een mislukte leesactie kan deze ook uitschakelen; een geslaagde statussynchronisatie herstelt de status. De kaart meldt haar eigen laadproblemen. |
| Laatste geslaagde synchronisatie | Tijdstip van de laatste geslaagde synchronisatie; blijft bij een storing op dat tijdstip staan. |
| Kinderen | Aantal gekoppelde kinderen, voor zover de API dit levert. |
| Groepen | Aantal gekoppelde groepen, voor zover de API dit levert. |
| Ongelezen mededelingen | Het door Parro geleverde aantal ongelezen mededelingen. |
| Ongelezen gesprekken | Aantal chatrooms met ongelezen inhoud; geen aantal afzonderlijke chatberichten. |

Ontbrekende aantallen zijn onbekend, nooit automatisch nul. Bij een volle begrensde lijst van 100 kinderen of groepen is het totaal onbekend. Bij een mislukte synchronisatie zijn tellers niet beschikbaar. Sensorstates, attributen en diagnostiek bevatten geen berichtteksten, kindnamen, foto's, bijlageadressen of iCal-URL's.

## Leesacties voor automatiseringen

De vier bestaande acties leveren een antwoord terug via **Ontwikkelaarstools → Acties** of `response_variable` in een automatisering. Een handmatige actie vereist een Home Assistant-beheerder; automatiseringen zonder gebruikerscontext kunnen deze ook uitvoeren.

Alle acties vereisen `config_entry_id` van het gekozen Parro-account. De actie-interface biedt hiervoor een integratiekiezer. `limit` is optioneel: standaard **20**, minimaal **1**, maximaal **50**. Het antwoord bevat `items`, `returned` en `limit`; een selectie is geen volledig archief.

| Actie | Extra invoer | Antwoorditems |
| --- | --- | --- |
| `parro.get_announcements` | — | Mededelingen met geselecteerde velden en bijlagemetadata. |
| `parro.get_chatrooms` | — | Gesprekken met identificatie voor een vervolgopvraag. |
| `parro.get_messages` | `chatroom_id` | Berichten uit één gesprek. |
| `parro.get_calendar_urls` | — | iCal-URL's; de integratie leest hiermee geen afspraken uit. |

`chatroom_id` is een positief numeriek ID van maximaal 20 cijfers, afkomstig uit `get_chatrooms`. Voorbeeld van een actiestap:

```yaml
action: parro.get_announcements
data:
  config_entry_id: VUL_PARRO_CONFIG_ENTRY_ID_IN
  limit: 10
response_variable: schoolmededelingen
```

Lees daarna `schoolmededelingen['items']` uit. Deze antwoorden kunnen privé-inhoud en kalenderadressen bevatten en zichtbaar worden in automatiseringstraces of in de bestemming die je zelf kiest. De acties leveren voor bijlagen uitsluitend metadata; foto-inhoud voor de kaart loopt via de afzonderlijke beveiligde route.

Voor eigen toepassingen is ook een aangemelde HTTP-lezing beschikbaar: `GET /api/parro/{config_entry_id}/feed?limit=5`, optioneel met `group_id`. Deze gebruikt dezelfde toegangscontrole als de kaart en accepteert 1–20 mededelingen. Gebruik de gebruikelijke Home Assistant-authenticatie; zet geen toegangstoken in de URL of in dashboard-YAML. De kaart gebruikt de overeenkomstige Home Assistant-WebSocketverbinding.

Periodieke statussynchronisatie leest geen chatinhoud. Deze versie biedt geen verzenden, markeren als gelezen, absenties, inschrijven, volledige archiefexport of AI-aansluiting. Eventuele effecten van leesaanroepen op de leesstatus aan de serverkant zijn nog niet volledig live beproefd.

## Problemen oplossen

- **Geen kaart in de kaartkiezer:** herlaad de browser en controleer de kaartresource zoals hierboven beschreven.
- **Geen account om te kiezen of geen toegang:** controleer of Parro is aangemeld en of de ingelogde Home Assistant-gebruiker beheerder is of toegang heeft gekregen bij de Parro-opties.
- **Een foto ontbreekt:** niet elke bijlage is een ondersteunde foto. De kaart begrenst het aantal foto's; een geweigerde of niet beschikbare afbeelding maakt de mededeling niet onleesbaar.
- **Aanmeldgegevens geweigerd:** controleer het account via Parro zelf. Deze integratie gebruikt een gebruikersnaam/wachtwoordflow; andere aanmeldvarianten zijn niet live gevalideerd.
- **Technische aanmeldfout:** werk bij naar de nieuwste versie, herstart Home Assistant en begin een nieuwe aanmelding. De fout betekent niet automatisch dat het wachtwoord onjuist is. De integratie logt alleen een vaste technische foutcategorie.
- **Verbinding uit of tellers niet beschikbaar:** wacht op de volgende synchronisatie of herlaad de integratie eenmaal. Bij een authenticatieprobleem biedt Home Assistant heraanmelding aan.

Diagnostiek bevat beperkte technische status. Deel geen wachtwoorden, tokens, kalender-URL's, schoolberichten of foto's in een probleemmelding.

## Handmatige installatie en ontwikkeling

Download de repository via **Code → Download ZIP**. Kopieer de volledige map `custom_components/parro` naar de Home Assistant-configuratiemap, zodat `<config>/custom_components/parro/manifest.json` bestaat. Herstart Home Assistant en volg daarna de stappen voor aanmelden en het toevoegen van de kaart. Bij handmatig bijwerken vervang je de volledige integratiemap; bewaar een eventuele reservekopie buiten `custom_components`.

Voor de testomgeving is Python **3.14.2 of nieuwer binnen 3.14** nodig. Voer vanuit deze repository uit:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/prepare_repository.py --check
.venv/bin/python scripts/prepare_repository.py --local-archive dist/parro-0.2.0-local.zip
```

De meegeleverde kaart heeft ook [synthetische browsertests en een lokale voorvertoning](tests/frontend/README.md). Deze gebruiken de echte kaartcode met verzonnen accounts, berichten en lokaal getekende foto's. De installatiekaart zelf heeft geen Node-afhankelijkheden.

De installatie-ZIP bevat de integratie inclusief kaart, openbare documentatie en het generieke voorbeelddashboard. Een aparte SHA-256-inventaris vermeldt de inhoud. De helper weigert bestaande uitvoer te overschrijven en kopieert alleen expliciet toegestane bestanden. Overdrachtsnotities, lokale verslagen, tests, ontwikkelhulpbestanden, afhankelijkheidsmappen, screenshots en familie- of dashboardgegevens worden niet meegenomen. Synthetische tests blijven wel in de bronrepository beschikbaar voor onderhoud.

Voor een nieuwe lokale publicatiemap kun je `scripts/prepare_repository.py` gebruiken met `--output`, `--owner`, `--repo` en `--codeowner`. De helper controleert de lokale structuur en publicatiemetadata, waaronder niet ingevulde waarden. Hij installeert of publiceert niets en neemt geen contact op met GitHub of Parro.

## Licentie

De eigen integratie en kaart vallen onder de [MIT-licentie](LICENSE). De apart geïnstalleerde afhankelijkheid [`parro` 1.1.0](https://github.com/anneschuth/parro-cli/releases/tag/v1.1.0) behoudt haar eigen licentie en auteursrecht. Dit project is onofficieel en wordt niet door Parro, ParnasSys of Home Assistant ondersteund.
