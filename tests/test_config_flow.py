"""Tests for the Google Pollen config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.google_pollen.api import (
    GooglePollenApiAuthError,
    GooglePollenApiConnectionError,
)
from custom_components.google_pollen.const import (
    CONF_API_KEY,
    CONF_UPDATE_INTERVAL_HOURS,
    DOMAIN,
)

USER_INPUT = {
    CONF_API_KEY: "test-key",
    CONF_LATITUDE: 37.7749,
    CONF_LONGITUDE: -122.4194,
}


async def test_user_flow_success(hass: HomeAssistant, mock_api_get_forecast) -> None:
    """Happy path: valid key + location creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Invalid API key surfaces the invalid_auth error."""
    with patch(
        "custom_components.google_pollen.config_flow.GooglePollenApiClient.async_get_forecast",
        new=AsyncMock(side_effect=GooglePollenApiAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Network errors surface the cannot_connect error."""
    with patch(
        "custom_components.google_pollen.config_flow.GooglePollenApiClient.async_get_forecast",
        new=AsyncMock(side_effect=GooglePollenApiConnectionError("dns")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_preserves_input_on_error(hass: HomeAssistant) -> None:
    """After an error, the form re-renders with the user's typed values."""
    with patch(
        "custom_components.google_pollen.config_flow.GooglePollenApiClient.async_get_forecast",
        new=AsyncMock(side_effect=GooglePollenApiAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

    schema_defaults = {
        key.schema: key.default() for key in result["data_schema"].schema
    }
    assert schema_defaults[CONF_LATITUDE] == USER_INPUT[CONF_LATITUDE]
    assert schema_defaults[CONF_LONGITUDE] == USER_INPUT[CONF_LONGITUDE]


async def test_already_configured(hass: HomeAssistant, mock_api_get_forecast) -> None:
    """Same lat/long aborts as already_configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow(hass: HomeAssistant, mock_api_get_forecast) -> None:
    """Reconfigure updates the entry's data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = {**USER_INPUT, CONF_API_KEY: "new-key"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_KEY] == "new-key"


async def test_reconfigure_changes_location(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """Reconfigure can change lat/long and the unique_id is updated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    new_input = {**USER_INPUT, CONF_LATITUDE: 40.0, CONF_LONGITUDE: -74.0}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_LATITUDE] == 40.0
    assert entry.data[CONF_LONGITUDE] == -74.0
    assert entry.unique_id == "40.0_-74.0"


async def test_reconfigure_collision_aborts(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """Reconfiguring to a location owned by another entry aborts."""
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id="40.0_-74.0",
        data={**USER_INPUT, CONF_LATITUDE: 40.0, CONF_LONGITUDE: -74.0},
    )
    other.add_to_hass(hass)

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    new_input = {**USER_INPUT, CONF_LATITUDE: 40.0, CONF_LONGITUDE: -74.0}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], new_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Original entry left untouched.
    assert entry.data[CONF_LATITUDE] == USER_INPUT[CONF_LATITUDE]


async def test_reauth_flow_success(hass: HomeAssistant, mock_api_get_forecast) -> None:
    """Reauth replaces the API key on the existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "rotated-key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "rotated-key"
    # Lat/long are preserved.
    assert entry.data[CONF_LATITUDE] == USER_INPUT[CONF_LATITUDE]


async def test_reauth_flow_invalid_key(hass: HomeAssistant) -> None:
    """A bad replacement key keeps the form open with invalid_auth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.google_pollen.config_flow.GooglePollenApiClient.async_get_forecast",
        new=AsyncMock(side_effect=GooglePollenApiAuthError("nope")),
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "still-bad"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    # Original key is untouched until the user gives a valid one.
    assert entry.data[CONF_API_KEY] == USER_INPUT[CONF_API_KEY]


async def test_options_flow(hass: HomeAssistant, mock_api_get_forecast) -> None:
    """Options flow sets the update interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL_HOURS: 12}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_UPDATE_INTERVAL_HOURS: 12}
