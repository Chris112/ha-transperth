# Transperth for Home Assistant

Live Perth (Western Australia) bus and train departures as native Home
Assistant entities — **with realtime delay data**. Add a bus stop or train
station through the UI, get auto-updating sensors and a delay-aware
"time to leave" alert. Zero YAML.

Built on [`aiotransperth`](https://github.com/Chris112/aiotransperth).
Successor to the PyScript-based
[transperth_bus_times](https://github.com/Chris112/transperth_bus_times).

## Install

1. In HACS: **⋮ → Custom repositories** → add
   `https://github.com/Chris112/ha-transperth` as an **Integration**.
2. Install **Transperth**, restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Transperth.**

## Setup

Pick **Bus stop** or **Train station**:

- **Bus stop** — enter the stop code (the number on the stop sign). The stop
  is validated live and its name confirmed. Then optionally tick routes to
  track and set your walk time to the stop.
- **Train station** — pick the line, then the station you board at and,
  optionally, **where you travel to**. Both dropdowns are offline and in route
  order, so setup works at 3am with nothing running.

### Trains are journeys, not stations

A station like Edgewater has trains going both ways, and "the next train" in
either direction is rarely what you want. So a train entry is a *journey leg*:

```
Edgewater Stn → Perth Stn      only city-bound trains
Perth Stn → Edgewater Stn      the trip home, as a second entry
```

Only services that actually reach your destination count. A Clarkson
short-working shows up if you're going to Joondalup and is filtered out if
you're going to Butler.

Leave **Travelling to** empty and you get a plain station entry instead, with
one sensor per direction — useful for a departure-board dashboard.

Change your walk time any time via **Configure**. Which way you travel is part
of the entry's identity, so add a second entry for the return trip.

## Entities

Each configured place becomes a device with:

| Entity | Type | Notes |
|---|---|---|
| Next train | timestamp sensor | Journey entries. Dashboards render it as "in 7 minutes" natively. Attributes: destination, platform, cars, `delay_minutes`, `is_live`. |
| Next train towards *terminus* | timestamp sensor | Station entries — one per direction. |
| Next departure | timestamp sensor | Bus entries. |
| Departures | sensor | Next 5 departures as a list attribute for board cards; filtered to your direction on a journey entry. |
| Next *route* | timestamp sensor | One per tracked bus route. |
| Time to leave | binary sensor | On when `now ≥ departure − walk time`, using the **live** estimate — a train running 3 minutes late delays the nudge by 3 minutes. Flips punctually, not on the next poll. Bus entries get one per tracked route; train entries get one once they name a destination. |
| Status | diagnostic sensor | Last successful update; `rate_limited` attribute. |

Timestamps use the live estimate when a vehicle is tracked, otherwise the
schedule. Trains are always live; buses light up when the vehicle is on the
road (typically the imminent departure).

## Example automation

```yaml
automation:
  - alias: "Leave for the 414"
    triggers:
      - trigger: state
        entity_id: binary_sensor.main_st_after_royal_st_12627_time_to_leave_for_the_414
        to: "on"
    conditions:
      - condition: time
        after: "07:00:00"
        before: "09:00:00"
        weekday: [mon, tue, wed, thu, fri]
    actions:
      - action: notify.mobile_app_your_phone
        data:
          title: "Leave now"
          message: >
            The 414 departs at
            {{ states('sensor.main_st_after_royal_st_12627_next_414') | as_timestamp | timestamp_custom('%H:%M') }}.
```

## Services (power users)

Ad-hoc queries for places you haven't configured — all return response data:

- `transperth.get_bus_departures` — `stop_code`, optional `at`
- `transperth.get_bus_schedule` — `stop_code`, `bus_number`, optional `at`
- `transperth.get_bus_stops` — `bus_number`, optional `at` (full stop list of the next trip)
- `transperth.get_train_departures` — `line`, `station`

`at` accepts `HH:MM` (next occurrence — rolls to tomorrow if past) or
`YYYY-MM-DD HH:MM` (exact). Failures raise proper HA errors, visible in
automation traces.

## Notes

- Polling: buses every 2 minutes, trains every minute — one request per entry.
  Two entries at the same station poll it separately, so a there-and-back
  commute costs two requests a minute.
- On HTTP 429 the Status entity's `rate_limited` attribute goes true and
  polling backs off, doubling from the entry's own interval up to 15 minutes,
  resetting after a success. Transperth sends no `Retry-After` header and its
  cooldown is sticky and shared with their public website, so polling straight
  through a rate limit only prolongs it.
- Data comes from Transperth's unofficial website APIs (there is no official
  realtime feed). It can break without notice; entities go unavailable and
  recover on their own.
- Every time the integration handles is `Australia/Perth`-aware regardless of
  your server's timezone, so the departure-board `HH:MM` strings are always
  Perth local time — which is what you want, but will differ from the rest of
  your dashboard if Home Assistant is set to another zone.

## Upgrading from 0.1.x

Existing train entries keep working and become station entries, reporting both
directions. Their per-destination sensors are replaced by per-direction ones,
so `sensor.…_next_departure` and `sensor.…_next_train_to_perth` give way to
`sensor.…_next_train_towards_perth` — update any automations referencing them.

To get the journey behaviour, add a new entry and set **Travelling to**.

## Removal

Delete the integration entries under **Settings → Devices & Services**, then
remove the repository from HACS.

## License

MIT
