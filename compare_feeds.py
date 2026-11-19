import os

import numpy as np
import pandas as pd

OLD_FEED = "data/old"
NEW_FEED = "data/new"
MOVE_THRESHOLD_M = 30
TRIP_CHANGE_THRESHOLD_PCT = 25
REPORT_FILE = "output/report.txt"


def load(feed_dir, filename):
    """read a GTFS file, columns kept as text"""
    return pd.read_csv(f"{feed_dir}/{filename}", dtype=str, encoding="utf-8-sig")


def for_display(table):
    """copy of a table ready to show"""
    shown = table.copy()
    if "change_pct" in shown.columns:
        shown["change_pct"] = shown["change_pct"].astype(object).replace(np.inf, "new service")
    return shown.fillna("")


def format_section(title, table, id_column):
    """heading with the number of IDs, then the table"""
    text = f"\n{title} ({table[id_column].nunique()})\n"
    if not table.empty:
        text += for_display(table).to_string(index=False) + "\n"
    return text


def format_header(old_agency, new_agency):
    """report title, which feeds were compared, warning if the agencies differ"""
    old_names = ", ".join(sorted(old_agency["agency_name"].dropna()))
    new_names = ", ".join(sorted(new_agency["agency_name"].dropna()))

    text = "GTFS FEED COMPARISON\n"
    text += f"Old feed: {OLD_FEED} ({old_names})\n"
    text += f"New feed: {NEW_FEED} ({new_names})\n"
    if old_names != new_names:
        text += "WARNING: The feeds have different agencies, check if files are correct!\n"
    return text


def report_duplicates(table, id_column, feed):
    """text warning about IDs that appear more than once"""
    dupes = table[table[id_column].duplicated(keep=False)].sort_values(id_column)
    if dupes.empty:
        return f"{feed} feed: every {id_column} is unique\n"
    count = dupes[id_column].nunique()
    text = f"WARNING: {count} {id_column} value(s) appear more than once in the {feed} feed\n"
    return text + for_display(dupes).to_string(index=False) + "\n"


def find_missing_and_new(old_stops, new_stops):
    """return stops only in the old feed (missing) and stops only in the new feed (new)"""
    old_ids = set(old_stops["stop_id"])
    new_ids = set(new_stops["stop_id"])

    missing_ids = old_ids - new_ids
    added_ids = new_ids - old_ids

    missing_stops = old_stops[old_stops["stop_id"].isin(missing_ids)][["stop_id", "stop_name"]].sort_values("stop_id")
    added_stops = new_stops[new_stops["stop_id"].isin(added_ids)][["stop_id", "stop_name"]].sort_values("stop_id")
    return missing_stops, added_stops


def find_missing_and_new_routes(old_routes, new_routes):
    """return routes only in the old feed (missing) and routes only in the new feed (new)"""
    columns = ["route_id", "route_short_name", "route_long_name"]
    old = old_routes.reindex(columns=columns).fillna("")  # spec allows for just one of those columns to be present
    new = new_routes.reindex(columns=columns).fillna("")

    old_ids = set(old["route_id"])
    new_ids = set(new["route_id"])

    missing_ids = old_ids - new_ids
    added_ids = new_ids - old_ids

    missing_routes = old[old["route_id"].isin(missing_ids)].sort_values("route_id")
    added_routes = new[new["route_id"].isin(added_ids)].sort_values("route_id")
    return missing_routes, added_routes


def find_trip_changes(old_routes, new_routes, old_trips, new_trips, threshold_pct):
    """return routes in both feeds that lost all trips, and routes whose trip count changed by threshold_pct or more"""
    columns = ["route_id", "route_short_name", "route_long_name"]
    routes = new_routes.reindex(columns=columns).fillna("")
    routes = routes[routes["route_id"].isin(old_routes["route_id"])].copy()

    old_counts = old_trips["route_id"].value_counts()
    new_counts = new_trips["route_id"].value_counts()
    routes["trips_old"] = routes["route_id"].map(old_counts).fillna(0).astype(int)
    routes["trips_new"] = routes["route_id"].map(new_counts).fillna(0).astype(int)

    lost_all = routes[(routes["trips_old"] > 0) & (routes["trips_new"] == 0)]

    running = routes[routes["trips_new"] > 0].copy()
    running["change_pct"] = ((running["trips_new"] - running["trips_old"]) / running["trips_old"] * 100).round(1)
    changed = running[running["change_pct"].abs() >= threshold_pct]  # 0 old trips gives inf, so it's reported
    return lost_all.sort_values("route_id"), changed.sort_values("route_id")


def normalize_name(names):
    """lowercase, trim and collapse spaces; same letters stored the same way; blank names become empty text"""
    return (
        names.fillna("")
        .str.normalize("NFC")  # same letter always stored the same way
        .str.lower()
        .str.split()
        .str.join(" ")
    )


