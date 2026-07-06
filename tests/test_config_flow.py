from unittest.mock import MagicMock

from aiotransperth import InvalidStopError
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.transperth.const import (
    CONF_DESTINATIONS,
    CONF_LINE,
    CONF_ROUTES,
    CONF_STATION,
    CONF_STOP_CODE,
    CONF_WALK_MINUTES,
    DOMAIN,
)


async def _start_bus_flow(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "bus"}
    )


async def test_bus_flow_happy_path(hass: HomeAssistant, mock_client: MagicMock) -> None:
    result = await _start_bus_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "bus"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "12627"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bus_tracking"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ROUTES: ["414"], CONF_WALK_MINUTES: 5}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Main St After Royal St (12627)"
    assert result["data"][CONF_STOP_CODE] == "12627"
    assert result["options"] == {CONF_ROUTES: ["414"], CONF_WALK_MINUTES: 5}


async def test_bus_flow_invalid_stop(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.get_stop_timetable.side_effect = InvalidStopError("nope")
    result = await _start_bus_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "00000"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_stop"}


async def test_bus_flow_duplicate_aborts(
    hass: HomeAssistant, mock_client: MagicMock, bus_entry: MockConfigEntry
) -> None:
    bus_entry.add_to_hass(hass)
    result = await _start_bus_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "12627"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def _start_train_flow(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "train"}
    )


async def test_train_flow_happy_path(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    result = await _start_train_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "train"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "Midland Line", CONF_STATION: "Maylands Stn"},
    )
    assert result["step_id"] == "train_tracking"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DESTINATIONS: ["Perth"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maylands Stn (Midland Line)"
    assert result["options"] == {CONF_DESTINATIONS: ["Perth"]}


async def test_train_flow_no_trains_running(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    mock_client.get_train_departures.return_value = ()
    result = await _start_train_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "Midland Line", CONF_STATION: "Maylands Stn"},
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "train"
    assert result["errors"] == {"base": "no_trains_running"}


async def test_train_flow_duplicate_aborts(
    hass: HomeAssistant, mock_client: MagicMock, train_entry: MockConfigEntry
) -> None:
    train_entry.add_to_hass(hass)
    result = await _start_train_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LINE: "Midland Line", CONF_STATION: "Maylands Stn"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
