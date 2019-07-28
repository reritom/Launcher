from src.flight_plan import FlightPlan
from src.scheduler import Scheduler
from src.simulator import Simulator
from src.tower import Tower
from src.bot import Bot

import datetime, sys


flight_plan = FlightPlan.from_file("./examples/flight_plan_1.json")
towers = [
    Tower.from_file("./examples/towers/tower_0.json"),
    Tower.from_file("./examples/towers/tower_1.json")
]

bots = Bot.from_catalogue_file("./examples/bots_1.json")

scheduler = Scheduler(towers=towers, bots=bots, refuel_duration=60, remaining_flight_time_at_refuel=300, refuel_anticipation_buffer=60)
when = datetime.datetime.now() + datetime.timedelta(days=1)
schedule = scheduler.determine_schedule_from_launch_time(flight_plan, when)

simulator = Simulator(bots=bots)
#simulator.simulate_flight_plan(flight_plan)
simulator.simulate_schedule(schedule)
#print(flight_plan.to_dict())
