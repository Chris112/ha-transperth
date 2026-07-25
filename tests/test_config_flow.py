from unittest.mock import MagicMock

from aiotransperth import InvalidStopError, TransperthError
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.transperth.const import (
    CONF_LINE,
    CONF_ROUTES,
    CONF_STATION,
    CONF_STOP_CODE,
    CONF_TO_STATION,
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


async def _pick_line(hass: HomeAssistant, line: str = "Midland Line"):
    result = await _start_train_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "train"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LINE: line}
    )


async def test_train_journey_flow_happy_path(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    result = await _pick_line(hass)
    assert result["step_id"] == "train_journey"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: "Maylands Stn", CONF_TO_STATION: "Perth Stn"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maylands → Perth"
    assert result["data"][CONF_TO_STATION] == "Perth Stn"
    assert result["options"] == {CONF_WALK_MINUTES: 0}


async def test_train_flow_without_destination_tracks_the_station(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    result = await _pick_line(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION: "Maylands Stn"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Maylands Stn (Midland Line)"
    assert CONF_TO_STATION not in result["data"]


async def test_train_flow_survives_an_unreachable_api(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    # Line and station lists come from the offline ordering table, so adding a
    # station works even at 3am with the catalog endpoints down — the old flow
    # aborted with cannot_connect, or refused when nothing was running.
    mock_client.get_train_lines.side_effect = TransperthError("down")
    mock_client.get_train_stations.side_effect = TransperthError("down")
    mock_client.get_train_departures.return_value = ()

    result = await _pick_line(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION: "Maylands Stn"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    mock_client.get_train_lines.assert_not_called()
    mock_client.get_train_stations.assert_not_called()


async def test_train_flow_rejects_travelling_to_where_you_board(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    result = await _pick_line(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: "Maylands Stn", CONF_TO_STATION: "Maylands Stn"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_TO_STATION: "same_station"}


async def test_opposite_journeys_are_separate_entries(
    hass: HomeAssistant, mock_client: MagicMock, journey_entry: MockConfigEntry
) -> None:
    journey_entry.add_to_hass(hass)
    result = await _pick_line(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: "Perth Stn", CONF_TO_STATION: "Maylands Stn"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Perth → Maylands"


async def test_train_flow_aborts_without_line_data(
    hass: HomeAssistant, mock_client: MagicMock, monkeypatch
) -> None:
    monkeypatch.setattr("aiotransperth.lines.LINE_STATIONS", {})
    result = await _start_train_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_line_data"


async def test_train_flow_duplicate_aborts(
    hass: HomeAssistant, mock_client: MagicMock, journey_entry: MockConfigEntry
) -> None:
    journey_entry.add_to_hass(hass)
    result = await _pick_line(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_STATION: "Maylands Stn", CONF_TO_STATION: "Perth Stn"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
