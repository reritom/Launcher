import unittest
import datetime

from .interval_resource_manager import IntervalResourceManager, Resource, AllocationError

class IntervalResourceManagerTest(unittest.TestCase):
    def test_init(self):
        manager = IntervalResourceManager(interval_duration=datetime.timedelta(seconds=60))
        self.assertEqual(manager.daily_intervals, 1440)
        self.assertEqual(manager.days, {})

    def test_allocate_resource(self):
        resources = [Resource(id="id1")]
        manager = IntervalResourceManager(interval_duration=datetime.timedelta(seconds=60), resources=resources)

        # Test 1 - Normal allocation
        manager.allocate_resource(
            resource_id="id1",
            date=datetime.datetime.now(),
            interval=0
        )

        # Test 2 - Allocate the next interval
        manager.allocate_resource(
            resource_id="id1",
            date=datetime.datetime.now(),
            interval=1
        )

        # Test 3 - Duplicate allocation raises an error
        with self.assertRaises(AllocationError) as ctx:
            manager.allocate_resource(
                resource_id="id1",
                date=datetime.datetime.now(),
                interval=1
            )

    def test_get_available_intervals(self):
        resources = [Resource(id="id1")]
        manager = IntervalResourceManager(interval_duration=datetime.timedelta(seconds=60), resources=resources)

        manager.allocate_resource(
            resource_id="id1",
            date=datetime.datetime.now(),
            interval=0
        )

        manager.allocate_resource(
            resource_id="id1",
            date=datetime.datetime.now(),
            interval=1
        )

        available_windows = manager.get_available_intervals(date=datetime.datetime.now())
        expected_windows = [i for i in range(1440) if i not in (0, 1)]

        self.assertEqual(available_windows, expected_windows)

    def test_get_nearest_intervals_to_window_start(self):
        now = datetime.datetime.now()
        test_time = datetime.datetime.strptime(now.strftime("%d/%m/%Y") + " 12:00:00", "%d/%m/%Y %H:%M:%S")
        resources = [Resource(id="id1")]
        manager = IntervalResourceManager(interval_duration=datetime.timedelta(hours=1), resources=resources)

        manager.allocate_resource(
            resource_id="id1",
            date=datetime.datetime.now(),
            interval=0
        )

        nearest_intervals = manager.get_nearest_intervals_to_window_start(reference_time=test_time)
        expected_nearest_intervals = [12, 11, 13, 10, 14, 9, 15, 8, 16, 7, 17, 6, 18, 5, 19, 4, 20, 3, 21, 2, 22, 1, 23]
        self.assertEqual(nearest_intervals, expected_nearest_intervals)

    def test_get_nearest_intervals_to_window_end(self):
        now = datetime.datetime.now()
        test_time = datetime.datetime.strptime(now.strftime("%d/%m/%Y") + " 12:00:00", "%d/%m/%Y %H:%M:%S")
        resources = [Resource(id="id1")]
        manager = IntervalResourceManager(interval_duration=datetime.timedelta(hours=1), resources=resources)

        manager.allocate_resource(
            resource_id="id1",
            date=datetime.datetime.now(),
            interval=0
        )

        nearest_intervals = manager.get_nearest_intervals_to_window_end(reference_time=test_time)
        expected_nearest_intervals = [11, 10, 12, 9, 13, 8, 14, 7, 15, 6, 16, 5, 17, 4, 18, 3, 19, 2, 20, 1, 21, 22, 23]
        self.assertEqual(nearest_intervals, expected_nearest_intervals)
