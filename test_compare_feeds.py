import pandas as pd

from compare_feeds import find_missing_and_new, find_renamed_stops


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