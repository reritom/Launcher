from src.flight_plan import FlightPlan
from src.scheduler import Scheduler
from src.simulator import Simulator
from src.tower import Tower

import datetime


flight_plan = FlightPlan.from_file("./examples/flight_plan_1.json")
towers = [
    Tower.from_file("./examples/towers/tower_0.json"),
    Tower.from_file("./examples/towers/tower_1.json")
]

scheduler = Scheduler(towers=towers, refuel_duration=60, remaining_flight_time_at_refuel=300)
when = datetime.datetime.now() + datetime.timedelta(days=1)
schedule = scheduler.determine_schedule_from_launch_time(flight_plan, when)

simulator = Simulator()
simulator.simulate_schedule(schedule)
