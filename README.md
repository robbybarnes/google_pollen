# Google Pollen Integration for Home Assistant

[![HACS Validation](https://github.com/robbybarnes/google_pollen/actions/workflows/hacs.yaml/badge.svg)](https://github.com/robbybarnes/google_pollen/actions/workflows/hacs.yaml)
[![Hassfest Validation](https://github.com/robbybarnes/google_pollen/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/robbybarnes/google_pollen/actions/workflows/hassfest.yaml)

A Home Assistant custom integration that provides pollen forecasts using the [Google Pollen API](https://developers.google.com/maps/documentation/pollen/overview).

## Features

- **Pollen Index Sensors**: Get the Universal Pollen Index (UPI) for grass, tree, and weed pollen (scale 0-5)
- **Pollen Level Sensors**: Human-readable pollen levels (None, Very Low, Low, Moderate, High, Very High)
- **5-Day Forecast**: Access upcoming pollen forecasts via sensor attributes
- **Health Recommendations**: Get health advice based on current pollen levels
- **Automatic Updates**: Data refreshes every 6 hours

## Sensors Created

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.google_pollen_grass_pollen_index` | Grass pollen index | UPI (0-5) |
| `sensor.google_pollen_grass_pollen_level` | Grass pollen category | Text |
| `sensor.google_pollen_tree_pollen_index` | Tree pollen index | UPI (0-5) |
| `sensor.google_pollen_tree_pollen_level` | Tree pollen category | Text |
| `sensor.google_pollen_weed_pollen_index` | Weed pollen index | UPI (0-5) |
| `sensor.google_pollen_weed_pollen_level` | Weed pollen category | Text |

### Sensor Attributes

Each index sensor includes additional attributes:
- `in_season`: Whether the pollen type is currently in season
- `health_recommendations`: List of health tips based on pollen levels
- `index_description`: Description of what the current index level means
- `forecast`: Array of upcoming days with index and category values

## Prerequisites

### Google Cloud API Key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Pollen API** from the API Library
4. Create an API key in the Credentials section
5. (Recommended) Restrict the API key to only the Pollen API

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/robbybarnes/google_pollen` as an Integration
5. Click "Add"
6. Search for "Google Pollen" and install it
7. Restart Home Assistant

### Manual Installation

1. Download the `custom_components/google_pollen` folder from this repository
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Google Pollen"
4. Enter your Google API key
5. Enter the latitude and longitude for the location you want to monitor (defaults to your Home Assistant location)

## Coverage

The Google Pollen API covers over 65 countries with 1km × 1km resolution. See the [official coverage documentation](https://developers.google.com/maps/documentation/pollen/coverage) for details.

## Example Automations

### Send notification when pollen is high

```yaml
automation:
  - alias: "High Pollen Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.google_pollen_grass_pollen_index
        above: 3
    action:
      - service: notify.mobile_app
        data:
          title: "High Pollen Alert"
          message: >
            Grass pollen is {{ states('sensor.google_pollen_grass_pollen_level') }}.
            {{ state_attr('sensor.google_pollen_grass_pollen_index', 'health_recommendations')[0] }}
```

### Display pollen card on dashboard

```yaml
type: entities
title: Pollen Levels
entities:
  - entity: sensor.google_pollen_grass_pollen_level
    name: Grass
  - entity: sensor.google_pollen_tree_pollen_level
    name: Tree
  - entity: sensor.google_pollen_weed_pollen_level
    name: Weed
```

## Troubleshooting

### "Invalid API key" error
- Ensure the Pollen API is enabled in your Google Cloud project
- Check that your API key has no IP restrictions or that your Home Assistant IP is allowed

### Sensors show "Unknown"
- Pollen data may not be available for your location
- Check the [coverage map](https://developers.google.com/maps/documentation/pollen/coverage) to verify support

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This integration is not affiliated with or endorsed by Google. All product names, trademarks, and registered trademarks are property of their respective owners.
