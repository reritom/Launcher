

class Schedule:
    def __init__(self):
        self.schedule = []
        self.applicable = True

    def add(self, time: int, flight_plan):
        self.schedule.append((time, flight_plan))

    def to_dict(self):
        return [
            {
                'time': time,
                'flight_plan': flight_plan.to_dict()
            }
            for time, flight_plan
            in self.schedule
        ]

    def set_unapplicable(self):
        self.applicable = False
