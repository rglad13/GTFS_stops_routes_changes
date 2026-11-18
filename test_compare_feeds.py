import pandas as pd

from compare_feeds import find_missing_and_new


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