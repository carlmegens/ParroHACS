# Wijzigingen

## 0.1.0 — eerste testversie

- Aanmelding in Home Assistant, keuze uit meerdere identiteiten, koppeling aan de echte account-ID en heraanmelding.
- Tokenverversing met eenmalig herstel van een API-lezing na een 401; geen tokenbestand van de Parro-CLI.
- Compacte sensoren voor verbinding, laatste synchronisatie, kinderen, groepen, ongelezen mededelingen en ongelezen gesprekken.
- Instelbare polling van 15–240 minuten, standaard 30 minuten.
- Vier begrensde leesacties voor mededelingen, gesprekken, berichten en kalender-URL's.
- Beperkte diagnostiek en uitsluitend bijlagemetadata; geen verzenden, markeren, downloads of periodiek ophalen van chatinhoud.
- Handmatige installatie-ZIP met inventaris en aparte voorbereiding van een HACS-repository.

Getest met een gemockte Parro-server en Home Assistant Core 2026.8.3. Een echte accountproef, hostinstallatie en HACS-downloadproef staan nog open. Zie de releasechecklist.
