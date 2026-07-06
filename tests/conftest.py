"""Shared fixtures. The aiotransperth client is always patched — no network."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiotransperth import (
    PERTH_TZ,
    BusDeparture,
    LiveStatus,
    Stop,
    StopTimetable,
    TrainDeparture,
    TrainStation,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.transperth.const import (
    CONF_DESTINATIONS,
    CONF_LINE,
    CONF_MODE,
    CONF_ROUTES,
    CONF_STATION,
    CONF_STOP_CODE,
    CONF_STOP_NAME,
    CONF_WALK_MINUTES,
    DOMAIN,
    MODE_BUS,
    MODE_TRAIN,
)

NOT_LIVE = LiveStatus(is_live=False, status_code=None, description="")
STOP = Stop(code="12627", name="Main St After Royal St", zone="1")


def _dt(hour: int, minute: int) -> datetime:
    return datetime(2026, 7, 7, hour, minute, tzinfo=PERTH_TZ)


BUS_DEPARTURES = (
    BusDeparture(
        route="414",
        headsign="Glendalough Stn",
        destination="Glendalough Stn",
        origin="Curtin University",
        scheduled=_dt(8, 10),
        estimated=_dt(8, 12),
        live=LiveStatus(is_live=True, status_code=2, description="2 min delay"),
        trip_uid="t1",
    ),
    BusDeparture(
        route="402",
        headsign="Perth Busport",
        destination="Perth Busport",
        origin="Stirling Stn",
        scheduled=_dt(8, 15),
        estimated=None,
        live=NOT_LIVE,
        trip_uid="t2",
    ),
    BusDeparture(
        route="414",
        headsign="Glendalough Stn",
        destination="Glendalough Stn",
        origin="Curtin University",
        scheduled=_dt(8, 25),
        estimated=None,
        live=NOT_LIVE,
        trip_uid="t3",
    ),
)
TIMETABLE = StopTimetable(stop=STOP, departures=BUS_DEPARTURES)

TRAINS = (
    TrainDeparture(
        line="Midland Line",
        destination="Perth",
        platform="1",
        scheduled=_dt(8, 10),
        estimated=_dt(8, 10),
        live=LiveStatus(is_live=True, status_code=1, description="On Time"),
        cars=4,
        pattern="",
        trip_id=1,
    ),
    TrainDeparture(
        line="Midland Line",
        destination="Midland",
        platform="2",
        scheduled=_dt(8, 14),
        estimated=_dt(8, 14),
        live=LiveStatus(is_live=True, status_code=1, description="On Time"),
        cars=6,
        pattern="",
        trip_id=2,
    ),
)
LINES = ("Fremantle Line", "Midland Line")
STATIONS = (
    TrainStation(id="130", name="Maylands Stn"),
    TrainStation(id="1", name="Perth Stn"),
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components in tests."""


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    client = MagicMock()
    client.get_stop_timetable = AsyncMock(return_value=TIMETABLE)
    client.validate_stop = AsyncMock(return_value=STOP)
    client.get_train_departures = AsyncMock(return_value=TRAINS)
    client.get_train_lines = AsyncMock(return_value=LINES)
    client.get_train_stations = AsyncMock(return_value=STATIONS)
    with (
        patch(
            "custom_components.transperth.coordinator.TransperthClient",
            return_value=client,
        ),
        patch(
            "custom_components.transperth.config_flow.TransperthClient",
            return_value=client,
        ),
        patch(
            "custom_components.transperth.services.TransperthClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def bus_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="bus_12627",
        title="Main St After Royal St (12627)",
        data={
            CONF_MODE: MODE_BUS,
            CONF_STOP_CODE: "12627",
            CONF_STOP_NAME: "Main St After Royal St",
        },
        options={CONF_ROUTES: ["414"], CONF_WALK_MINUTES: 5},
    )


@pytest.fixture
def train_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="train_midland_line_maylands_stn",
        title="Maylands Stn (Midland Line)",
        data={
            CONF_MODE: MODE_TRAIN,
            CONF_LINE: "Midland Line",
            CONF_STATION: "Maylands Stn",
        },
        options={CONF_DESTINATIONS: ["Perth"]},
    )
