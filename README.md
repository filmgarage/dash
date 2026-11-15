# DASH HA Apps

DASH is a small set of web pages for Home Assistant dashboards on simple screens: a Fully Kiosk photo frame, a wall
tablet or an old phone. The pages are light, fast to load and show live values from Home Assistant.

You design a layout in the DASH editor inside Home Assistant, choose a skin (colours, fonts, tile style) and publish
it. A screen then opens one URL and shows the layout. The URL contains the layout, the skin and a read token, so the
screen never needs a login menu.

## What is in this repository

| Path | Contents |
|---|---|
| `repository.yaml` | Makes this repository visible as an HA App repository in Home Assistant. |
| `dash/` | The DASH HA App. See [dash/README.md](dash/README.md) for setup and screen URLs. |
| `docs/CONTRACT.md` | The contract between the editor front end and the HA App's API. |
| `dash/app/ui/status.html` | The status page: monitored entities and their layouts. See [Status page](#status-page). |

## Requirements

- Home Assistant OS or Home Assistant Supervised (HA Apps need the Supervisor).
- A screen with a modern browser, for example Fully Kiosk Browser on Android.
- Port 8092 of the Home Assistant host reachable from the screen.

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**.
2. Open the menu (⋮) in the top right and choose **Repositories**.
3. Enter the URL of this repository and add it.
4. Find **DASH** in the store, install it and open its **Configuration** tab.
5. Set a read token for the screens and save.
6. Start the HA App and open **DASH** in the sidebar.

To update, open the HA App's page and install the new version when Home Assistant offers it.

## Status page

The status page lists the entities that DASH monitors, the layouts that use each one, and any entity that is
missing from Home Assistant. Open **DASH** in the sidebar and add `status` to the end of the address in your browser.
The page is only reachable through Home Assistant's login, not on port 8092.

## Safety

The screens are served on your local network only, on port 8092. Read the safety chapter in
[dash/README.md](dash/README.md) before you publish anything, and do not forward port 8092 on your router.

## Disclaimer

**Use this HA App at your own risk.** It is provided "as is", without warranty of any kind. The author accepts no
liability for damage, data loss, security incidents or unintended device behaviour. See the disclaimer in
[dash/README.md](dash/README.md).

## Development

The HA App is written in Python (aiohttp). The tests need no Home Assistant:

```bash
cd dash
python3 -m unittest discover -s tests -p "test_*.py"
```
