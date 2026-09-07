# Wijzigingen

## 0.1.2 — aanvullende correctie aanmelding

- Accepteert de callbackvorm `parro://oauth2:443/` die voorkomt in de [aanmeldtests van de vastgezette Parro-SDK](https://github.com/anneschuth/parro-cli/blob/4e0de03ff6c47ccaf1d99b1abd7e8b7643f95df0/tests/test_login.py#L118-L120). De eerdere controle wees deze vorm ook bij een correcte `state` af.
- Behoudt de exacte controle van de oorspronkelijke OAuth-`state` en de beperking tot de verwachte callbackbestemming.

Lokaal gecontroleerd met **200 geslaagde tests**, inclusief de volledige aanmeldketen zonder accountkeuze en accountkeuze via header of XML. Code- en formatteringscontroles slagen.

De nieuwe live aanmeldpoging met 0.1.1 mislukte nog met `state_mismatch`. De SDK-test toont een ondersteunde callbackvorm; de werkelijke callback van die praktijkproef is daarmee niet vastgesteld. Versie 0.1.2 moet opnieuw live worden geprobeerd voordat een geslaagde accountaanmelding kan worden bevestigd.

## 0.1.1 — correctie aanmeldproces

- Behoudt de oorspronkelijke OAuth-`state` wanneer de aanmeldserver het autorisatiepad hervat zonder een nieuwe `state` mee te geven. Een later aangeboden afwijkende waarde wordt afgewezen.
- Onderscheidt technische fouten in de aanmeldflow van geweigerde aanmeldgegevens, zodat een technische fout niet als een onjuist wachtwoord wordt gemeld.
- Logt bij een technische aanmeldfout uitsluitend een vooraf toegestane foutcategorie, zonder tokens, aanmeldgegevens of serverinhoud.

Lokaal gecontroleerd met **170 geslaagde tests** tegen Home Assistant Core 2026.8.3 en een gemockte Parro-server; Ruff-codecontrole geslaagd.

Na installatie van 0.1.1 via HACS en een herstart mislukte de nieuwe live aanmeldpoging nog met `state_mismatch`. Deze correctie verhelpt een gevonden fout in de afhandeling van het aanmeldproces; zij is niet bevestigd als oorzaak van de eerdere mislukte praktijkproef.

## 0.1.0 — eerste testversie

- Aanmelding in Home Assistant, keuze uit meerdere identiteiten, koppeling aan de echte account-ID en heraanmelding.
- Tokenverversing met eenmalig herstel van een API-lezing na een 401; geen tokenbestand van de Parro-CLI.
- Compacte sensoren voor verbinding, laatste synchronisatie, kinderen, groepen, ongelezen mededelingen en ongelezen gesprekken.
- Instelbare polling van 15–240 minuten, standaard 30 minuten.
- Vier begrensde leesacties voor mededelingen, gesprekken, berichten en kalender-URL's.
- Beperkte diagnostiek en uitsluitend bijlagemetadata; geen verzenden, markeren, downloads of periodiek ophalen van chatinhoud.
- Handmatige installatie-ZIP met inventaris en aparte voorbereiding van een HACS-repository.

Lokaal getest met een gemockte Parro-server en Home Assistant Core 2026.8.3. De daaropvolgende download en installatie via HACS zijn bevestigd; de accountaanmelding is nog niet geslaagd. Zie de releasechecklist voor de resterende praktijkproeven.
