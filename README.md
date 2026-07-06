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
- **Train station** — pick the line and station from dropdowns, then tick the
  destination(s) you care about from what's currently running (e.g. "Perth"
  for city-bound). No typing, no guessing. If no trains are running, configure
  again while services are active.

Change tracked routes/destinations or walk time any time via **Configure** on
the integration entry.

## Entities

Each configured place becomes a device with:

| Entity | Type | Notes |
|---|---|---|
| Next departure | timestamp sensor | Dashboards render it as "in 7 minutes" natively. Attributes: route/destination, platform & cars (trains), `delay_minutes`, `is_live`. |
| Departures | sensor | Next 5 departures as a list attribute for board cards. |
| Next *route* / Next train to *destination* | timestamp sensor | One per tracked route/destination. |
| Time to leave for the *route* | binary sensor (bus only) | On when `now ≥ departure − walk time`, using the **live** estimate — a bus running 3 minutes late delays the nudge by 3 minutes. Flips punctually, not on the next poll. |
| Status | diagnostic sensor | Last successful update; `rate_limited` attribute. |

Timestamps use the live estimate when a vehicle is tracked, otherwise the
schedule. Trains are always live; buses light up when the vehicle is on the
road (typically the imminent departure).

## Example automation

```yaml
automation:
  - alias: "Leave for the 414"
    trigger:
      - platform: state
        entity_id: binary_sensor.main_st_after_royal_st_12627_time_to_leave_for_the_414
        to: "on"
    condition:
      - condition: time
        after: "07:00:00"
        before: "09:00:00"
        weekday: [mon, tue, wed, thu, fri]
    action:
      - service: notify.mobile_app_your_phone
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

- Polling: buses every 2 minutes, trains every minute — one request per
  configured place. Transperth rate limits (HTTP 429) surface on the Status
  entity and back off automatically.
- Data comes from Transperth's unofficial website APIs (there is no official
  realtime feed). It can break without notice; entities go unavailable and
  recover on their own.
- Assumes your Home Assistant server runs in `Australia/Perth`.

## Removal

Delete the integration entries under **Settings → Devices & Services**, then
remove the repository from HACS.

## License

MIT
