# Wijzigingen

## 0.1.1 — correctie aanmeldproces

- Behoudt de oorspronkelijke OAuth-`state` wanneer de aanmeldserver het autorisatiepad hervat zonder een nieuwe `state` mee te geven. Een later aangeboden afwijkende waarde wordt afgewezen.
- Onderscheidt technische fouten in de aanmeldflow van geweigerde aanmeldgegevens, zodat een technische fout niet als een onjuist wachtwoord wordt gemeld.
- Logt bij een technische aanmeldfout uitsluitend een vooraf toegestane foutcategorie, zonder tokens, aanmeldgegevens of serverinhoud.

Lokaal gecontroleerd met **170 geslaagde tests** tegen Home Assistant Core 2026.8.3 en een gemockte Parro-server; Ruff-codecontrole geslaagd.

De eerdere versie is via HACS geïnstalleerd, maar de accountaanmelding is nog niet geslaagd. Deze correctie richt zich op een gevonden fout in de afhandeling van het aanmeldproces; de werkelijke aanmeldroute en oorzaak van de mislukte praktijkproef zijn daarmee niet vastgesteld. Een nieuwe live aanmeldproef met 0.1.1 blijft nodig.

## 0.1.0 — eerste testversie

- Aanmelding in Home Assistant, keuze uit meerdere identiteiten, koppeling aan de echte account-ID en heraanmelding.
- Tokenverversing met eenmalig herstel van een API-lezing na een 401; geen tokenbestand van de Parro-CLI.
- Compacte sensoren voor verbinding, laatste synchronisatie, kinderen, groepen, ongelezen mededelingen en ongelezen gesprekken.
- Instelbare polling van 15–240 minuten, standaard 30 minuten.
- Vier begrensde leesacties voor mededelingen, gesprekken, berichten en kalender-URL's.
- Beperkte diagnostiek en uitsluitend bijlagemetadata; geen verzenden, markeren, downloads of periodiek ophalen van chatinhoud.
- Handmatige installatie-ZIP met inventaris en aparte voorbereiding van een HACS-repository.

Lokaal getest met een gemockte Parro-server en Home Assistant Core 2026.8.3. De daaropvolgende download en installatie via HACS zijn bevestigd; de accountaanmelding is nog niet geslaagd. Zie de releasechecklist voor de resterende praktijkproeven.
