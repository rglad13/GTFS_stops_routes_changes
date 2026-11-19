
# GTFS stops & routes changes

Compares two versions of a GTFS feed and reports what changed in stops and routes, plus data-quality problems that affect the comparison.

## What it reports

- **Stops** (by `stop_id`): missing, new, renamed, moved more than 30 m
- **Routes** (by `route_id`): missing, new, lost all trips, trip count changed by 25% or more
- **Data quality**: duplicate IDs, unusable coordinates, trips with an unknown `route_id`

## How to run

Requires Python 3.12 or newer (developed and tested on 3.14).

```
pip install -r requirements.txt
python compare_feeds.py sample/old sample/new
```

Use your own feed folders instead of `sample/old` and `sample/new`. Without arguments, the tool compares `data/old` and `data/new`. The report is printed and saved to `output/report.txt` and `output/report.csv`.

Tests: `pytest`

Thresholds are set at the top of `compare_feeds.py`: `MOVE_THRESHOLD_M = 30`, `TRIP_CHANGE_THRESHOLD_PCT = 25`.

## Example (sample feed)

```
Missing stops                             1
New stops                                 1
Renamed stops                             1
Stops moved more than 30 m                1
Missing routes                            1
New routes                                1
Routes that lost all trips                1
Routes with trips changed 25% or more     1
```

## Limitations

- Not a validator: run a GTFS validator first. This tool only checks data problems that affect the comparison.
- Trip counts assume both feeds cover a similar period.
- Results for duplicated IDs may be unreliable (flagged in the report).
- A stop with a new `stop_id` appears as one missing and one new stop.
- `report.csv` lists changes only; data-quality findings are in `report.txt`.

## Next steps

- flag missing + new stops with the same name as possible ID changes
- warn when the feeds cover very different periods