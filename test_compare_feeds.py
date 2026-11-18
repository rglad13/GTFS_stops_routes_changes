import pandas as pd

from compare_feeds import distance_m, find_missing_and_new, find_moved_stops, find_renamed_stops, normalize_name, \
    find_missing_and_new_routes


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
