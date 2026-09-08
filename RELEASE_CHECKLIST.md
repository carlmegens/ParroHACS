# Releasechecklist 0.3.0

Versie 0.3.0 maakt mededelingen en gesprekken bereikbaar vanuit het bestaande Parro-apparaat. De eerdere dashboardkaart blijft optioneel. Leg alleen technische testuitkomsten vast; neem geen accountgegevens, schoolinhoud, foto's of privé-URL's op.

## Lokale kandidaat 0.3.0

- [x] 482 tests geslaagd tegen Home Assistant Core 2026.8.3 en `parro==1.1.0`; Ruff-codecontrole en formatteringscontrole geslaagd.
- [x] Echte frontendbundel synthetisch gecontroleerd met 23 browsercontroles, inclusief toetsenbordfocus. Desktop-, mobiele, popup- en paneelbeelden onafhankelijk beoordeeld.
- [x] Bestaande sensoren behouden: uitsluitend de twee ongelezen-tellers krijgen openbare popupverwijzingen; apparaatlink verwijst intern naar de eigen config entry. Geen schoolinhoud in states of diagnostiek.
- [x] Globale module beschikbaar vóór een dashboardbezoek; verborgen accountpaneel registreert zonder de bestaande optiesknop te vervangen. Herhaald registreren, eigen URL bijwerken, behoud van andere modules/panelen en veilige foutlogging lokaal gecontroleerd.
- [x] Lokale statische route levert exact het ene frontendbestand en geen naastliggende integratiebestanden. Entity- en frontendcontroles: 19 synthetische tests geslaagd.
- [ ] Beide tellerpop-ups controleren met de echte frontendbundel, ook na accountwissel, directe apparaatnavigatie, sluiten en opnieuw openen.
- [ ] Verborgen accountpaneel en terugkeer naar het Parro-apparaat controleren; geen dashboardconfiguratie nodig.
- [x] Afzonderlijke rechten voor mededelingen en gesprekken controleren, inclusief andere account-ID, anonieme aanvragen, ingetrokken toegang en heraanmelding. Synthetisch gecontroleerd.
- [x] Begrensde gesprekkenlijst en berichten ophalen uit een gesprek van hetzelfde account; vijfminutencache en maximaal één uur oude terugval bij verbindingsfouten controleren. Synthetisch gecontroleerd.
- [x] Foto's per bron synthetisch gecontroleerd op rechten, tijdelijke opslag en begrensde afmetingen. Geen bron-URL's in antwoorden. Accountbrede cacheblokkade na een authenticatiefout en behoud van gedeelde foto's bij cache-opruiming getest.
- [x] Bestaande vier leesacties blijven voor beheerders en automatiseringen; toegekende popuprechten geven geen extra actierechten. Synthetisch gecontroleerd.
- [x] Distributiecontrole met verplichte `chat_feed.py` en exact één `frontend/parro-card.js` geslaagd; 50 synthetische distributietests controleren ook uitsluiting van ontwikkelhulpbestanden, afhankelijkheden, screenshots en privégegevens.
- [ ] Eventuele installatie-ZIP uitpakken en vergelijken met bron en SHA-256-inventaris.

## Praktijkproef 0.3.0

- [ ] Bijwerken via HACS en Home Assistant herstarten; geladen versie controleren en browser herladen.
- [ ] Vanaf het bestaande Parro-apparaat op beide ongelezen-tellers klikken en juiste inhoud controleren.
- [ ] Mededelingen, gesprekken en beschikbare foto's vergelijken met Parro; geen volledigheid van geschiedenis claimen.
- [ ] Interne apparaatlink naar de Parro-weergave en terugkeer naar het apparaat controleren.
- [ ] Normale integratieopties blijven bereikbaar; mededelingen- en gespreksrechten afzonderlijk toekennen en intrekken.
- [ ] Tokenverversing, herstart, heraanmelding en geen privé-inhoud in sensorattributen of diagnostiek controleren.
- [ ] Leesstatus in Parro vóór en na de begrensde leesaanroepen vergelijken.

## Publicatie 0.3.0

- [x] Repository `carlmegens/ParroHACS` is openbaar, met codeowner `@carlmegens`.
- [ ] Definitieve bron en publicatiemap vergelijken; tests, codecontrole en `scripts/prepare_repository.py --check` uitvoeren.
- [ ] Alleen gecontroleerde integratiecode, frontendbundel, openbare documentatie, generieke voorbeelden en synthetische tests publiceren.
- [ ] Gepubliceerde inhoud vergelijken met bron en beschikbaarheid van de update in HACS controleren.
- [ ] README en wijzigingen aanvullen met uitsluitend daadwerkelijk uitgevoerde controles.

## Eerder gecontroleerd

- Versie 0.1.2: 200 lokale tests; installatie, aanmelding en samenvatting met tellers door de gebruiker bevestigd.
- Versie 0.2.0: 374 Python-tests en 14 browsercontroles; mededelingen, foto's, groepsfilter, automatische kaartregistratie en visuele editor live gecontroleerd. Toegang en intrekking voor andere gebruikers zijn synthetisch getest.

Lokale tests bewijzen geen volledige werking van de nieuwe pop-ups met ieder Parro-account of iedere Home Assistant-versie. De [browsertesthandleiding](tests/frontend/README.md) beschrijft de synthetische controles.
