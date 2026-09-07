# Parro voor Home Assistant

Een eigen, onofficiële Home Assistant-integratie voor compacte schoolstatus en het op verzoek lezen van Parro-informatie. Aanmelden en accountkeuze gaan via de Home Assistant-interface. Een aparte app, MQTT-brug of browserextensie is niet nodig.

[![Open Parro in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=carlmegens&repository=ParroHACS&category=integration)

Opent deze repository in HACS. HACS moet al geïnstalleerd zijn in je Home Assistant.

**Versie 0.1.0 is een eerste testversie.** De automatische tests gebruiken Home Assistant Core 2026.8.3 en een gemockte Parro-server. Aanmelden met een echt Parro-account, installatie op een Home Assistant-host en downloaden via HACS zijn nog niet live beproefd.

Lokale controle op 7 september 2026: **142 tests geslaagd**, inclusief de volledige aanmeld-, installatie-, leesactie- en tokenverversingsketen binnen de Home Assistant-testomgeving. Codecontrole en controle van de actie-interface en vertalingen zijn geslaagd.

## Vereisten

- Home Assistant Core **2026.8.3 of nieuwer**; de lokale testbasis is precies 2026.8.3.
- Een Parro-/ParnasSys-account met toegang tot de gewenste schoolinformatie.
- Internettoegang vanuit Home Assistant naar `inloggen.parnassys.net` en `rest-v2.parro.com`. Home Assistant installeert de vastgezette afhankelijkheid `parro==1.1.0` bij het laden.
- Voor installatie via HACS: een gepubliceerde, openbare GitHub-repository met deze integratie. Voor de lokale ZIP is HACS niet nodig.

## Installeren via HACS

Met de knop hierboven open je Parro rechtstreeks in HACS. Handmatig toevoegen kan ook:

1. Open HACS, kies het menu met de drie puntjes en **Aangepaste repositories / Custom repositories**.
2. Voeg **https://github.com/carlmegens/ParroHACS** toe, met type **Integratie / Integration**.
3. Open **Parro** in HACS, download de integratie en herstart Home Assistant.
4. Ga naar **Instellingen → Apparaten en diensten → Integratie toevoegen**, zoek **Parro** en meld je aan.
5. Kies de juiste identiteit wanneer het account meerdere ParnasSys-identiteiten aanbiedt.

Dit is een aangepaste HACS-repository; opname in de standaardcatalogus is niet aangevraagd. HACS gebruikt de bestanden van de standaardbranch `main`. Zie de [officiële uitleg voor aangepaste repositories](https://www.hacs.xyz/docs/faq/custom_repositories/). De indeling volgt de [integratievereisten van HACS](https://www.hacs.xyz/docs/publish/integration/).

## Handmatig installeren

1. Open [de repository](https://github.com/carlmegens/ParroHACS) en kies **Code → Download ZIP**.
2. Pak de ZIP uit en kopieer de map `custom_components/parro` naar de configuratiemap van Home Assistant. Het resultaat moet `<config>/custom_components/parro/manifest.json` zijn. Op Home Assistant OS is de configuratiemap doorgaans `/config`.
3. Herstart Home Assistant en voeg **Parro** toe onder **Instellingen → Apparaten en diensten**.

Kopieer alleen de integratiemap naar Home Assistant. De tests en documentatie in de repository zijn bedoeld voor ontwikkeling. Een met de lokale distributiehelper gebouwde installatie-ZIP bevat dezelfde integratiemap en openbare documentatie, plus een aparte SHA-256-inventaris.

Bij handmatig bijwerken: bewaar de bestaande integratiemap als reservekopie buiten `custom_components`, vervang de volledige map `parro` door de nieuwe versie en herstart Home Assistant. De accountinstellingen staan afzonderlijk in Home Assistant. Verwijderen gaat via **Apparaten en diensten**; verwijder daarna desgewenst de map en herstart.

## Aanmelding en instellingen

Voer het wachtwoord alleen in de Home Assistant-configuratieflow in. Het blijft tijdelijk in het geheugen tijdens het aanmelden en wordt niet als instelling opgeslagen. Toegangs- en ververstokens worden in de Home Assistant-config entry bewaard; er wordt geen tokenbestand van de Parro-CLI aangemaakt. Behandel Home Assistant-back-ups daarom als privégegevens.

De gekozen identiteit wordt na aanmelding gekoppeld aan de echte account-ID van de Parro-API. Hetzelfde account kan niet dubbel worden toegevoegd. Bij verlopen of ingetrokken toegang vraagt Home Assistant om opnieuw aan te melden; daarbij moet hetzelfde account worden gekozen.

De integratie ververst tokens automatisch en probeert een lezing na een 401 eenmaal opnieuw na tokenverversing. Een wijziging van tokens veroorzaakt geen herlaadlus.

Via **Configureren** bij de integratie kun je het ophaalinterval wijzigen. Standaard is dit **30 minuten**; toegestaan is **15 tot en met 240 minuten**. Dit interval staat los van eventuele verversing van een dashboard of scherm.

## Sensoren

| Sensor | Betekenis |
| --- | --- |
| Verbinding | De laatste periodieke synchronisatie is geslaagd en er is sindsdien geen API-lezing mislukt. Na een fout herstelt deze status bij een geslaagde periodieke synchronisatie. |
| Laatste geslaagde synchronisatie | Tijdstip van de laatste geslaagde synchronisatie; blijft bij een storing op dat tijdstip staan. |
| Kinderen | Aantal gekoppelde kinderen, voor zover de API dit levert. |
| Groepen | Aantal gekoppelde groepen, voor zover de API dit levert. |
| Ongelezen mededelingen | Het door Parro geleverde aantal ongelezen mededelingen. |
| Ongelezen gesprekken | Het door Parro geleverde aantal chatrooms met ongelezen inhoud, dus geen aantal afzonderlijke chatberichten. |

Ontbrekende aantallen zijn onbekend, nooit automatisch nul. Voor kinderen en groepen wordt begrensd opgehaald; bij een volle lijst van 100 resultaten is het totaal onbekend. Bij een mislukte synchronisatie zijn tellers niet beschikbaar en staat de verbindingssensor uit. Sensorstates, attributen en diagnostiek bevatten geen berichtteksten, namen van kinderen, bijlageadressen of iCal-URL's.

## Leesacties op aanvraag

De acties hieronder leveren een antwoord terug. Ze zijn bruikbaar via **Ontwikkelaarstools → Acties** of in een automatisering met `response_variable`. Een handmatige actie vereist een Home Assistant-beheerder. Automatiseringen zonder gebruikerscontext kunnen de acties uitvoeren.

Alle acties vereisen **`config_entry_id`** van het gewenste Parro-account. De actie-interface biedt hiervoor een integratiekiezer. In YAML kun je de ID vinden met een bekende Parro-entiteit: `{{ config_entry_id('sensor.jouw_parro_entiteit') }}` onder **Ontwikkelaarstools → Sjablonen**. Entiteitsnamen kunnen per installatie verschillen.

`limit` is optioneel: standaard **20**, minimaal **1**, maximaal **50**. Het antwoord bevat `items`, `returned` en `limit`. Een begrensd resultaat is geen volledig archief; er wordt niet onbeperkt door pagina's gelopen. Ook lange teksten en lijsten met bijlagemetadata worden afgekapt om de respons compact te houden.

| Actie | Extra invoer | Inhoud van `items` |
| --- | --- | --- |
| `parro.get_announcements` | — | Mededelingen met geselecteerde velden en bijlagemetadata. |
| `parro.get_chatrooms` | — | Gesprekken met de benodigde identificatie voor een vervolgopvraag. |
| `parro.get_messages` | `chatroom_id` | Berichten uit één gekozen gesprek. |
| `parro.get_calendar_urls` | — | Door Parro geleverde iCal-URL's. |

De antwoordvelden zijn bewust beperkt; niet door de API geleverde waarden zijn `null`:

- Mededelingen: `id`, `title`, `contents`, `created_at`, `sort_date`, `read`, `sender`, `group_id`, `attachments`.
- Gesprekken: `id`, `title`, `type`, `sort_date`, `unread_count`.
- Berichten: `id`, `text`, `created_at`, `last_modified_at`, `read`, `sender`, `attachments`. Aanmaak- en wijzigingstijd blijven afzonderlijk; een wijzigingstijd wordt niet als aanmaaktijd ingevuld.
- Kalenderadressen: een lijst URL-strings. De integratie opent deze adressen niet en leest hiermee geen agenda-afspraken uit.

Bijlagemetadata bevat `id`, `name`, `type`, `size` en een beperkte lijst `entries` met `type`, `size`, `mime_type`. Berichtinhoud blijft de door Parro geleverde tekst; deze integratie interpreteert geen schoolafspraken of HTML.

`chatroom_id` komt uit `get_chatrooms` en is een positief numeriek ID van maximaal 20 cijfers. Dit voorbeeld is een actiestap in een automatisering; vul de eigen config-entry-ID in:

```yaml
action: parro.get_announcements
data:
  config_entry_id: "VUL_CONFIG_ENTRY_ID_IN"
  limit: 10
response_variable: schoolmededelingen
```

Lees daarna bijvoorbeeld `schoolmededelingen['items']` uit in volgende stappen. De inhoud van antwoorden is privé en kan zichtbaar worden in automatiseringstraces of in bestemmingen die je zelf kiest. De integratie slaat deze antwoorden niet als sensorattributen op. iCal-URL's kunnen toegang tot een agenda geven: deel ze alleen met de bedoelde bestemming.

Periodieke synchronisatie leest geen chatinhoud. Deze versie biedt geen verzenden, markeren als gelezen, bijlagen downloaden, absenties, inschrijven of AI-aansluiting. Bijlagen worden alleen als metadata teruggegeven, zonder download-URL. Eventuele effecten van leesaanroepen op de leesstatus aan de serverkant moeten nog met een echt account worden gecontroleerd. Volledige kalenderdetails en de volledigheid van de historie zijn niet aangetoond.

## Problemen oplossen

- **Parro verschijnt niet bij integraties:** controleer de mapstructuur en herstart Home Assistant. Controleer dat Core aan de minimumversie voldoet en de afhankelijkheid kon worden geïnstalleerd.
- **Aanmelden mislukt:** controleer het account via Parro zelf. Herhaald proberen kan niet-ondersteunde aanmeldvarianten, zoals een vereiste interactieve stap, niet verhelpen. Deze versie gebruikt een gebruikersnaam/wachtwoordflow; andere aanmeldvarianten zijn niet live gevalideerd.
- **Verbinding uit of tellers niet beschikbaar:** wacht op de volgende synchronisatie of herlaad de integratie eenmaal. Bij een authenticatieprobleem biedt Home Assistant heraanmelding aan.
- **Verkeerde identiteit bij heraanmelding:** kies dezelfde Parro-identiteit. Voeg een ander account toe als aparte integratie.
- **Een leesactie faalt:** kies een geladen Parro-config entry en controleer de grenzen van `limit` en `chatroom_id`.

Diagnostiek bevat uitsluitend de instellingsstatus, het ophaalinterval, de uitkomst van de laatste synchronisatie en het tijdstip van de laatste geslaagde synchronisatie. Deel geen wachtwoorden, tokens, kalender-URL's of schoolberichten in een probleemmelding. De integratie is onafhankelijk ontwikkeld en wordt niet door Parro, ParnasSys of Home Assistant ondersteund.

## Lokaal controleren en een pakket maken

Voer onderstaande opdrachten uit vanuit de root van deze integratie. Voor de testomgeving is Python **3.14.2 of nieuwer binnen 3.14** nodig; de distributiehelper gebruikt alleen de standaardbibliotheek.

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/prepare_repository.py --local-archive dist/parro-0.1.0-local.zip
```

De helper weigert bestaande uitvoer te overschrijven. Kies bij opnieuw bouwen een nieuwe ZIP-naam of verwijder bewust alleen een eerdere, zelf gemaakte ZIP en bijbehorende inventaris. De testbestanden en testafhankelijkheden staan in de repository; het installatiepakket bevat uitsluitend de integratie en expliciet toegestane documentatie. De meegeleverde SDK wordt bij installatie opgehaald en is niet in het pakket gekopieerd.

De metadata voor deze repository controleer je met `python3 scripts/prepare_repository.py --check`. Voor een nieuwe versie of een fork kan de helper daarnaast een **nieuwe lokale stagingmap** met expliciet opgegeven GitHub-gegevens maken:

```sh
python3 scripts/prepare_repository.py \
  --output dist/repository-ready \
  --owner carlmegens \
  --repo ParroHACS \
  --codeowner carlmegens
python3 dist/repository-ready/scripts/prepare_repository.py --check
```

`--codeowner` accepteert een GitHub-gebruiker of `organisatie/team`, met of zonder `@`, en kan worden herhaald. `--check` weigert ontbrekende publicatiemetadata en placeholders. Een geslaagde stagingcontrole bewijst de lokale structuur; eigendom, bereikbaarheid en HACS-installatie zijn daarmee nog niet online gecontroleerd. De helper publiceert niets, installeert niets en neemt geen contact op met GitHub of Parro.

De distributielijst voor ZIP en minimale staging sluit overdrachtsnotities, tests, caches en dashboard- of familiebestanden uit en weigert symlinks en onverwachte bestanden in de integratiemap. Deze bronrepository bevat daarnaast de gecontroleerde synthetische tests en hun testconfiguratie; die zijn niet nodig voor HACS-installatie. Controleer daarnaast de werkelijke inhoud voor publicatie. Gebruik de [releasechecklist](RELEASE_CHECKLIST.md) voor de resterende account-, host- en publicatieproeven.

## Licentie en afhankelijkheid

De eigen integratiecode valt onder de [MIT-licentie](LICENSE). De apart geïnstalleerde afhankelijkheid [`parro` 1.1.0](https://github.com/anneschuth/parro-cli/releases/tag/v1.1.0) is van de auteurs van `parro-cli` en behoudt haar eigen licentie en auteursrecht. Dit project maakt geen aanspraak op die broncode of op de merken Parro en ParnasSys.
