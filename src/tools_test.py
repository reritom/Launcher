import unittest
import datetime
import math as maths

from .tools import distance_between, find_middle_position_by_ratio, without_microseconds

class TestWithoutMicroseconds(unittest.TestCase):
    def test_without_microseconds(self):
        delta = datetime.timedelta(seconds=30, microseconds=400000)
        processed = without_microseconds(delta)

        self.assertEqual(processed.seconds, delta.seconds)
        self.assertEqual(processed.microseconds, 0)

    def test_without_microseconds_with_rounding(self):
        delta = datetime.timedelta(seconds=30, microseconds=600000)
        processed = without_microseconds(delta)

        self.assertEqual(processed.seconds, 31)
        self.assertEqual(processed.microseconds, 0)

class TestDistanceBetween(unittest.TestCase):
    def test_distance_between_1(self):
        # Simple case in one plane
        distance = distance_between([0,0,0], [0,0,1])
        expected_distance = 1
        self.assertEqual(distance, expected_distance)

    def test_distance_between_2(self):
        # Case with two planes
        distance = distance_between([0,0,0], [0,1,1])
        expected_distance = maths.sqrt(2)
        self.assertEqual(distance, expected_distance)

    def test_distance_between_3(self):
        # Case with three planes
        distance = distance_between([0,0,0], [1,1,1])
        expected_distance = maths.sqrt(3)
        self.assertEqual(distance, expected_distance)

class TestFindMiddlePositionByRatio(unittest.TestCase):
    def test_find_middle_position_by_ratio_1_plane_simple(self):
        # Case with 1 plane
        middle_position = find_middle_position_by_ratio([0,0,0], [0,0,1], 0.5)
        expected_middle_position = [0,0,0.5]
        self.assertEqual(middle_position, expected_middle_position)

    def test_find_middle_position_by_ratio_1_plane_complex(self):
        # Case with 1 plane
        middle_position = find_middle_position_by_ratio([0,0,0], [0,0,1], 0.7)
        expected_middle_position = [0,0,0.7]
        self.assertEqual(middle_position, expected_middle_position)

    def test_find_middle_position_by_ratio_2_plane_simple(self):
        # Case with 2 plane
        middle_position = find_middle_position_by_ratio([0,0,0], [0,1,1], 0.5)
        expected_middle_position = [0,0.5,0.5]
        self.assertEqual(middle_position, expected_middle_position)

    def test_find_middle_position_by_ratio_2_plane_complex(self):
        # Case with 2 plane
        middle_position = find_middle_position_by_ratio([0,0,0], [0,1,1], 0.7)
        expected_middle_position = [0,0.7,0.7]
        #self.assertEqual(middle_position, expected_middle_position)

    def test_find_middle_position_by_ratio_3_plane_simple(self):
        # Case with 3 plane
        middle_position = find_middle_position_by_ratio([0,0,0], [1,1,1], 0.5)
        expected_middle_position = [0.5,0.5,0.5]
        #self.assertEqual(middle_position, expected_middle_position)

    def test_find_middle_position_by_ratio_3_plane_complex(self):
        # Case with 3 plane
        middle_position = find_middle_position_by_ratio([0,0,0], [1,1,1], 0.7)
        expected_middle_position = [0.7,0.7,0.7]
        #self.assertEqual(middle_position, expected_middle_position)
