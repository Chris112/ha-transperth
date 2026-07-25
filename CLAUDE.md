# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration (HACS) exposing live Perth bus/train departures
as entities. All API access goes through the `aiotransperth` library — this repo
contains no HTTP code, only HA plumbing.

## Commands

Uses the local `.venv` (Python 3.13). `aiotransperth` is installed editable from
the sibling checkout at `../aiotransperth` (CI installs it from the git URL instead).

```bash
source .venv/bin/activate
pytest -q                                  # all tests (fast, fully mocked)
pytest tests/test_sensor.py -q             # one file
pytest tests/test_config_flow.py -k bus    # filter by keyword
ruff check .                               # lint (also run: ruff format)
```

CI (`.github/workflows/ci.yml`) additionally runs hassfest and HACS validation —
`manifest.json`, `services.yaml`, `strings.json`/`translations/en.json`, and
`hacs.json` must stay consistent.

## Architecture

Data flow: `aiotransperth.TransperthClient` → coordinator → entities.

- **`api.py`**: `async_shared_client(hass)` — the ONE `TransperthClient` for the
  whole instance, shared by coordinators, config/options flows, and services.
  Never construct `TransperthClient` elsewhere: fresh clients re-scrape CSRF
  tokens and refetch the train catalog, and Transperth's rate limit is sticky.
  `async_train_departures(hass, line, station)` wraps that call in a
  per-station cache just under the poll interval, so several journeys boarding
  at one station cost one request — `TrainCoordinator` must go through it
  rather than calling the client directly. Failures are evicted, never served.
- **One config entry = one place or one journey leg**, distinguished by
  `data[CONF_MODE]` (`bus`/`train`). Entry `data` is identity (stop code, or
  line + station + optional `to_station`, immutable); entry `options` is
  preferences (routes, walk minutes). Options changes trigger a full entry
  reload (`__init__.py` update listener).
- **Train direction comes from `to_station`.** With one set, the entry is a
  journey (Edgewater → Perth) and every sensor is filtered to services that
  actually reach the target — `TrainCoordinator.departures_towards`, which
  defers to `aiotransperth.serves_journey`. Without one, the entry reports
  both ways with a sensor per line end. `journey.py` is the single place that
  decides which mode an entry is in; don't re-derive it from `data`.
  Direction knowledge (station order per line) lives in the library, not here.
- **`coordinator.py`**: `BusCoordinator` (2 min poll) and `TrainCoordinator`
  (1 min poll) share `_BaseCoordinator`, which owns the client and the
  `rate_limited`/`last_success` bookkeeping surfaced by the diagnostic
  `StatusSensor`. `TransperthCoordinator` is the union type alias, stored in
  `entry.runtime_data` (typed via `TransperthConfigEntry` in `__init__.py`).
- **`entity.py`**: `TransperthEntity` base — one device per entry, unique IDs are
  `{entry_id}_{key}`. All entities use `_attr_has_entity_name`.
- **`sensor.py`**: timestamp sensors prefer `dep.estimated or dep.scheduled`
  (live estimate falls back to schedule) — keep that pattern everywhere departure
  times are shown. Per-route/per-destination sensors subclass the "next departure"
  sensors and only override `_departure()`.
- **`binary_sensor.py`**: bus-only "time to leave". Flips punctually (not on the
  next poll) by scheduling `async_track_point_in_time` at the threshold on every
  coordinator update; timer is cancelled/rescheduled on update and removal.
- **`services.py`**: four ad-hoc query services registered in `async_setup`
  (available without any entry), all `SupportsResponse.ONLY`. Error mapping
  convention: user-input problems → `ServiceValidationError`, upstream failures →
  `HomeAssistantError`.
- **`config_flow.py`**: menu → bus (validate stop code live, then pick routes
  from what's observed) or train (pick line, then station + optional
  destination). The train branch makes **no network calls at all** — its
  dropdowns come from the library's offline ordering table in route order, so
  setup can't fail at night or when the API is down. Bus options flow
  re-fetches live data and unions it with the saved selection so existing
  choices survive quiet periods.

All times are `Australia/Perth`-aware (`PERTH_TZ` from aiotransperth).

## Tests

`tests/conftest.py` patches `TransperthClient` at its single construction
point (`api.py`) via the `mock_client` fixture — tests never hit the network. Canned data (`TIMETABLE`, `TRAINS`,
fixtures `bus_entry`/`train_entry`) lives there; extend it rather than building
new mocks. Uses `pytest-homeassistant-custom-component` with `asyncio_mode = auto`.

## Conventions

- `quality_scale.yaml` tracks HA integration quality scale rules — update it when
  adding/changing features that touch a rule.
- New user-facing strings go in both `strings.json` and `translations/en.json`.
- New services need entries in `services.yaml` and `strings.json`.
