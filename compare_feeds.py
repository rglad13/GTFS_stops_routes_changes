import pandas as pd



OLD_FEED = "data/old"
NEW_FEED = "data/new"


def load(feed_dir, filename):
    """read a GTFS file, columns kept as text"""
    return pd.read_csv(f"{feed_dir}/{filename}", dtype=str, encoding="utf-8-sig")


old_stops = load(OLD_FEED, "stops.txt")
new_stops = load(NEW_FEED, "stops.txt")

old_ids = set(old_stops["stop_id"])
new_ids = set(new_stops["stop_id"])

missing_ids = old_ids - new_ids
added_ids = new_ids - old_ids
common_ids = old_ids & new_ids # needed for next step

print("Old feed stops:", len(old_ids))
print("New feed stops:", len(new_ids))
print("Missing stops: ", len(missing_ids))
print("New stops:     ", len(added_ids))


# TODO: list missing/new stop_id and stop_name in the output, not just counts
# TODO: find stops with changed names (same stop_id, different name), show old and new name
# TODO: ??? flag missing+new pairs with the same name as possible ID changes
# TODO: duplicate IDs