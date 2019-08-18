from src.flight_plan import FlightPlan
from src.partial_flight_plan import PartialFlightPlan
from src.scheduler import Scheduler
from src.simulator import Simulator
from src.tower import Tower
from src.bot import Bot
from src.tools import Encoder

import datetime, sys, os, json

"""
This demo shows a schedule for an orchestration
"""
DEMO_NUMBER = 5

""" Common """
towers = Tower.from_catalogue_file(f"./examples/demo_{DEMO_NUMBER}/towers_1.json")
bots = Bot.from_catalogue_file(f"./examples/demo_{DEMO_NUMBER}/bots_1.json")
scheduler = Scheduler(towers=towers, bots=bots, refuel_duration=60, remaining_flight_time_at_refuel=300, refuel_anticipation_buffer=60)
simulator = Simulator(towers=towers, bots=bots)
when = datetime.datetime.now() + datetime.timedelta(days=1)

# Prepare the storage
dir = os.path.dirname(os.path.realpath(__file__))

if not f'demo_{DEMO_NUMBER}' in os.listdir(os.path.join(dir, 'demo')):
    os.mkdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}'))

if not 'raw' in os.listdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}')):
    os.mkdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw'))


""" 1) a) Section showing the schedule """
# Read the raw orchestration
with open(f"./examples/demo_{DEMO_NUMBER}/orchestration.json", 'r') as f:
    orchestration_dict = json.load(f)

# Create the partial flight plans
partial_flight_plans = [
    PartialFlightPlan.from_dict(partial_flight_plan_dict)
    for partial_flight_plan_dict
    in orchestration_dict['partial_flight_plans']
]

schedule = scheduler.determine_schedule_for_partial_flight_plans_orchestration(partial_flight_plans, when)
print(f"There are {len(schedule.flight_plans)} flight plans")
"""
simulator.simulate_schedule(schedule, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.json'), 'w') as f:
    f.write(json.dumps(schedule.to_dict(), cls=Encoder))
"""
