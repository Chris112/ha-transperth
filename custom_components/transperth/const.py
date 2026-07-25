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
CONF_TO_STATION = "to_station"

CONF_ROUTES = "routes"
CONF_WALK_MINUTES = "walk_minutes"

# Dropped in config entry version 2, when per-destination train sensors gave
# way to direction-filtered ones. Kept only so migration can remove it.
CONF_DESTINATIONS = "destinations"

BUS_SCAN_INTERVAL = timedelta(seconds=120)
TRAIN_SCAN_INTERVAL = timedelta(seconds=60)
BOARD_SIZE = 5

# Transperth's 429 carries no Retry-After header, and its cooldown is sticky
# and shared with their public website — polling straight through one only
# feeds it. Back off blind, doubling from the entry's own interval.
RATE_LIMIT_BACKOFF_MAX = timedelta(minutes=15)
