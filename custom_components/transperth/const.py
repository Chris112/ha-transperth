"""Constants for the Transperth integration."""

import logging
from datetime import timedelta

DOMAIN = "transperth"
LOGGER = logging.getLogger(__package__)

CONF_MODE = "mode"
MODE_BUS = "bus"
MODE_TRAIN = "train"

CONF_STOP_CODE = "stop_code"
CONF_STOP_NAME = "stop_name"
CONF_LINE = "line"
CONF_STATION = "station"

CONF_ROUTES = "routes"
CONF_DESTINATIONS = "destinations"
CONF_WALK_MINUTES = "walk_minutes"

BUS_SCAN_INTERVAL = timedelta(seconds=120)
TRAIN_SCAN_INTERVAL = timedelta(seconds=60)
BOARD_SIZE = 5
