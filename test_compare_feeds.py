import pandas as pd

from compare_feeds import find_missing_and_new, find_renamed_stops, normalize_name


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