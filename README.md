# 🌨️ Montreal Snow Removal for Home Assistant

Track snow removal operations on your street using Montreal's Planif-Neige data. **No API key required.**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

## Features

- Real-time snow removal status updates (every 10 minutes)
- Parking restriction alerts
- Planned start/end times
- English & French support
- Easy address search or manual street ID entry

## Installation

### HACS (Recommended)

1. Add this repo as a custom repository in HACS
2. Search for "Montreal Snow Removal" and install
3. Restart Home Assistant

### Manual

Copy `custom_components/snow_montreal` to your `config/custom_components` folder and restart.

## Setup

**Settings → Devices & Services → Add Integration → Montreal Snow Removal**

### Search by Address

Enter your street name and civic number to find your street automatically.

### Manual Entry

If search doesn't work, find your street ID from the [Montreal Geobase](https://donnees.montreal.ca/dataset/geobase-double):

1. Download `gbdouble.json`
2. Search for your street and find the `COTE_RUE_ID`:

```json
{
  "COTE_RUE_ID": 10200162,
  "NOM_VOIE": "Acadie",
  "COTE": "Gauche",
  "DEBUT_ADRESSE": 1000,
  "FIN_ADRESSE": 1200
}
```

> **Tip:** Each side of a street has a different ID. `Gauche` = Left, `Droit` = Right.

## Entities

| Entity | Description |
|--------|-------------|
| `sensor.*_snow_removal_status` | Status: snowed, cleared, scheduled, in_progress, clear |
| `sensor.*_planned_start` | When snow removal begins |
| `sensor.*_planned_end` | When snow removal ends |
| `binary_sensor.*_snow_removal_active` | ON when scheduled or in progress |
| `binary_sensor.*_parking_restricted` | ON when you need to move your car |

## Status Values

| Code | Status | Meaning |
|:----:|--------|---------|
| 0 | Snowed | Not yet cleared |
| 1 | Cleared | Removal complete |
| 2 | Scheduled | Removal planned |
| 3 | Rescheduled | Date changed |
| 4 | Deferred | Postponed |
| 5 | In Progress | Currently clearing |
| 10 | Clear | Between operations |

## Automation Example

```yaml
automation:
  - alias: "Snow Removal Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.my_street_parking_restricted
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Move Your Car!"
          message: "Snow removal scheduled for your street."
```

## Services

| Service | Description |
|---------|-------------|
| `snow_montreal.search_street` | Search for streets by name |
| `snow_montreal.refresh_geobase` | Re-download street database |

## Credits

- [Planif-Neige Public API](https://github.com/ludodefgh/planif-neige-public-api) by @ludodefgh
- [Montreal Open Data](https://donnees.montreal.ca/)

---

**Note:** Always follow posted traffic signs. They take precedence over this data.
