import pandas as pd

OLD_FEED = "data/old"
NEW_FEED = "data/new"


def load(feed_dir, filename):
    """read a GTFS file, columns kept as text"""
    return pd.read_csv(f"{feed_dir}/{filename}", dtype=str, encoding="utf-8-sig")


def print_stop_list(title, stops):
    """print stop ID and name"""
    print(f"\n{title} ({stops['stop_id'].nunique()})")
    if not stops.empty:
        print(stops.to_string(index=False))


def report_duplicates(stops, feed):
    """warn about duplicate stops"""
    dupes = stops[stops["stop_id"].duplicated(keep=False)].sort_values("stop_id")
    if dupes.empty:
        print(f"{feed} feed: every stop_id is unique")
    else:
        count = dupes["stop_id"].nunique()
        print(f"WARNING: {count} stop_id value(s) appear more than once in the {feed} feed")
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


def normalize_name(names):
    """lowercase, trim and collapse spaces, same letters stored the same way, missing names become empty text"""
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


def main():
    old_stops = load(OLD_FEED, "stops.txt")
    new_stops = load(NEW_FEED, "stops.txt")

    report_duplicates(old_stops, "old")
    report_duplicates(new_stops, "new")

    missing_stops, added_stops = find_missing_and_new(old_stops, new_stops)
    renamed_stops = find_renamed_stops(old_stops, new_stops)

    print("Old feed stops:", old_stops["stop_id"].nunique())
    print("New feed stops:", new_stops["stop_id"].nunique())
    print("Missing stops: ", missing_stops["stop_id"].nunique())
    print("New stops:     ", added_stops["stop_id"].nunique())
    print("Renamed stops: ", renamed_stops["stop_id"].nunique())

    print_stop_list("Missing stops", missing_stops)
    print_stop_list("New stops", added_stops)
    print_stop_list("Renamed stops", renamed_stops)


if __name__ == "__main__":
    main()

# TODO: ??? flag missing+new pairs with the same name as possible ID changes
# TODO: report header with agency name; warn if agencies differ
# TODO: stops that moved
# TODO: missing and new routes (route_id)
# TODO: routes that lost all trips
# TODO: output report (CSV?)
# TODO: command line
