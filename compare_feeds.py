import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent

OLD_FEED = "data/old"
NEW_FEED = "data/new"
MOVE_THRESHOLD_M = 30
TRIP_CHANGE_THRESHOLD_PCT = 25
REPORT_FILE = "output/report.txt"
CSV_FILE = "output/report.csv"


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


def format_header(old_agency, new_agency, old_feed, new_feed):
    """report title, which feeds were compared, warning if the agencies differ"""
    old_names = ", ".join(sorted(old_agency["agency_name"].dropna()))
    new_names = ", ".join(sorted(new_agency["agency_name"].dropna()))

    text = "GTFS FEED COMPARISON\n"
    text += f"Old feed: {old_feed} ({old_names})\n"
    text += f"New feed: {new_feed} ({new_names})\n"
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


def csv_rows(category, ids, names, old_value="", new_value="", change=""):
    """rows for the CSV report"""
    return pd.DataFrame({
        "category": category,
        "id": ids,
        "name": names,
        "old_value": old_value,
        "new_value": new_value,
        "change": change,
    })


def route_name(routes):
    """short and long name together"""
    return (routes["route_short_name"] + " " + routes["route_long_name"]).str.strip()


def find_bad_coordinates(stops):
    """return stops with bad coords"""
    columns = ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type"]
    table = stops.reindex(columns=columns)
    needs_coordinates = ~table["location_type"].isin(["3", "4"])  # generic nodes and boarding areas may have none

    lat = pd.to_numeric(table["stop_lat"], errors="coerce")
    lon = pd.to_numeric(table["stop_lon"], errors="coerce")

    problem = pd.Series("", index=table.index)
    problem.loc[lat.isna() | lon.isna()] = "missing or not a number"
    problem.loc[(lat.abs() > 90) | (lon.abs() > 180)] = "out of range"
    problem.loc[(lat == 0) & (lon == 0)] = "0, 0 placeholder"

    table["problem"] = problem
    bad = table[needs_coordinates & (problem != "")]
    return bad[["stop_id", "stop_name", "stop_lat", "stop_lon", "problem"]].sort_values("stop_id")


def find_orphan_trips(trips, routes):
    """return route_ids used in trips but missing in routes"""
    orphans = trips[~trips["route_id"].isin(routes["route_id"])]
    counts = orphans["route_id"].value_counts().reset_index(name="trips")
    return counts.sort_values("route_id")


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


def feed_folders():
    """old and new feed folders: from the command line if given, otherwise the settings at the top"""
    if len(sys.argv) == 3:
        return sys.argv[1], sys.argv[2]
    if len(sys.argv) == 1:
        return HERE / OLD_FEED, HERE / NEW_FEED
    print("Usage: python compare_feeds.py [OLD_FEED_FOLDER NEW_FEED_FOLDER]")
    sys.exit(1)


def main():
    old_feed, new_feed = feed_folders()
    report_file = HERE / REPORT_FILE
    csv_file = HERE / CSV_FILE

    old_agency = load(old_feed, "agency.txt")
    new_agency = load(new_feed, "agency.txt")
    old_stops = load(old_feed, "stops.txt")
    new_stops = load(new_feed, "stops.txt")
    old_routes = load(old_feed, "routes.txt")
    new_routes = load(new_feed, "routes.txt")
    old_trips = load(old_feed, "trips.txt")
    new_trips = load(new_feed, "trips.txt")

    missing_stops, added_stops = find_missing_and_new(old_stops, new_stops)
    renamed_stops = find_renamed_stops(old_stops, new_stops)
    moved_stops = find_moved_stops(old_stops, new_stops, MOVE_THRESHOLD_M)
    missing_routes, added_routes = find_missing_and_new_routes(old_routes, new_routes)
    lost_trips_routes, changed_trips_routes = find_trip_changes(
        old_routes, new_routes, old_trips, new_trips, TRIP_CHANGE_THRESHOLD_PCT
    )

    report = format_header(old_agency, new_agency, old_feed, new_feed)

    report += "\nDATA QUALITY\n"
    report += report_duplicates(old_stops, "stop_id", "old")
    report += report_duplicates(new_stops, "stop_id", "new")
    report += report_duplicates(old_routes, "route_id", "old")
    report += report_duplicates(new_routes, "route_id", "new")
    report += format_section("Stops with unusable coordinates (old feed)", find_bad_coordinates(old_stops), "stop_id")
    report += format_section("Stops with unusable coordinates (new feed)", find_bad_coordinates(new_stops), "stop_id")
    report += format_section(
        "route_id in trips.txt but not in routes.txt (old feed)", find_orphan_trips(old_trips, old_routes), "route_id"
    )
    report += format_section(
        "route_id in trips.txt but not in routes.txt (new feed)", find_orphan_trips(new_trips, new_routes), "route_id"
    )

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

    pct = changed_trips_routes["change_pct"]
    csv_table = pd.concat([
        csv_rows("missing stop", missing_stops["stop_id"], missing_stops["stop_name"]),
        csv_rows("new stop", added_stops["stop_id"], added_stops["stop_name"]),
        csv_rows("renamed stop", renamed_stops["stop_id"], renamed_stops["stop_name_new"],
                 renamed_stops["stop_name_old"], renamed_stops["stop_name_new"]),
        csv_rows("moved stop", moved_stops["stop_id"], moved_stops["stop_name"],
                 change=moved_stops["moved_m"].astype(str) + " m"),
        csv_rows("missing route", missing_routes["route_id"], route_name(missing_routes)),
        csv_rows("new route", added_routes["route_id"], route_name(added_routes)),
        csv_rows("route lost all trips", lost_trips_routes["route_id"], route_name(lost_trips_routes),
                 lost_trips_routes["trips_old"], lost_trips_routes["trips_new"], "-100%"),
        csv_rows("route trips changed", changed_trips_routes["route_id"], route_name(changed_trips_routes),
                 changed_trips_routes["trips_old"], changed_trips_routes["trips_new"],
                 (pct.astype(str) + "%").where(~np.isinf(pct), "new service")),
    ])

    print(report)
    os.makedirs(report_file.parent, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as file:
        file.write(report)
    csv_table.to_csv(csv_file, index=False, encoding="utf-8-sig")  # -sig so Excel shows accents correctly
    print(f"Report saved to {report_file} and {csv_file}")


if __name__ == "__main__":
    main()

# TODO: ??? flag missing+new pairs with the same name as possible ID changes
# TODO: limitations for README: different service time length, csv for changes only, txt contains data quality
