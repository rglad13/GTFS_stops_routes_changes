import pandas as pd

from compare_feeds import distance_m, find_missing_and_new, find_moved_stops, find_renamed_stops, normalize_name, \
    find_missing_and_new_routes, find_trip_changes, for_display, format_header, report_duplicates, \
    csv_rows, route_name


def test_stop_only_in_old_feed_is_missing():
    old = pd.DataFrame({"stop_id": ["A", "B"], "stop_name": ["Alpha", "Beta"]})
    new = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Alpha"]})

    missing, added = find_missing_and_new(old, new)

    assert list(missing["stop_id"]) == ["B"]
    assert added.empty


def test_stop_only_in_new_feed_is_new():
    old = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Alpha"]})
    new = pd.DataFrame({"stop_id": ["A", "C"], "stop_name": ["Alpha", "Gamma"]})

    missing, added = find_missing_and_new(old, new)

    assert missing.empty
    assert list(added["stop_id"]) == ["C"]


def test_stop_with_different_name_is_renamed():
    old = pd.DataFrame({"stop_id": ["A", "B"], "stop_name": ["Alpha", "Beta"]})
    new = pd.DataFrame({"stop_id": ["A", "B"], "stop_name": ["Alpha", "Beta North"]})

    renamed = find_renamed_stops(old, new)

    assert list(renamed["stop_id"]) == ["B"]
    assert list(renamed["stop_name_old"]) == ["Beta"]
    assert list(renamed["stop_name_new"]) == ["Beta North"]


def test_blank_names_only_count_when_one_side_has_a_name():
    old = pd.DataFrame({"stop_id": ["A", "B", "C"], "stop_name": [None, None, "Gamma"]}, dtype="str")
    new = pd.DataFrame({"stop_id": ["A", "B", "C"], "stop_name": [None, "Beta", None]}, dtype="str")

    renamed = find_renamed_stops(old, new)

    assert list(renamed["stop_id"]) == ["B", "C"]


def test_normalize_name_ignores_case_and_extra_spaces_but_keeps_accents():
    names = pd.Series(["  Šilo   Gatvė ", "ŠILO GATVĖ", "Silo Gatve", None], dtype="str")

    assert list(normalize_name(names)) == ["šilo gatvė", "šilo gatvė", "silo gatve", ""]


def test_same_letter_stored_two_ways_is_not_renamed():
    old = pd.DataFrame({
        "stop_id": ["A", "B"],
        "stop_name": ["\u0160ilas", "\u0104žuolas"],  # Š and Ą as single characters
    })
    new = pd.DataFrame({
        "stop_id": ["A", "B"],
        "stop_name": ["S\u030cilas", "A\u0328žuolas"],  # S + caron (ˇ), A + ogonek (˛); look the same
    })

    assert find_renamed_stops(old, new).empty


def test_case_change_is_not_renamed():
    old = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Park Gate"]})
    new = pd.DataFrame({"stop_id": ["A"], "stop_name": ["PARK GATE"]})

    assert find_renamed_stops(old, new).empty


def test_accent_change_is_renamed():
    old = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Šilas"]})
    new = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Silas"]})

    renamed = find_renamed_stops(old, new)

    assert list(renamed["stop_id"]) == ["A"]


def test_distance_of_one_thousandth_degree_north_is_about_111_m():
    lat1, lon1 = pd.Series([47.75]), pd.Series([-3.36])
    lat2, lon2 = pd.Series([47.751]), pd.Series([-3.36])

    assert round(distance_m(lat1, lon1, lat2, lon2)[0]) == 111


def test_stop_moved_50_m_is_reported_and_5_m_is_not():
    old = pd.DataFrame({
        "stop_id": ["A", "B"],
        "stop_name": ["Hospital", "Library"],
        "stop_lat": ["47.753000", "47.754000"],
        "stop_lon": ["-3.366000", "-3.368000"],
    })
    new = pd.DataFrame({
        "stop_id": ["A", "B"],
        "stop_name": ["Hospital", "Library"],
        "stop_lat": ["47.753450", "47.754045"],  # A about 50 m north, B about 5 m north
        "stop_lon": ["-3.366000", "-3.368000"],
    })

    moved = find_moved_stops(old, new, threshold_m=30)

    assert list(moved["stop_id"]) == ["A"]
    assert 49 < moved["moved_m"].iloc[0] < 51


def test_stop_with_broken_coordinate_is_not_reported_as_moved():
    old = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Hospital"], "stop_lat": ["47.753"], "stop_lon": ["-3.366"]})
    new = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Hospital"], "stop_lat": ["oops"], "stop_lon": ["-3.366"]})

    assert find_moved_stops(old, new, threshold_m=30).empty


def test_route_only_in_old_feed_is_missing_and_only_in_new_is_new():
    old = pd.DataFrame({
        "route_id": ["R1", "R2"],
        "route_short_name": ["1", "2"],
        "route_long_name": ["Namai - Parduotuvė", "Namai - Baras"],
    })
    new = pd.DataFrame({
        "route_id": ["R1", "R3"],
        "route_short_name": ["1", "3"],
        "route_long_name": ["Namai - Parduotuvė", "Namai - Kapinės"],
    })

    missing, added = find_missing_and_new_routes(old, new)

    assert list(missing["route_id"]) == ["R2"]
    assert list(added["route_id"]) == ["R3"]


