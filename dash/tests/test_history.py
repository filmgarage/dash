import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from history import int_param, number_or_none, reduce_history  # noqa: E402
from errors import ApiError  # noqa: E402

START = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=2)


def row(minutes, state):
    moment = START + timedelta(minutes=minutes)
    return {"state": state, "last_changed": moment.isoformat()}


class ReduceHistoryTests(unittest.TestCase):
    def test_one_point_per_bucket_with_the_time_weighted_average(self):
        rows = [row(0, "20"), row(30, "22")]  # 20 for the first 30 minutes, then 22
        points = reduce_history(rows, START, END, 2)  # buckets of 60 minutes
        self.assertEqual([p["v"] for p in points], [21.0, 22.0])
        self.assertEqual(points[0]["t"], "2026-11-21T12:00:00Z")
        self.assertEqual(points[1]["t"], "2026-11-21T13:00:00Z")

    def test_a_state_that_is_not_a_number_gives_a_gap(self):
        rows = [row(0, "20"), row(60, "unavailable"), row(90, "21")]
        points = reduce_history(rows, START, END, 4)  # 30-minute buckets
        self.assertEqual([p["v"] for p in points], [20.0, 20.0, None, 21.0])

    def test_no_rows_means_unknown_everywhere(self):
        points = reduce_history([], START, END, 10)
        self.assertEqual(len(points), 10)
        self.assertTrue(all(p["v"] is None for p in points))

    def test_points_are_sorted_by_time(self):
        points = reduce_history([row(0, "1")], START, END, 10)
        times = [p["t"] for p in points]
        self.assertEqual(times, sorted(times))

    def test_number_or_none(self):
        self.assertEqual(number_or_none("20.4"), 20.4)
        self.assertIsNone(number_or_none("on"))
        self.assertIsNone(number_or_none("unknown"))
        self.assertIsNone(number_or_none("nan"))


class ParameterTests(unittest.TestCase):
    def test_defaults_and_limits(self):
        self.assertEqual(int_param({}, "hours", 24, 1, 168), 24)
        self.assertEqual(int_param({"hours": "168"}, "hours", 24, 1, 168), 168)
        with self.assertRaises(ApiError) as err:
            int_param({"hours": "169"}, "hours", 24, 1, 168)
        self.assertEqual(err.exception.status, 400)
        with self.assertRaises(ApiError):
            int_param({"points": "ten"}, "points", 120, 10, 500)


if __name__ == "__main__":
    unittest.main()