def find_renamed_stops(old_stops, new_stops):
    """return stops in both feeds whose name changed, with old and new name"""
    old = old_stops[["stop_id", "stop_name"]]
    new = new_stops[["stop_id", "stop_name"]]

    pairs = old.merge(new, on="stop_id", suffixes=("_old", "_new"))
    renamed = pairs[normalize_name(pairs["stop_name_old"]) != normalize_name(pairs["stop_name_new"])]
    return renamed.sort_values("stop_id")


def distance_m(lat1, lon1, lat2, lon2):
    """approximate distance in metres between two points"""
    metres_per_degree = 111_320
    middle_lat = np.radians((lat1 + lat2) / 2)

    north = (lat2 - lat1) * metres_per_degree
    east = (lon2 - lon1) * metres_per_degree * np.cos(middle_lat)
    return np.sqrt(north ** 2 + east ** 2)


def find_moved_stops(old_stops, new_stops, threshold_m):
    """return stops in both feeds that moved more than threshold_m metres"""
    old = old_stops[["stop_id", "stop_lat", "stop_lon"]]
    new = new_stops[["stop_id", "stop_name", "stop_lat", "stop_lon"]]

    pairs = old.merge(new, on="stop_id", suffixes=("_old", "_new"))
    for column in ["stop_lat_old", "stop_lon_old", "stop_lat_new", "stop_lon_new"]:
        pairs[column] = pd.to_numeric(pairs[column], errors="coerce")  # broken coordinate - NaN

    pairs["moved_m"] = distance_m(
        pairs["stop_lat_old"], pairs["stop_lon_old"], pairs["stop_lat_new"], pairs["stop_lon_new"]
    ).round(1)
    moved = pairs[pairs["moved_m"] > threshold_m]  # NaN is never > threshold, so not reported
    return moved[["stop_id", "stop_name", "moved_m"]].sort_values("stop_id")


def main():
    old_agency = load(OLD_FEED, "agency.txt")
    new_agency = load(NEW_FEED, "agency.txt")
    old_stops = load(OLD_FEED, "stops.txt")
    new_stops = load(NEW_FEED, "stops.txt")
    old_routes = load(OLD_FEED, "routes.txt")
    new_routes = load(NEW_FEED, "routes.txt")
    old_trips = load(OLD_FEED, "trips.txt")
    new_trips = load(NEW_FEED, "trips.txt")

    missing_stops, added_stops = find_missing_and_new(old_stops, new_stops)
    renamed_stops = find_renamed_stops(old_stops, new_stops)
    moved_stops = find_moved_stops(old_stops, new_stops, MOVE_THRESHOLD_M)
    missing_routes, added_routes = find_missing_and_new_routes(old_routes, new_routes)
    lost_trips_routes, changed_trips_routes = find_trip_changes(
        old_routes, new_routes, old_trips, new_trips, TRIP_CHANGE_THRESHOLD_PCT
    )

    report = format_header(old_agency, new_agency)

    report += "\nINPUT CHECKS\n"
    report += report_duplicates(old_stops, "stop_id", "old")
    report += report_duplicates(new_stops, "stop_id", "new")
    report += report_duplicates(old_routes, "route_id", "old")
    report += report_duplicates(new_routes, "route_id", "new")

    summary = [
        ("Stops in old feed", old_stops["stop_id"].nunique()),
        ("Stops in new feed", new_stops["stop_id"].nunique()),
        ("Missing stops", missing_stops["stop_id"].nunique()),
        ("New stops", added_stops["stop_id"].nunique()),
        ("Renamed stops", renamed_stops["stop_id"].nunique()),
        (f"Stops moved more than {MOVE_THRESHOLD_M} m", moved_stops["stop_id"].nunique()),
        ("Routes in old feed", old_routes["route_id"].nunique()),
        ("Routes in new feed", new_routes["route_id"].nunique()),
        ("Missing routes", missing_routes["route_id"].nunique()),
        ("New routes", added_routes["route_id"].nunique()),
        ("Routes that lost all trips", lost_trips_routes["route_id"].nunique()),
        (f"Routes with trips changed {TRIP_CHANGE_THRESHOLD_PCT}% or more", changed_trips_routes["route_id"].nunique()),
    ]
    report += "\nSUMMARY\n"
    for label, count in summary:
        report += f"{label:<42}{count}\n"

    report += "\nDETAILS\n"
    report += format_section("Missing stops", missing_stops, "stop_id")
    report += format_section("New stops", added_stops, "stop_id")
    report += format_section("Renamed stops", renamed_stops, "stop_id")
    report += format_section(f"Stops moved more than {MOVE_THRESHOLD_M} m", moved_stops, "stop_id")
    report += format_section("Missing routes", missing_routes, "route_id")
    report += format_section("New routes", added_routes, "route_id")
    report += format_section("Routes that lost all trips", lost_trips_routes, "route_id")
    report += format_section(
        f"Routes with trips changed {TRIP_CHANGE_THRESHOLD_PCT}% or more", changed_trips_routes, "route_id"
    )

    print(report)
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as file:
        file.write(report)
    print(f"Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()

# TODO: ??? flag missing+new pairs with the same name as possible ID changes
# TODO: output report CSV
# TODO: command line
# TODO: data quality section? (broken coords, orphan trips)
# TODO: limitations for README: different service time length