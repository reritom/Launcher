from src.flight_plan import FlightPlan
from src.scheduler import Scheduler
from src.simulator import Simulator
from src.tower import Tower
from src.bot import Bot
from src.tools import Encoder

import datetime, sys, os, json

"""
This demo creates the raw files for showing the evolution of a single energy deficient flight plan into
a plan with refueler points and refueler sub plans
"""
DEMO_NUMBER = 1

""" Common """
towers = [
    Tower.from_file(f"./examples/demo_{DEMO_NUMBER}/towers/tower_0.json"),
    Tower.from_file(f"./examples/demo_{DEMO_NUMBER}/towers/tower_1.json")
]

bots = Bot.from_catalogue_file(f"./examples/demo_{DEMO_NUMBER}/bots_1.json")
scheduler = Scheduler(towers=towers, bots=bots, refuel_duration=60, remaining_flight_time_at_refuel=300, refuel_anticipation_buffer=60)
simulator = Simulator(bots=bots)
when = datetime.datetime.now() + datetime.timedelta(days=1)

# Prepare the storage
dir = os.path.dirname(os.path.realpath(__file__))

if not f'demo_{DEMO_NUMBER}' in os.listdir(os.path.join(dir, 'demo')):
    os.mkdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}'))

if not 'raw' in os.listdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}')):
    os.mkdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw'))

""" 1) a) Section for showing flight plan running out of fuel """
print("Part 1")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_2.json")
scheduler.add_positions_to_action_waypoints(flight_plan)
simulator.simulate_flight_plan(flight_plan, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'raw_flight_plan.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'raw_flight_plan.json'), 'w') as f:
    f.write(json.dumps(flight_plan.to_dict(), cls=Encoder))


""" 1) b) Section showing the same flight plan but with refuel points added (without schedule)"""
print("Part 2")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_2.json")
schedule = scheduler.determine_schedule_from_launch_time(flight_plan, when)
simulator.simulate_flight_plan(flight_plan, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'calculated_flight_plan.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'calculated_flight_plan.json'), 'w') as f:
    f.write(json.dumps(flight_plan.to_dict(), cls=Encoder))


""" 1) c) Section showing the schedule for the refuelers """
print("Part 3")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_2.json")
schedule = scheduler.determine_schedule_from_launch_time(flight_plan, when)
simulator.simulate_schedule(schedule, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.json'), 'w') as f:
    f.write(json.dumps(schedule.to_dict(), cls=Encoder))
