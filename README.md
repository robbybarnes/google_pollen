# Google Pollen Integration for Home Assistant

[![HACS Validation](https://github.com/robbybarnes/google_pollen/actions/workflows/hacs.yaml/badge.svg)](https://github.com/robbybarnes/google_pollen/actions/workflows/hacs.yaml)
[![Hassfest Validation](https://github.com/robbybarnes/google_pollen/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/robbybarnes/google_pollen/actions/workflows/hassfest.yaml)
[![Tests](https://github.com/robbybarnes/google_pollen/actions/workflows/test.yaml/badge.svg)](https://github.com/robbybarnes/google_pollen/actions/workflows/test.yaml)

A Home Assistant custom integration that provides pollen forecasts using the [Google Pollen API](https://developers.google.com/maps/documentation/pollen/overview).

## Features

- **Pollen Index Sensors**: Get the Universal Pollen Index (UPI) for grass, tree, and weed pollen (scale 0-5)
- **Pollen Level Sensors**: Human-readable pollen levels (None, Very Low, Low, Moderate, High, Very High)
- **Date-Aware Forecasts**: Access up to five days of pollen data; cached readings advance at UTC midnight without an extra API request
- **Tomorrow and Peak Sensors**: Optional per-type sensors for tomorrow and the largest known upcoming index
- **Data Freshness**: A diagnostic timestamp sensor and `forecast_date` / `last_successful_update` attributes
- **Dashboard Example**: Built-in cards for trends, forecasts, active plants, and recommendations
- **In-Season Plant Details**: Per-pollen-type list of plants currently in season, with family and cross-reaction info
- **Per-Plant Sensors**: Optional index sensors for each plant the API reports for your region (oak, birch, ragweed, ...) — disabled by default, enable the ones you care about from the device page
- **Health Recommendations**: Get health advice based on current pollen levels
- **Automatic Updates**: Data refreshes every 6 hours (configurable 1–24h via integration options)
- **Multiple Locations**: Add the integration once per location, each with its own name
- **Reconfigurable**: Update the name, API key, or location without removing the integration
- **Re-authentication**: If your API key is revoked or rotated, Home Assistant prompts you to enter a new one — no manual cleanup
- **Diagnostics**: Download redacted diagnostics from Home Assistant for troubleshooting

## Sensors Created

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.google_pollen_grass_pollen_index` | Grass pollen index | UPI (0-5) |
| `sensor.google_pollen_grass_pollen_level` | Grass pollen category | Enum |
| `sensor.google_pollen_tree_pollen_index` | Tree pollen index | UPI (0-5) |
| `sensor.google_pollen_tree_pollen_level` | Tree pollen category | Enum |
| `sensor.google_pollen_weed_pollen_index` | Weed pollen index | UPI (0-5) |
| `sensor.google_pollen_weed_pollen_level` | Weed pollen category | Enum |

The level sensors are enum sensors with the states `None`, `Very Low`, `Low`, `Moderate`, `High`, and `Very High`.

### Sensor Attributes

Current index sensors include additional attributes:
- `forecast_date`: Date of the current forecast record, in UTC; `null` if no current record exists
- `last_successful_update`: UTC timestamp of the last successful API refresh
- `in_season`: Whether the pollen type is currently in season
- `health_recommendations`: List of health tips based on pollen levels
- `index_description`: Description of what the current index level means
- `color`: Index color as a `#RRGGBB` hex string (usable directly in Lovelace conditions)
- `in_season_plants`: List of plants currently in season for this pollen type, each with `code`, `display_name`, `family`, `season`, and `cross_reaction`
- `forecast`: Array of upcoming returned dates, with `datetime`, `date`, `index`, `category`, and `in_season`. Missing readings remain `null`. These are pollen-specific attributes; they do not make the entity a Home Assistant weather entity.

### Per-Plant Sensors

In addition to the six sensors above, one index sensor is created for every plant the API reports for your region (e.g. `sensor.google_pollen_oak_pollen_index`). These are **disabled by default** to avoid clutter — open the Google Pollen device page in Home Assistant and enable the plants you care about. Each plant sensor exposes `in_season`, `category`, `family`, `season`, and `cross_reaction` attributes where the API provides them, plus the same freshness and future `forecast` attributes as the main index sensors. Plants reported only on future dates also receive optional entities.

### Optional Forecast Sensors

Enable these from the Google Pollen device page when needed:

| Entity ID (default location name) | Meaning |
| --- | --- |
| `sensor.google_pollen_grass_pollen_tomorrow_index` | Grass UPI for the next UTC date |
| `sensor.google_pollen_grass_pollen_upcoming_peak_index` | Highest known grass UPI on future returned dates |

Equivalent tomorrow and peak sensors are available for tree and weed pollen. They are disabled by default and use the existing cached forecast, so enabling them adds no API calls. Forecast values are not declared as measurements for long-term statistics.

Peak sensors expose `peak_date` (earliest date in a tie), `forecast_days`, and `forecast_complete`. The peak is computed from **known readings**, excluding today. `forecast_complete` means every returned future date has a known reading; it does not guarantee four future days were returned. If every future reading is unknown, the peak is unknown too.

`sensor.google_pollen_last_successful_update` is an enabled diagnostic timestamp sensor. It remains readable during API outages so you can inspect data freshness.

### Reading Semantics

An explicit UPI is reported as provided (0–5), with a stable category derived from its numeric value. A reported pollen type or plant with no index is zero only when the API explicitly reports `inSeason: false`. Missing readings for in-season plants, missing season information, and absent species remain **unknown**. A failed refresh makes current pollen sensors **unavailable**; it does not advance the last-successful timestamp.

Google represents forecast dates in UTC. “Today” and “tomorrow” in this integration follow UTC, including locations in other time zones. At midnight UTC, sensors select the next cached dated record. If no matching record exists, the state becomes unknown rather than continuing to display yesterday's reading. Polling still follows the configured interval.

## Prerequisites

- Home Assistant **2025.4.4** or newer (the minimum version is tested in CI)

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
4. Enter a name for the location (used as the device name — defaults to "Google Pollen")
5. Enter your Google API key
6. Enter the latitude and longitude for the location you want to monitor (defaults to your Home Assistant location)

To monitor several locations, add the integration once per location and give each a distinct name.

To change the name, API key, or location later, use **Reconfigure** from the integration's overflow menu — all fields are editable, and the integration will reject collisions with another configured location. To change the update interval, use **Configure** to open the options flow. If your API key stops working, Home Assistant will surface a re-authentication prompt automatically.

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
            {{ (state_attr('sensor.google_pollen_grass_pollen_index', 'health_recommendations') or [''])[0] }}
```

### Complete forecast dashboard

Copy [examples/pollen-dashboard.yaml](examples/pollen-dashboard.yaml) into a **Manual** dashboard card. It uses only built-in entities, history graph, and Markdown cards. It shows current levels, recent readings, upcoming forecasts with direction arrows, in-season plants, recommendations, and the last successful refresh. Replace the entity IDs throughout if you named the location differently. Unknown forecasts are displayed as a dash.

### Alert on tomorrow's forecast

Enable the optional tomorrow sensor first:

```yaml
automation:
  - alias: "High grass pollen tomorrow"
    trigger:
      - platform: numeric_state
        entity_id: sensor.google_pollen_grass_pollen_tomorrow_index
        above: 3
    action:
      - service: notify.mobile_app
        data:
          title: "High pollen tomorrow"
          message: >-
            Grass UPI is forecast to reach
            {{ states('sensor.google_pollen_grass_pollen_tomorrow_index') }} on
            {{ state_attr('sensor.google_pollen_grass_pollen_tomorrow_index', 'forecast_date') }} (UTC).
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

### Setup and API errors

- **Invalid API key**: Replace an invalid, expired, or revoked key.
- **Service disabled**: Enable the Pollen API in the Google Cloud project.
- **Access denied**: Check project permissions, billing, and API key restrictions. If using IP restrictions, allow your Home Assistant server's public IP.
- **Quota exhausted**: Check Google Cloud quotas and wait before retrying. Consider a longer polling interval when monitoring several locations.
- **Invalid location / no data**: Check coordinate ranges and coverage, then retry if coverage is supported.
- **Cannot connect / temporarily unavailable**: Check connectivity or wait for the provider to recover.
- If the key was working previously and was rotated or revoked, Home Assistant will show a re-authentication prompt — enter the new key there instead of removing and re-adding the integration

Only invalid credentials initiate reauthentication. Disabled service, quota, permission, and temporary failures do not prompt you to rotate an otherwise valid key.

### Sensors show "Unknown"
- A reading or current UTC date may be absent from the response, including an in-season plant with no index
- Pollen data may not be available for your location
- Check the [coverage map](https://developers.google.com/maps/documentation/pollen/coverage) to verify support

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

Run the suite in Python 3.13 with `pip install -r requirements_test.txt` and `pytest tests/ -q`. To verify the minimum Home Assistant release, use a separate environment with `pip install -r requirements_test_min.txt` and the same pytest command. CI also runs the current test harness on Python 3.13 and 3.14, alongside Ruff, HACS, and Hassfest validation.

## Disclaimer

This integration is not affiliated with or endorsed by Google. All product names, trademarks, and registered trademarks are property of their respective owners.
