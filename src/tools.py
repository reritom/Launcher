import math as maths
import json

def distance_between(position_a, position_b):
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

class Encoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return obj.to_dict()
        except:
            return super().default(obj)
