import math as maths

def distance_between(position_a, position_b):
    return maths.sqrt(
        abs(position_a[0] - position_b[0])**2
        + abs(position_a[1] - position_b[1])**2
        + abs(position_a[2] - position_b[2])**2
    )
