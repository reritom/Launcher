

class Schedule:
    def __init__(self, raw_schedule: dict):
        self.raw_schedule = raw_schedule
        self.schedule = []
        self.applicable = True
        self.flight_plans = self.get_flight_plans_from_raw_schedule(raw_schedule)
        self.flight_plans.sort(key=lambda x: x.start_time, reverse=True)

    def add(self, time: int, flight_plan):
        self.schedule.append((time, flight_plan))

    def to_dict(self):
        return {
            'raw_schedule': self.raw_schedule,
            'flight_plans': [flight_plan.to_dict() for flight_plan in self.flight_plans]
        }

    def set_unapplicable(self):
        self.applicable = False

    def get_flight_plans_from_raw_schedule(self, raw_schedule: dict) -> list:
        """
        A raw schedule is of the following format:
        {
            'flight_plan': <FlightPlan>,
            'related_sub_flight_plans': {
                '<waypoint_id>': [
                    <raw_schedule>
                ],
                ...
            }
        }
        """
        flight_plans = []
        flight_plans.append(raw_schedule['flight_plan'])

        for waypoint_id, list_of_potential_flight_plan_dicts in raw_schedule.get('related_sub_flight_plans', {}).items():
            flight_plans.extend([
                flight_plan
                for potential_flight_plan_dict in list_of_potential_flight_plan_dicts
                for flight_plan in self.get_flight_plans_from_raw_schedule(potential_flight_plan_dict)
            ])

        return flight_plans

    @property
    def start_time(self):
        start_time = self.flight_plans[0].start_time

        if len(self.flight_plans) > 1:
            for flight_plan in self.flight_plans[1:]:
                start_time = (
                    start_time
                    if start_time < flight_plan.start_time
                    else flight_plan.start_time
                )

        return start_time

    @property
    def end_time(self):
        end_time = self.flight_plans[0].end_time

        if len(self.flight_plans) > 1:
            for flight_plan in self.flight_plans[1:]:
                end_time = (
                    end_time
                    if end_time > flight_plan.end_time
                    else flight_plan.end_time
                )

        return end_time

    @property
    def duration(self):
        return (self.end_time - self.start_time).total_seconds()
