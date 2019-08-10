import math as maths
import json
from typing import List

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
