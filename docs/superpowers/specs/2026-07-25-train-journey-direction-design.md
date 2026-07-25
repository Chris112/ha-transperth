# Direction-aware train entries

**Date:** 2026-07-25
**Status:** implemented, pending generation of the ordering table

Two rules below were corrected during implementation, both marked **[revised]**:
lines are not all city-radial, and a terminus that isn't on the line means the
service ends its run at the CBD rather than continuing past it.

## Problem

A train entry currently models a *station*, and its `Next departure` sensor is
`departures[0]` — the next train through that station in **either** direction.
At a through-station this is close to useless: at Edgewater roughly half the
trains run north to Yanchep, away from the city, so the sensor answers a
question nobody asks. Humans think in journeys ("when's my train to Perth"),
not in station-level departure sets.

The per-destination sensors (`Next train to Perth`) already read naturally, but
they are keyed on the literal `Destination` string, so a Clarkson or Butler
short-working becomes its own entity instead of counting as "the next
northbound train".

## What the upstream data actually provides

Verified against the live API on 2026-07-25, not assumed:

- `GetStationLiveStatusAsync` returns a flat `StatusDetailList`. The only
  direction signals per entry are `Destination` (that service's terminus) and
  `Platform`. **There is no direction field.**
- The station dropdown on `/Timetables/Live-Train-Times` is one flat
  alphabetical list across all lines. Station IDs encode nothing useful —
  Edgewater 98, Joondalup 106, Butler 175, Alkimos 194.
- The **per-line** page (`/Timetables/Live-Train-Times/{line}`) lists exactly
  the stations on that line — 16 for Yanchep Line. Still alphabetical, but
  line membership is authoritative and live.
- **Station order is derivable.** A `TripId` recurs at every station it calls
  at, with increasing `TripStopSchedule`. Confirmed: trip `7131983` (dest
  Perth) calls Joondalup 15:20 → Edgewater 15:23 → Warwick 15:33, and trip
  `6668499` (dest Yanchep) runs the exact reverse.

Nothing in this design requires hand-authored geography.

## Design

### Entry shape

```
data    = { mode: "train", line, station, to_station? }   # to_station optional
options = { walk_minutes }                                # only when to_station is set
```

`to_station` is optional from day one. This is the only decision here that is
expensive to reverse, so it is made permissive now: every other element of this
design is additive and can land later without a migration.

**`to_station` set** — the commute case. One direction, one poll:

```
Device: Edgewater Stn → Perth Stn
  Next train        15:07    city-bound only
  Departures        [board, city-bound only]
  Time to leave     off
  Status
```

**`to_station` blank** — the departure-board case, and what existing entries
become:

```
Device: Edgewater Stn
  Next train towards Perth Underground   15:07
  Next train towards Yanchep             15:22
  Departures                             [board, both directions]
  Status
```

Both modes share one coordinator and one request per poll. The branch is in
entity setup only.

### Direction and reachability

With `order = LINE_STATIONS[line]`, indexed from the city end outward:

```
i_a = order.index(station)
i_b = order.index(to_station)
i_t = order.index(terminus)          # terminus of the departing service

direction = sign(i_b - i_a)
serves    = sign(i_t - i_a) == direction and abs(i_t - i_a) >= abs(i_b - i_a)
```

A service counts when it runs the right way **and** its terminus is at or
beyond the target. This is what makes short-workings correct rather than
guessed: a Clarkson-terminating train serves Edgewater→Joondalup but not
Edgewater→Butler.

**[revised] Lines are not all city-radial.** The generator's assertion caught
this: the Airport Line runs High Wycombe → CBD → Claremont, so the city sits
mid-route. Nothing may assume index 0 is the city. `direction` and `serves`
are computed from relative positions and are orientation-independent; index 0
is merely the end nearer the CBD, which is cosmetic.

**[revised] A terminus that isn't on the line ends its run at the CBD.** Two
cases collapse into one rule. A bare `Perth` on a northern line names no
station there (those lines serve Perth Underground). A `Mandurah` on the
Airport Line is another line entirely. Either way the service stops being
useful to this line at the centre — it terminates in the city or diverges
there — so `i_t` becomes the line's CBD index.

The original rule treated such a service as continuing *past* the far end,
which is wrong on a CBD-spanning line: a Mandurah-bound service at an eastern
Airport Line station does not carry you onward to Claremont. Writing the test
for that case is what exposed it. Standing at the CBD interchange the rule
degenerates correctly to serving nothing, with no special case needed.

**Name normalisation.** Departure `Destination` values are bare — `Perth`,
not `Perth Stn` — while the catalog always carries the suffix. All comparisons
go through a normaliser that strips `Stn`/`Station` and casefolds.

**Terminus stations.** When `station` is at either end of `order`, only one
direction exists and only one direction sensor is created.

### Library work (`aiotransperth`)

This change spans both repos. The integration cannot ship until the library is
released, because `manifest.json` pins `aiotransperth==0.1.0`.

1. `get_train_stations(line: str | None = None)` — line-filtered via the
   per-line page. Catalog-wide behaviour is preserved when `line` is `None`.
2. `LINE_STATIONS` — generated ordered table, committed as static data.
3. `scripts/generate_line_order.py` — derives that table by querying every
   station on each line, grouping calls by `TripId`, and sorting by scheduled
   time. Must be run during service hours; stations with no trips in the
   window are reported rather than silently dropped. Requests are spaced,
   since Transperth's rate limit is sticky.

   **[revised]** The line must contain a CBD station somewhere — asserted at
   generation time, since the CBD anchors the off-line-terminus rule — but not
   necessarily at an end. Index 0 is pointed at whichever end is nearer it,
   purely for readability.
4. `serves_journey(line, station, terminus, target)` — the rule above.

Direction logic lives in the library because it is Transperth network
knowledge, reusable and testable independently of Home Assistant. The
integration stays HA plumbing, per its existing architecture.

### Config flow

Two steps, not one as first sketched: the station list depends on the chosen
line, and Home Assistant forms can't have dependent dropdowns. So it is line →
(station, optional destination), the second step listing that line's stations
in route order.

Both steps are **offline**, reading the ordering table rather than the API.
That deletes the `no_trains_running` error and the `cannot_connect` abort,
which between them could block setup entirely at night or during an outage. An
empty table aborts with `no_line_data` rather than showing a bare dropdown.

### Entities

Timestamp sensors keep the existing `dep.estimated or dep.scheduled` rule.
`Time to leave` extends to trains, reusing `binary_sensor.py`'s
`async_track_point_in_time` flip; it is created only when `to_station` is set,
since a walk time is meaningless without a direction.

Removed: the merged `Next departure` sensor, and the per-destination sensors
driven by the `destinations` option. Both are redundant — blank-`to_station`
mode covers "both directions", and the board lists every service regardless.

### Migration

Entry `data` is forward-compatible: existing train entries lack `to_station`
and become blank-mode entries. Bump `VERSION` to 2 and have
`async_migrate_entry` drop the now-unused `destinations` option. Entity IDs
for the removed sensors change; this is called out in the README.

## Out of scope

**Buses keep stop + routes.** The API could support stop→stop journeys
(`get_trip_stops` already exists), but bus direction comes from route patterns
rather than line order, and reachability would need a trip stop list per
departure — more requests against a sticky rate limit. It is a differently
shaped problem and doing it by analogy to trains would be worse than doing it
deliberately later. The resulting asymmetry between the bus and train halves
is a real documentation cost, accepted knowingly.

## Testing

Extend `tests/conftest.py` canned data rather than building new mocks:

- an ordered `LINE_STATIONS` fixture for a synthetic line
- train departures including a short-working terminus and a through-routed
  terminus absent from the line

Cases: direction selection both ways; short-working included when it reaches
the target and excluded when it does not; through-routed terminus treated as
city-bound; origin at a line terminus yielding one direction sensor; blank
`to_station` yielding both; `Time to leave` created only with `to_station`;
migration dropping `destinations` and preserving the entry.