def test_routes_work_when_a_feed_has_only_one_name_column():
    old = pd.DataFrame({"route_id": ["R1", "R2"], "route_short_name": ["1", "2"]})  # no long names
    new = pd.DataFrame(
        {"route_id": ["R1", "R3"], "route_long_name": ["Namai - Parduotuvė", "Namai - Baras"]})  # no short names

    missing, added = find_missing_and_new_routes(old, new)

    assert list(missing["route_id"]) == ["R2"]
    assert list(added["route_id"]) == ["R3"]
    assert list(added.columns) == ["route_id", "route_short_name", "route_long_name"]


def make_routes(route_ids):
    return pd.DataFrame({"route_id": route_ids, "route_short_name": route_ids})


def make_trips(trips_per_route):
    route_ids = []
    for route_id, count in trips_per_route.items():
        route_ids += [route_id] * count
    return pd.DataFrame({"route_id": route_ids})


def test_trip_change_of_25_percent_or_more_is_reported():
    routes = make_routes(["DROP", "SMALL", "EXACT", "RISE"])
    old_trips = make_trips({"DROP": 10, "SMALL": 10, "EXACT": 8, "RISE": 4})
    new_trips = make_trips({"DROP": 5, "SMALL": 9, "EXACT": 6, "RISE": 6})  # -50%, -10%, -25%, +50%

    lost_all, changed = find_trip_changes(routes, routes, old_trips, new_trips, threshold_pct=25)

    assert lost_all.empty
    assert list(changed["route_id"]) == ["DROP", "EXACT", "RISE"]
    assert list(changed["change_pct"]) == [-50.0, -25.0, 50.0]


def test_route_with_no_trips_left_is_lost_not_changed():
    routes = make_routes(["A", "B"])
    old_trips = make_trips({"A": 4, "B": 4})
    new_trips = make_trips({"B": 4})  # A is still in routes.txt but has no trips

    lost_all, changed = find_trip_changes(routes, routes, old_trips, new_trips, threshold_pct=25)

    assert list(lost_all["route_id"]) == ["A"]
    assert changed.empty


def test_route_that_had_no_trips_and_now_has_some_is_reported_as_changed():
    routes = make_routes(["A"])
    old_trips = make_trips({})
    new_trips = make_trips({"A": 3})

    lost_all, changed = find_trip_changes(routes, routes, old_trips, new_trips, threshold_pct=25)

    assert lost_all.empty
    assert list(changed["route_id"]) == ["A"]


def test_removed_route_is_not_counted_as_lost_trips():
    old_routes = make_routes(["A", "B"])
    new_routes = make_routes(["A"])  # B removed from routes.txt, reported as a missing route instead
    old_trips = make_trips({"A": 4, "B": 4})
    new_trips = make_trips({"A": 4})

    lost_all, changed = find_trip_changes(old_routes, new_routes, old_trips, new_trips, threshold_pct=25)

    assert lost_all.empty
    assert changed.empty


def test_for_display_shows_new_service_and_empty_blanks():
    table = pd.DataFrame({"route_id": ["A", "B"], "route_long_name": [None, "Port"], "change_pct": [float("inf"), -50.0]})

    shown = for_display(table)

    assert list(shown["change_pct"]) == ["new service", -50.0]
    assert list(shown["route_long_name"]) == ["", "Port"]


def test_header_warns_when_agencies_differ():
    old = pd.DataFrame({"agency_name": ["Grybas"]})
    same = pd.DataFrame({"agency_name": ["Grybas"]})
    other = pd.DataFrame({"agency_name": ["Baravykas"]})

    assert "WARNING" not in format_header(old, same)
    assert "WARNING" in format_header(old, other)


def test_report_duplicates_names_the_repeated_id():
    stops = pd.DataFrame({"stop_id": ["A", "B", "B"], "stop_name": ["Alpha", "Beta", "Beta"]})

    text = report_duplicates(stops, "stop_id", "new")

    assert "WARNING: 1 stop_id value(s) appear more than once in the new feed" in text
    assert text.count("Beta") == 2


def test_csv_rows_have_the_same_columns_for_every_category():
    stops = pd.DataFrame({"stop_id": ["A"], "stop_name": ["Alpha"]})

    rows = csv_rows("missing stop", stops["stop_id"], stops["stop_name"])

    assert list(rows.columns) == ["category", "id", "name", "old_value", "new_value", "change"]
    assert rows.iloc[0].tolist() == ["missing stop", "A", "Alpha", "", "", ""]


def test_csv_rows_for_an_empty_table_give_no_rows():
    stops = pd.DataFrame({"stop_id": [], "stop_name": []})

    assert csv_rows("missing stop", stops["stop_id"], stops["stop_name"]).empty


def test_route_name_joins_short_and_long_and_handles_blanks():
    routes = pd.DataFrame({"route_short_name": ["122", "", "T4"], "route_long_name": ["Gare - Port", "Beach Loop", ""]})

    assert list(route_name(routes)) == ["122 Gare - Port", "Beach Loop", "T4"]