# Montreal Snow Removal Integration for Home Assistant

A Home Assistant custom integration for tracking Montreal snow removal operations using the City of Montreal's Planif-Neige API.

## Features

- Track snow removal status for specific streets
- **Address search** - Find your street by typing your address (no need to look up IDs manually!)
- Binary sensors for parking restrictions
- Planned start/end times for snow removal operations
- Support for both English and French
- UI-based configuration
- Services for street lookup in automations

## Prerequisites

### API Token

You need an API token from Montreal Open Data to use this integration. To obtain one:

1. Send an email to donneesouvertes@montreal.ca
2. Request access to the Planif-Neige API
3. You will receive an API token to use with this integration

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
4. Enter your API token
5. Choose how to find your street:
   - **Search by address**: Enter your civic number and street name to find matching streets
   - **Enter manually**: Enter the street ID directly if you know it
6. Select your street from the search results

You can add multiple streets by adding the integration multiple times.

## Entities

For each configured street, the following entities are created:

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.<street>_snow_removal_status` | Current snow removal status (scheduled, in_progress, completed, etc.) |
| `sensor.<street>_snow_removal_planned_start` | Planned start time for snow removal |
| `sensor.<street>_snow_removal_planned_end` | Planned end time for snow removal |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.<street>_snow_removal_active` | ON when snow removal is scheduled or in progress |
| `binary_sensor.<street>_parking_restricted` | ON when parking is restricted due to snow removal |

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

### Notify before snow removal starts

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
            {{ states('sensor.my_street_snow_removal_planned_start') }}
```

### Advanced notification with timing

```yaml
automation:
  - alias: "Snow Removal Advance Warning"
    trigger:
      - platform: time_pattern
        minutes: "/30"
    condition:
      - condition: state
        entity_id: binary_sensor.my_street_parking_restricted
        state: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "Reminder: Move Your Car"
          message: >
            Snow removal on your street ends at
            {{ state_attr('sensor.my_street_snow_removal_status', 'planned_end') }}
```

## Data Sources & Credits

This integration uses data from the following sources:

### City of Montreal Open Data
- **Planif-Neige API** - Real-time snow removal scheduling data
- **Geobase Double** - Street segment data for address lookup
- Data provided under the [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/)
- [Montreal Open Data Portal](https://donnees.montreal.ca/)

### OpenStreetMap / Nominatim
- Address geocoding powered by [Nominatim](https://nominatim.org/)
- Uses [OpenStreetMap](https://www.openstreetmap.org/) data
- © OpenStreetMap contributors, [ODbL license](https://opendatacommons.org/licenses/odbl/)

**Important:** The traffic signs in force on streets for parking during periods of snow loading always prevail over the data transmitted by this API.

## Troubleshooting

### Street not found in search
- Try different variations of the street name (e.g., "St-Denis" vs "Saint-Denis")
- Try without the civic number first to see all segments
- Use the `snow_montreal.search_street` service to debug

### No data for my street
- Snow removal data is only available during active operations
- Check if your borough is covered (all 19 Montreal boroughs are supported since 2021)
- Verify the street ID is correct using the search service

## Links

- [Info-Neige Montreal Application](https://montreal.ca/en/services/info-neige-montreal-application)
- [Snow Removal Operations Map](https://montreal.ca/en/services/snow-removal-operations-map)
- [Montreal Open Data - Snow Removal](https://donnees.montreal.ca/dataset/deneigement)
- [Double Geobase Dataset](https://donnees.montreal.ca/dataset/geobase-double)

## License

MIT License
