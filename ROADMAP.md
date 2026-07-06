# Roadmap

Where this project is and what's left, in order. Companion library:
[`aiotransperth`](https://github.com/Chris112/aiotransperth).

## ✅ Done

- `aiotransperth` library: bus + train clients, realtime delays, typed models,
  40 offline tests + live contract suite, CI, PyPI release workflow.
- `ha-transperth` integration: config flows (bus stop / train station),
  timestamp entities, departure boards, delay-aware time-to-leave binary
  sensor, diagnostic status sensor, four ad-hoc services, options flows,
  22 offline tests, hassfest + HACS validation CI.
- Both repos on GitHub under Chris112.

## Phase 1 — Release (blocks everything below)

- [ ] PyPI: add a **trusted publisher** for `Chris112/aiotransperth`
      (pypi.org → publishing → workflow `release.yml`, environment `pypi`)
      and create the `pypi` environment in the repo settings.
- [ ] Publish `aiotransperth` **v0.1.0** via a GitHub release — the
      integration's `manifest.json` pins `aiotransperth==0.1.0` from PyPI,
      so HA can't install requirements until this exists.
- [ ] Confirm CI green on both repos.
- [ ] Tag/release `ha-transperth` **v0.1.0** (HACS installs from releases).

## Phase 2 — Real-world validation (own install)

- [ ] Add `https://github.com/Chris112/ha-transperth` as a HACS custom
      repository, install, restart HA.
- [ ] Add a train entry: Midland Line → Maylands Stn → track "Perth".
- [ ] Add a bus entry (stop 12627) to exercise the bus path + time-to-leave.
- [ ] Watch a real morning: do the countdown, delay attributes, and
      time-to-leave flip behave? Does the Status entity stay clean?
- [ ] Run each service once from Developer Tools with responses.
- [ ] Retire the old `rest_command.get_next_train_time` + script.
- [ ] Let it run for a week; check logs for UpdateFailed noise / 429s.

## Phase 3 — Community release

- [ ] Submit to the **HACS default store** (requires: releases, description,
      topics, README, passing hacs/action — all in place after Phase 1).
- [ ] **home-assistant/brands** PR so the integration gets a proper logo
      (currently the `brands` quality-scale item is `todo`).
- [ ] Archive `transperth_bus_times` with a README pointer to both
      successors.

## Phase 4 — Quality scale (Gold)

- [ ] `diagnostics` platform: config-entry diagnostics dump (redact nothing —
      no credentials exist, but keep the pattern).
- [ ] Entity translations (`translations/en.json` entity names) and icons.
- [ ] Reconfigure flow (change stop code / station without removing).

## Phase 5 — Feature backlog (in rough value order)

- [ ] **Decode realtime status enums** — observed: bus `2`=delayed,
      `-1`=unavailable; train `1`=on time, `2`=delayed. Cancelled/early
      values unconfirmed; models pass raw codes through, so this is
      observation work, then richer `LiveStatus`.
- [ ] **Service disruptions** — probe `GetTripInfoAsync`
      (`Status`, `RealTime`, `Interruptions`) and, if useful, add an alerts
      sensor per place.
- [ ] **Train "All lines" view** — the site supports line=`All`; useful for
      interchange stations (probe the URL variant first).
- [ ] **Adaptive polling** — tighten the bus interval only in the final
      minutes before a tracked departure; laziest possible otherwise.
- [ ] **Train lead-time option** — optional drive/walk lead minutes +
      time-to-leave binary sensor for train entries (dropped from v1
      deliberately).
- [ ] **Ferries** — models carry `mode` already; needs API exploration.
- [ ] **Busy-interchange depth** — verify how many trips the bus endpoint
      returns at high-frequency stops (self-cap behaviour beyond ~13).

## Known constraints (by design)

- Unofficial API: can break without notice. The library's `pytest -m live`
  contract suite is the early-warning system — run it when something looks
  wrong before blaming the code.
- Bus realtime only covers vehicles already on the road.
- One request per place per poll; Transperth's 429 cooldown is sticky and
  shared with their public website.
