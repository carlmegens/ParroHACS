# Releasechecklist 0.1.0

De eerste versie is lokaal gecontroleerd en gepubliceerd in `carlmegens/ParroHACS`. Accountproef, hostinstallatie en HACS-downloadproef zijn nog niet uitgevoerd. De publicatiecontrole hieronder is ook bruikbaar voor volgende versies. Vul na een proef alleen technische uitkomsten in, zonder namen, schoolinformatie, tokens of privé-URL's.

## Lokale kandidaat

- [x] Tests uitvoeren tegen Home Assistant Core 2026.8.3 en `parro==1.1.0`: 142 geslaagd op 7 september 2026; Ruff geslaagd.
- [x] Lokale ZIP bouwen en de SHA-256-inventaris controleren. Bij bronwijzigingen opnieuw bouwen.
- [x] Pakketbestanden vergelijken met de bron en de inventaris; actieschema en vertalingen gecontroleerd.
- [x] Bevestigen dat uitsluitend `custom_components/parro` en toegestane openbare documentatie aanwezig zijn; geen tests, overdrachtsnotities, familiegegevens, tokens of dashboardbestanden.

## Account- en hostproef, na keuze voor installatie

- [ ] Reservekopie van Home Assistant maken en Core-versie controleren.
- [ ] Handmatig installeren; herstart en eerste aanmelding via de Home Assistant-interface controleren.
- [ ] Expliciete accountkeuze testen als het account meerdere identiteiten aanbiedt; dubbele toevoeging van dezelfde identiteit afwijzen.
- [ ] Tellers vergelijken met het Parro-account, met onderscheid tussen ongelezen gesprekken en losse berichten.
- [ ] Tokenverversing, herstart met opgeslagen tokens en heraanmelding met hetzelfde account controleren.
- [ ] Instelbaar interval en herstellen na netwerkuitval controleren; wijziging van tokens mag geen reloadlus geven.
- [ ] Elk van de vier acties één keer begrensd uitvoeren en de leesstatus in Parro vóór en na vergelijken.
- [ ] Controleren dat sensorattributen en diagnostiek geen berichtinhoud, kindnamen of privé-URL's bevatten.
- [ ] Verwijderen, herladen en handmatig bijwerken controleren.

## HACS-publicatie

- [x] GitHub-eigenaar `carlmegens`, repository `ParroHACS` en codeowner `@carlmegens` vastgelegd; de repository is openbaar.
- [x] Stagingmap gemaakt met de expliciete waarden; tests, codecontrole en `scripts/prepare_repository.py --check` geslaagd.
- [x] Staginginhoud, licentie, pakketinhoud en resterende beperkingen beoordeeld; openbare bron bevat uitsluitend de integratie, documentatie en synthetische tests.
- [x] Gecontroleerde bestanden gepubliceerd op `main` in de door de gebruiker gekozen repository; beschrijving en relevante GitHub-topics aanwezig. Alle 35 gepubliceerde bestanden gecontroleerd tegen de lokale bron.
- [ ] HACS-validatie en installatie als aangepaste repository testen.
- [ ] Desgewenst een GitHub-release `v0.1.0` publiceren. `hacs.json` gebruikt repositorybestanden en geen ZIP-release.
- [ ] README en wijzigingen bijwerken met uitsluitend daadwerkelijk uitgevoerde proeven en ondersteunde versies.

De helper controleert geen GitHub-eigendom of bereikbaarheid. Een succesvolle lokale releasecheck is geen bewijs van een geslaagde HACS-download of live accountwerking.
