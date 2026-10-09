# Delhi Underpass Flood Early Warning (prototype)

Early warning plus live community status for Delhi's chronic waterlogging hotspots, mostly underpasses.
Built solo for Environmental Hacks (WeMakeDevs x AWS, Bharat Builds Delhi), Heat and Water track, 8-11 Oct 2026.

**Promise:** give commuters, bus operators and ambulance drivers an early warning before a known flood-prone
underpass becomes unsafe, and let people on the ground confirm or correct it live.

> Prototype. Estimated risk, not an official warning. No claim of water depth or street-level prediction.

## Status

- [x] Incident dataset in `data/events.csv` (dated flood and "stayed clear" records with source links)
- [x] Rainfall + threshold pipeline (`pipeline/`)
- [x] Delhi hotspot map with marker details
- [ ] Risk cards, "Why this alert?"
- [ ] Live community reports on AWS (API Gateway, Lambda, DynamoDB)
- [ ] Replay mode and evaluation panel

## How the model works

- Hourly rainfall from Open-Meteo at each hotspot's coordinates. For each (hotspot, event date) we take the
  strongest 1-hour burst and the strongest 3-hour total in a 36-hour local-time window.
- A hotspot's threshold is the lowest rain at which it was recorded flooding, per window, once it has at least
  3 recorded floods. Otherwise a pooled threshold (25th percentile of all recorded floods) is used and the
  hotspot is labelled "limited evidence".
- Risk compares forecast rain with the threshold (green / yellow / orange / red). No LLM in the core.
- Evaluation is leave-one-storm-out: each storm day is predicted using thresholds learned from the other days.
  The effective sample size is the number of storm days, not the number of rows.

Run it:

```bash
pip install -r requirements.txt
python pipeline/fetch_rain.py        # downloads hourly rain from Open-Meteo into data/rain/
python pipeline/fit_thresholds.py    # data/thresholds.json
python pipeline/evaluate.py          # data/metrics.json (leave-one-storm-out)
```

Start the web map:

```bash
cd web
npm install
npm run dev
```

## Data and credits

- Incident records were compiled from public news reports before the event; every row has its link in
  `source_url` (see also `SOURCES.md`). Rain figures quoted in articles are informational only; the model uses
  Open-Meteo rainfall.
- Rainfall: Weather data by [Open-Meteo.com](https://open-meteo.com/), licensed CC BY 4.0.
- Hotspot coordinates in `data/hotspots.json` are approximate.

## AI tools used

Claude (Anthropic) was used to help with data cleaning, the pipeline scripts and drafting this README.

## Limitations

- Rainfall is effectively a city-wide signal (coarse grid; Delhi rain is patchy). Differences between hotspots
  come from their flood history, not from local rain measurements.
- Small sample: a handful of storm days and few "stayed clear" records, so results are counts, not rates.
- Reported incidents depend on news coverage, so quiet or unreported floods are missing.
- Infrastructure changes (new drains and pumps, for example at Minto Bridge and Pul Prahladpur) change how a
  hotspot behaves, and some hotspots behave inconsistently across storms.
- The hotspot list and thresholds live in data files so other cities could be added later. That is the only
  claim made about scaling.
