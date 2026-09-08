# Voorbeelddashboard Parro

[dashboard.yaml](dashboard.yaml) is een zelfstandig, generiek dashboard met één Parro-kaart. Het bevat geen accounts, foto's of schoolberichten. De integratie en kaart worden samen geïnstalleerd vanuit [ParroHACS](https://github.com/carlmegens/ParroHACS).

Dit voorbeeld is optioneel. Vanaf versie 0.3.0 open je mededelingen en gesprekken rechtstreeks via de bestaande tellers op het Parro-apparaat. Daarvoor hoef je geen dashboard aan te maken.

## Via de dashboardeditor

1. Installeer Parro en meld een account aan volgens de [installatiehandleiding](../README.md#installeren-via-hacs).
2. Maak onder **Instellingen → Dashboards** een nieuw leeg dashboard, bijvoorbeeld **Parro**, en open dit.
3. Kies **Dashboard bewerken → Kaart toevoegen**, zoek **Parro** en kies het gekoppelde Parro-account in de visuele editor.
4. Stel de titel, het aantal mededelingen en de fotoweergave in. Voor gebruik door een andere Home Assistant-gebruiker geeft een beheerder die gebruiker toegang via **Parro → Configureren → Toegang tot mededelingen en foto’s**.

Een minimale kaartconfiguratie waarmee je daarna de visuele editor kunt openen:

```yaml
type: custom:parro-card
```

De kaart haalt pas informatie op nadat een account is gekozen. Beheerders hebben standaard toegang; voor andere gebruikers bepaalt de instelling van het Parro-account of zij de inhoud mogen lezen.

## De volledige YAML gebruiken

Open de ruwe configuratie-editor van een **nieuw leeg dashboard** en plak de inhoud van `dashboard.yaml`. Vervang `VUL_PARRO_CONFIG_ENTRY_ID_IN` door de ID van je eigen Parro-config entry. Je kunt de ID ook door accountkeuze in de visuele kaarteditor laten invullen. Een config-entry-ID is een verwijzing naar een ingestelde integratie, geen wachtwoord of toegangssleutel.

Voor bestaande YAML-dashboards kun je dezelfde inhoud als apart dashboardbestand gebruiken en dit bij je eigen dashboardconfiguratie registreren. De [officiële dashboarddocumentatie](https://www.home-assistant.io/dashboards/dashboards/#adding-yaml-dashboards) beschrijft die registratie. Het voorbeeld vervangt geen bestaande dashboardconfiguratie automatisch.

## Kaartopties

| Instelling | Betekenis |
| --- | --- |
| `type` | Altijd `custom:parro-card`. |
| `config_entry_id` | Vereist om inhoud op te halen; kies het eigen Parro-account in de editor. |
| `title` | Titel boven de mededelingen. |
| `limit` | Aantal mededelingen of berichten, 1–20; het voorbeeld gebruikt 5. |
| `show_images` | `true` toont beschikbare foto's; `false` laat ze weg. |
| `group_id` | Optioneel: filter op één groep van het gekozen account. |
| `source` | Optioneel: `announcements` (standaard) of `messages`. Gesprekken vereisen afzonderlijk verleende toegang. |
| `chatroom_id` | Optioneel bij `source: messages`: positief numeriek gespreks-ID als tekenreeks, afkomstig uit de gesprekken van dit account. |

De groepsfilter werkt binnen de begrensd opgehaalde selectie. Een lege lijst bewijst niet dat de groep nooit mededelingen heeft gehad. Dit voorbeeld toont mededelingen en foto's; gesprekken zijn ook vanuit het Parro-apparaat te openen.

## Als de kaart niet verschijnt

In dashboards met opslag via de Home Assistant-interface registreert de integratie de kaartresource automatisch. Herlaad de pagina na installatie of een update. Controleer zo nodig de dashboardresources en voeg deze JavaScript-module eenmaal toe:

```yaml
url: /parro_static/parro-card.js?v=0.3.0
type: module
```

Bij resources die je in YAML beheert, voeg je deze module toe aan de bestaande lijst met dashboardresources. De resource hoort bij de geïnstalleerde integratie; een aparte HACS-repository voor de kaart is niet nodig. Zie de [resource-instructies](../README.md#meegeleverde-weergave-controleren).
