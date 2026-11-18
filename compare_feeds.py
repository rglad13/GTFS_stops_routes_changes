import numpy as np
import pandas as pd

OLD_FEED = "data/old"
NEW_FEED = "data/new"
MOVE_THRESHOLD_M = 30


def load(feed_dir, filename):
    """read a GTFS file, columns kept as text"""
    return pd.read_csv(f"{feed_dir}/{filename}", dtype=str, encoding="utf-8-sig")


def print_stop_list(title, stops):
    """print stop ID and name"""
    print(f"\n{title} ({stops['stop_id'].nunique()})")
    if not stops.empty:
        print(stops.to_string(index=False))


def print_route_list(title, routes):
    """print route ID, short name and long name"""
    print(f"\n{title} ({routes['route_id'].nunique()})")
    if not routes.empty:
        print(routes.to_string(index=False))


def report_duplicates(table, id_column, feed):
    """warn about IDs that appear more than once"""
    dupes = table[table[id_column].duplicated(keep=False)].sort_values(id_column)
    if dupes.empty:
        print(f"{feed} feed: every {id_column} is unique")
    else:
        count = dupes[id_column].nunique()
        print(f"WARNING: {count} {id_column} value(s) appear more than once in the {feed} feed")
        print(dupes.to_string(index=False))


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
    old_stops = load(OLD_FEED, "stops.txt")
    new_stops = load(NEW_FEED, "stops.txt")
    old_routes = load(OLD_FEED, "routes.txt")
    new_routes = load(NEW_FEED, "routes.txt")

    report_duplicates(old_stops, "stop_id", "old")
    report_duplicates(new_stops, "stop_id", "new")
    report_duplicates(old_routes, "route_id", "old")
    report_duplicates(new_routes, "route_id", "new")

    missing_stops, added_stops = find_missing_and_new(old_stops, new_stops)
    renamed_stops = find_renamed_stops(old_stops, new_stops)
    moved_stops = find_moved_stops(old_stops, new_stops, MOVE_THRESHOLD_M)
    missing_routes, added_routes = find_missing_and_new_routes(old_routes, new_routes)

    print("Old feed stops:", old_stops["stop_id"].nunique())
    print("New feed stops:", new_stops["stop_id"].nunique())
    print("Missing stops: ", missing_stops["stop_id"].nunique())
    print("New stops:     ", added_stops["stop_id"].nunique())
    print("Renamed stops: ", renamed_stops["stop_id"].nunique())
    print("Moved stops:   ", moved_stops["stop_id"].nunique())
    print("Old feed routes:", old_routes["route_id"].nunique())
    print("New feed routes:", new_routes["route_id"].nunique())
    print("Missing routes: ", missing_routes["route_id"].nunique())
    print("New routes:     ", added_routes["route_id"].nunique())

    print_stop_list("Missing stops", missing_stops)
    print_stop_list("New stops", added_stops)
    print_stop_list("Renamed stops", renamed_stops)
    print_stop_list(f"Stops moved more than {MOVE_THRESHOLD_M} m", moved_stops)
    print_route_list("Missing routes", missing_routes)
    print_route_list("New routes", added_routes)


if __name__ == "__main__":
    main()

# TODO: ??? flag missing+new pairs with the same name as possible ID changes
# TODO: report header with agency name; warn if agencies differ
# TODO: routes that lost all trips
# TODO: output report (CSV?)
# TODO: command line
# TODO: data quality section? (broken coords, ???)
