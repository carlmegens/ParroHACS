# Parro card synthetic browser checks

This harness imports the actual bundled `parro-card.js`. The small mock Home Assistant surface supplies synthetic accounts, messages and locally drawn test photos. It does not use a Home Assistant instance, credentials, school data, external image assets or external font requests. Nothing from this directory is included in the HACS integration package.

From this directory, install the browser test dependency and Chromium once:

```sh
npm install
npx playwright install chromium
```

Start `npm run preview`, then run `npm test` in a second terminal. The preview is available at `http://127.0.0.1:8766/tests/frontend/index.html`. The production card itself has no Node or framework dependency. The preview server binds only localhost and serves exactly the preview HTML, its harness module and the bundled card JavaScript; repository files, reports and screenshots are unavailable over HTTP.

Preview variants:

- `?source=messages`: conversation selector; choosing one room loads only its messages.
- `?source=messages&room=101`: pinned synthetic conversation with a photo.
- `?surface=popup&source=messages`: actual `more-info-parro` component with HA-style `hass`/`stateObj` properties.
- `?surface=panel&source=messages`: actual `parro-panel` with tabs and a routed account; add `&chooseAccount=1` for its account selector.
- `?theme=dark`: mobile or desktop dark theme.
- `?editor=1`: working visual editor below the card.
- `?state=loading`: unresolved request, with loading skeleton.
- `?state=authentication_expired&lang=en`: English sign-in state.
- `?state=noaccount`, `?state=choose`, `?state=empty`, `?state=unauthorized`, `?state=cannot_connect`: actual empty/error surfaces.
- `?state=stale`: temporarily cached announcement notice.

The browser checks cover authenticated blob photos, message/photo keyboard controls, plain-text XSS resistance, old request ownership after account switches, permission revocation and URL cleanup, hidden/disconnected cards, bounded content/photo counts, editor change events, editor group cancellation, photo request deduplication and independence from ordinary HA state changes. Additional checks cover separate chat permissions, explicit single-room reads, late room/source results, source/room editor choices, HA more-info state changes, panel route/tabs/backlinks, optional panel account selection and chat empty states. Screenshots for desktop/light, mobile/dark, messages desktop/mobile, popup, panel, editor, loading and English error are written to ignored `artifacts/` with a no-horizontal-overflow assertion.

Set `PARRO_SKIP_SCREENSHOTS=1` to run only functional checks, `PARRO_PREVIEW_PORT` to change the preview port, or `PARRO_PREVIEW_URL` to test a different local harness URL.

These checks establish the custom element's behavior against the integration's WebSocket and authenticated-image contract. A final check in Home Assistant is still needed to validate installation, resource registration, theme integration and real server permissions.
