# Releasechecklist 0.2.0

Installatie via HACS, aanmelding en de samenvatting met tellers zijn met 0.1.2 door de gebruiker bevestigd. Versie 0.2.0 voegt een dashboardkaart, foto's en toegang per Home Assistant-gebruiker toe. Leg alleen technische testuitkomsten vast; neem geen accountgegevens, schoolinhoud, foto's of privé-URL's op.

## Lokale kandidaat 0.2.0

- [x] Volledige tests tegen Home Assistant Core 2026.8.3 en `parro==1.1.0`: 374 geslaagd; daarnaast 14 browsercontroles. Historisch had 0.1.2 200 geslaagde tests.
- [x] Code- en formatteringscontrole geslaagd; kaart en visuele editor gecontroleerd.
- [x] Accountselectie en toegang voor beheerder, toegestane gebruiker en gebruiker zonder toegang lokaal gecontroleerd; verzoeken met een ander account-ID, anonieme aanvragen en ingetrokken toegang afgedekt door synthetische tests.
- [ ] Feedgrenzen van 1–20 mededelingen, vijfminutencache, maximaal één uur oude terugval bij verbindingsfouten en groepsfilter controleren; broncollectie blijft begrensd.
- [ ] Foto's controleren op geauthenticeerde toegang, begrensde tijdelijke opslag en begrensde afmetingen; geen oorspronkelijke school- of bijlage-URL's in kaartantwoorden.
- [ ] Bestaande vier acties blijven alleen toegankelijk voor beheerders en automatiseringen, ook wanneer een gebruiker toegang tot de kaart heeft.
- [x] Automatische registratie en actualisatie van uitsluitend de eigen kaartresource, herhaald registreren en YAML-fallback lokaal gecontroleerd. De statische route levert exact het kaartbestand; andere integratiebestanden zijn niet bereikbaar via die route. Zeven synthetische tests slagen.
- [x] Veertien synthetische browsertests met de echte kaartcode geslaagd, waaronder accountwissel, ingetrokken toegang, veilige tekstweergave en begrensde fotoweergave. Voorvertoningen voor desktop/licht, mobiel/donker en visuele editor beoordeeld. Zie [de browsertesthandleiding](tests/frontend/README.md).
- [ ] Actieschema, vertalingen en generiek YAML-voorbeelddashboard controleren.
- [x] Distributiecontrole geslaagd met 49 synthetische distributietests: één integratie met verplichte backendmodules, exact `frontend/parro-card.js` en de twee toegestane voorbeeldbestanden; ontwikkelhulpbestanden, afhankelijkheidsmappen, screenshots en privégegevens uitgesloten.
- [ ] Eventuele nieuwe installatie-ZIP uitpakken en vergelijken met bron en SHA-256-inventaris.

## Praktijkproef

- [x] Installatie via HACS en geslaagde aanmelding met 0.1.2 bevestigd.
- [x] Samenvatting met tellers na aanmelding door de gebruiker bevestigd.
- [ ] Bijwerken naar 0.2.0 en Home Assistant herstarten; de geladen versie controleren.
- [ ] Kaart toevoegen aan een apart proefdashboard en het eigen account in de visuele editor kiezen.
- [ ] Mededelingen en beschikbare foto's vergelijken met Parro; titel, aantal en groepsfilter controleren.
- [ ] Andere Home Assistant-gebruiker expliciet toegang geven, met die gebruiker lezen en toegang daarna weer intrekken.
- [ ] Verifiëren dat er geen berichtinhoud of foto's in sensorattributen of diagnostiek terechtkomen.
- [ ] Tokenverversing, herstart en heraanmelding met hetzelfde account controleren.
- [ ] Leesstatus in Parro vóór en na de begrensde leesaanroepen vergelijken.

## Publicatie 0.2.0

- [x] Repository `carlmegens/ParroHACS` is openbaar, met codeowner `@carlmegens`.
- [ ] Definitieve bron en publicatiemap vergelijken; tests, codecontrole en `scripts/prepare_repository.py --check` uitvoeren.
- [ ] Alleen gecontroleerde integratiecode, kaart, openbare documentatie, generieke voorbeelden en synthetische tests publiceren.
- [ ] Gepubliceerde inhoud vergelijken met de bron en beschikbaarheid van de update in HACS controleren.
- [ ] Desgewenst een GitHub-release `v0.2.0` publiceren. HACS gebruikt de integratierepository; de kaart hoort bij hetzelfde pakket.
- [ ] README en wijzigingen aanvullen met uitsluitend daadwerkelijk uitgevoerde controles.

Lokale tests en een geslaagde pakketcontrole bewijzen geen volledige werking van de nieuwe kaart met ieder Parro-account of iedere Home Assistant-versie.
