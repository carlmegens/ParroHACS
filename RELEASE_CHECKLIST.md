# Releasechecklist 0.1.2

Versie 0.1.1 is via HACS geïnstalleerd en opnieuw geprobeerd; de aanmelding mislukte nog met `state_mismatch`. Versie 0.1.2 voegt ondersteuning toe voor de callbackvorm uit de tests van de vastgezette SDK. De werkelijke callback van de praktijkproef is niet vastgesteld. Een nieuwe aanmeldproef blijft nodig. Leg alleen technische uitkomsten vast, zonder namen, schoolinformatie, tokens of privé-URL's.

## Lokale kandidaat 0.1.2

- [x] Tests uitvoeren tegen Home Assistant Core 2026.8.3 en `parro==1.1.0`; **200 tests geslaagd**.
- [x] Code- en formatteringscontrole uitvoeren.
- [x] Regressietests controleren dat de SDK-callbackvorm met poort 443 en afsluitende slash bij exact overeenkomende OAuth-`state` wordt geaccepteerd.
- [x] Controleren dat afwijkende callbackbestemmingen en ontbrekende, dubbele of afwijkende `state`-waarden worden afgewezen.
- [x] Controleren dat hervatten zonder nieuwe `state` de oorspronkelijke waarde behoudt en dat technische foutmeldingen uitsluitend veilige foutcategorieën loggen.
- [x] Actieschema en vertalingen controleren.
- [ ] Eventueel een nieuwe lokale ZIP bouwen, uitpakken en vergelijken met bron en SHA-256-inventaris; oude ZIP's gelden uitsluitend voor hun oorspronkelijke versie.
- [x] Pakketinhoud controleren: alleen de integratie en toegestane openbare documentatie; geen overdrachtsnotities, lokale verslagen, tokens of familie- en dashboardbestanden.

## Account- en hostproef

- [x] Installatie van 0.1.1 via HACS, herstart en nieuwe aanmeldpoging uitgevoerd; aanmelding nog mislukt met `state_mismatch`.
- [ ] Bijwerken naar 0.1.2, Home Assistant herstarten en een nieuwe aanmelding beginnen.
- [ ] Eerste geslaagde aanmelding en aanmaak van de Parro-config entry bevestigen.
- [ ] Expliciete accountkeuze testen als het account meerdere identiteiten aanbiedt; dubbele toevoeging van dezelfde identiteit afwijzen.
- [ ] Tellers vergelijken met het Parro-account, met onderscheid tussen ongelezen gesprekken en losse berichten.
- [ ] Tokenverversing, herstart met opgeslagen tokens en heraanmelding met hetzelfde account controleren.
- [ ] Instelbaar interval en herstellen na netwerkuitval controleren; wijziging van tokens mag geen herlaadlus geven.
- [ ] Elk van de vier acties één keer begrensd uitvoeren en de leesstatus in Parro vóór en na vergelijken.
- [ ] Controleren dat sensorattributen en diagnostiek geen berichtinhoud, kindnamen of privé-URL's bevatten.
- [ ] Verwijderen, herladen en handmatig bijwerken controleren.

## Publicatie 0.1.2

- [x] Repository `carlmegens/ParroHACS` is openbaar, met codeowner `@carlmegens`, beschrijving en relevante GitHub-topics.
- [x] Definitieve bron en publicatiemap vergelijken; tests, codecontrole en `scripts/prepare_repository.py --check` uitvoeren.
- [ ] Gecontroleerde bestanden van 0.1.2 publiceren op `main` en de gepubliceerde inhoud controleren tegen de bron.
- [ ] Beschikbaarheid van de update in HACS controleren.
- [ ] Desgewenst een GitHub-release `v0.1.2` publiceren. `hacs.json` gebruikt repositorybestanden en geen ZIP-release.
- [x] README en wijzigingen bijwerken met uitsluitend daadwerkelijk uitgevoerde proeven en ondersteunde versies.

De openbare repository bevat daarnaast synthetische tests en hun testconfiguratie. De distributiehelper controleert de lokale bestandsstructuur en metadata; een geslaagde controle bewijst geen live accountwerking.
