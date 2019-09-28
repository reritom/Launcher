import math as maths
import json
from decimal import Decimal
from typing import List
import datetime

class ScheduleError(Exception):
    pass

class TrackerError(Exception):
    pass

def without_microseconds(delta: datetime.timedelta) -> datetime.timedelta:
    """
    For a given timedelta object remove the microseconds
    """
    if isinstance(delta, datetime.timedelta):
        return datetime.timedelta(seconds=round(delta.total_seconds()))
    else:
        microseconds = delta.microsecond
        without = delta - datetime.timedelta(microseconds=microseconds)
        if microseconds > 500000:
            without = without + datetime.timedelta(seconds=1)
        return without

def distance_between(position_a: tuple, position_b: tuple) -> tuple:
    return maths.sqrt(
        abs(position_a[0] - position_b[0])**2
        + abs(position_a[1] - position_b[1])**2
        + abs(position_a[2] - position_b[2])**2
    )

def find_middle_position_by_ratio(position_a, position_b, ratio):
    return [
        position_a[i] + (position_b[i] - position_a[i]) * ratio
        for i in [0, 1, 2]
    ]

def get_path(starting_position: tuple, ending_position: tuple, available_positions: List[tuple]) -> List[tuple]:
    """
    This function is an A* implementation to determine the shortest path between 3 dimensional cartesian coordinates
    """
    pass

class Encoder(json.JSONEncoder):
    """
    An encoder class to be passed into json.dumps that calls to_dict on any nested objects if that method is available

    Consumed like:
    dumped = json.dumps(dict_to_dump, cls=Encoder)
    """
    def default(self, obj):
        try:
            return obj.to_dict()
        except:
            return super().default(obj)
