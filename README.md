# 🌨️ Montreal Snow Removal

**Home Assistant integration for tracking snow removal operations in Montreal**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/badge/release-v2.0.0-blue.svg?style=flat-square)](https://github.com/manjotsc/ha-snow_montreal/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)

> **Powered by [Planif-Neige Public API](https://github.com/ludodefgh/planif-neige-public-api)** — Free API by [@ludodefgh](https://github.com/ludodefgh), no key required

## ✨ Features

| | |
|---|---|
| 📊 **Status Tracking** | Know when your street is scheduled, in progress, or cleared |
| 🚗 **Parking Alerts** | Get notified when parking restrictions apply |
| 🕐 **Planned Times** | See scheduled start and end times |
| 🔍 **Easy Setup** | Search by address or enter street ID manually |
| 🌐 **Bilingual** | Full English & French support |

> ⚠️ **Data Accuracy:** Updates depend on contractors reporting to dispatchers, who then update the city's system. Expect some delay between actual operations and status changes.

## 📦 Installation

<details>
<summary><b>HACS (Recommended)</b></summary>

1. Open HACS → Integrations → Menu (⋮) → Custom repositories
2. Add `https://github.com/manjotsc/ha-snow_montreal` → Category: Integration
3. Search "Montreal Snow Removal" → Install → Restart Home Assistant
</details>

<details>
<summary><b>Manual</b></summary>

Copy `custom_components/snow_montreal` to your `config/custom_components` folder and restart.
</details>

## ⚙️ Setup

**Settings → Devices & Services → Add Integration → Montreal Snow Removal**

### Option 1: Search by Address
Enter your street name and civic number — the integration will find your street.

### Option 2: Manual Entry
Find your street ID using one of these methods:

**Method A:** Use the `snow_montreal.search_street` service in Developer Tools → Services:
```yaml
service: snow_montreal.search_street
data:
  street_name: "Acadie"
  civic_number: 1234
```

**Method B:** Download [Montreal Geobase](https://donnees.montreal.ca/dataset/geobase-double) and search for your street:
```json
{
  "COTE_RUE_ID": 10200162,    ← This is your street ID
  "NOM_VOIE": "Acadie",
  "COTE": "Gauche"            ← Left side / Right side (Droit)
}
```

## 📊 Entities

```
sensor.{street}_snow_removal_status        → Current status
sensor.{street}_planned_start              → Scheduled start time
sensor.{street}_planned_end                → Scheduled end time
binary_sensor.{street}_snow_removal_active → ON when active
binary_sensor.{street}_parking_restricted  → ON when restricted
```

## 🚦 Status Codes

| Code | Status | Description |
|:----:|:-------|:------------|
| `0` | Snowed | Not yet cleared |
| `1` | Cleared | Removal complete |
| `2` | Scheduled | Removal planned |
| `3` | Rescheduled | Date changed |
| `4` | Deferred | Postponed |
| `5` | In Progress | Currently clearing |
| `10` | Clear | Between operations |

## 🤖 Automation Example

```yaml
automation:
  - alias: "Snow Removal Alert"
    trigger:
      platform: state
      entity_id: binary_sensor.my_street_parking_restricted
      to: "on"
    action:
      service: notify.mobile_app
      data:
        title: "🚗 Move Your Car!"
        message: "Snow removal scheduled for your street"
```

## 🛠️ Services

| Service | Description |
|:--------|:------------|
| `snow_montreal.search_street` | Search streets by name |
| `snow_montreal.refresh_geobase` | Re-download street database |

---

**Credits:** [Planif-Neige Public API](https://github.com/ludodefgh/planif-neige-public-api) by [@ludodefgh](https://github.com/ludodefgh) • [Montreal Open Data](https://donnees.montreal.ca/)

⚠️ Always follow posted traffic signs — they take precedence over this data.
