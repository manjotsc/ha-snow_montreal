# Montreal Snow Removal Integration for Home Assistant

A Home Assistant custom integration for tracking Montreal snow removal operations using the free [Planif-Neige Public API](https://github.com/ludodefgh/planif-neige-public-api).

## Features

- **No API key required** - Uses the free public API
- Track snow removal status for specific streets
- **Address search** - Find your street by typing your address
- Binary sensors for parking restrictions
- Planned start/end times for snow removal operations
- Support for both English and French
- UI-based configuration
- Services for street lookup in automations

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Search for "Montreal Snow Removal" and install it
7. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/snow_montreal` folder to your Home Assistant `config/custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "Montreal Snow Removal"
4. Choose your setup method:
   - **Search by address** (recommended)
   - **Enter street ID manually**

### Option 1: Search by Address

1. Select "Search by address"
2. Enter your civic number (optional but recommended)
3. Enter your street name (e.g., "Saint-Denis", "Sherbrooke")
4. Select your street from the results

### Option 2: Manual Entry (Finding Your Street ID)

If the search doesn't find your street, you can enter the street ID manually:

#### Step 1: Download the Geobase Data

1. Go to [Montreal Geobase Double Dataset](https://donnees.montreal.ca/dataset/geobase-double)
2. Download the **GeoJSON** file (`gbdouble.json`)

#### Step 2: Find Your Street ID

Open the file and search for your street. Look for the `COTE_RUE_ID` value:

```json
{
  "properties": {
    "COTE_RUE_ID": 10200162,
    "NOM_VOIE": "Acadie",
    "NOM_VILLE": "MTL",
    "DEBUT_ADRESSE": 0,
    "FIN_ADRESSE": 0,
    "COTE": "Gauche",
    "TYPE_F": "boulevard"
  }
}
```

**Key fields:**
| Field | Description |
|-------|-------------|
| `COTE_RUE_ID` | **The street ID you need** |
| `NOM_VOIE` | Street name |
| `DEBUT_ADRESSE` | Starting address number |
| `FIN_ADRESSE` | Ending address number |
| `COTE` | Side of street: "Gauche" (Left) or "Droit" (Right) |

#### Step 3: Enter in Home Assistant

1. Select "Enter street ID manually"
2. Enter the `COTE_RUE_ID` value
3. Enter a display name (e.g., "Home", "123 Acadie")

**Tip:** Each side of a street has a different ID. If your address is on the left side (even numbers typically), look for `"COTE": "Gauche"`. For right side (odd numbers), look for `"COTE": "Droit"`.

You can add multiple streets by adding the integration multiple times.

## Entities

For each configured street, the following entities are created:

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.<street>_snow_removal_status` | Current status (snowed, cleared, scheduled, in_progress, etc.) |
| `sensor.<street>_planned_start` | Planned start time for snow removal |
| `sensor.<street>_planned_end` | Planned end time for snow removal |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.<street>_snow_removal_active` | ON when snow removal is scheduled or in progress |
| `binary_sensor.<street>_parking_restricted` | ON when parking is restricted due to snow removal |

## Snow Removal Status Codes

| Status | English | French | Description |
|--------|---------|--------|-------------|
| 0 | Snowed | Enneigé | Not yet cleared |
| 1 | Cleared | Déneigé | Removal completed |
| 2 | Scheduled | Planifié | Removal scheduled |
| 3 | Rescheduled | Replanifié | Rescheduled to new date |
| 4 | Deferred | Reporté | Deferred, date TBD |
| 5 | In Progress | En cours | Currently clearing |
| 10 | Clear | Dégagé | Between operations |

## Services

### `snow_montreal.search_street`

Search for a street by name or address. Returns matching street segments with their IDs.

**Parameters:**
- `street_name` (required): The name of the street to search for
- `civic_number` (optional): Civic/house number to narrow down results

**Example:**
```yaml
service: snow_montreal.search_street
data:
  street_name: "Saint-Denis"
  civic_number: 1234
```

**Response:**
```yaml
results:
  - street_id: 123456
    street_name: "Saint-Denis"
    address_start: 1200
    address_end: 1300
    side: "Droit"
    borough: "Le Plateau-Mont-Royal"
    display_name: "Saint-Denis (1200-1300, R)"
count: 1
```

### `snow_montreal.refresh_geobase`

Force refresh the cached street data from Montreal's Geobase.

```yaml
service: snow_montreal.refresh_geobase
```

## Automation Examples

### Notify when parking is restricted

```yaml
automation:
  - alias: "Snow Removal Parking Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.my_street_parking_restricted
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Snow Removal Alert"
          message: "Parking will be restricted on your street. Move your car!"
```

### Notify when snow removal is scheduled

```yaml
automation:
  - alias: "Snow Removal Warning"
    trigger:
      - platform: state
        entity_id: sensor.my_street_snow_removal_status
        to: "scheduled"
    action:
      - service: notify.mobile_app
        data:
          title: "Snow Removal Scheduled"
          message: >
            Snow removal is scheduled for your street starting at
            {{ states('sensor.my_street_planned_start') }}
```

### Notify when snow removal starts

```yaml
automation:
  - alias: "Snow Removal Started"
    trigger:
      - platform: state
        entity_id: sensor.my_street_snow_removal_status
        to: "in_progress"
    action:
      - service: notify.mobile_app
        data:
          title: "Snow Removal In Progress"
          message: "Snow removal has started on your street!"
```

## Data Sources & Credits

### Planif-Neige Public API
- Free public API by [@ludodefgh](https://github.com/ludodefgh/planif-neige-public-api)
- Updates every 10 minutes
- No API key required

### City of Montreal Open Data
- **Geobase Double** - Street segment data for address lookup
- Data provided under the [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/)
- [Montreal Open Data Portal](https://donnees.montreal.ca/)

**Important:** The traffic signs in force on streets for parking during periods of snow loading always prevail over the data transmitted by this API.

## Troubleshooting

### Street not found in search
- Try different variations of the street name (e.g., "St-Denis" vs "Saint-Denis")
- Try without the civic number first to see all segments
- Use manual entry with the Geobase file (see above)

### No data for my street
- Snow removal data is only available during active operations
- Check if your borough is covered (all 19 Montreal boroughs are supported)
- Verify the street ID is correct using the search service

### First search is slow
- The first search downloads the Geobase data (~50MB)
- Subsequent searches use the cached data (24-hour cache)

## Links

- [Planif-Neige Public API](https://github.com/ludodefgh/planif-neige-public-api)
- [Info-Neige Montreal Application](https://montreal.ca/en/services/info-neige-montreal-application)
- [Snow Removal Operations Map](https://montreal.ca/en/services/snow-removal-operations-map)
- [Montreal Geobase Double Dataset](https://donnees.montreal.ca/dataset/geobase-double)

## License

MIT License
