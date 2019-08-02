from src.flight_plan import FlightPlan
from src.scheduler import Scheduler
from src.simulator import Simulator
from src.tower import Tower
from src.bot import Bot
from src.tools import Encoder

import datetime, sys, os, json

"""
This demo shows a schedule for a bot being refueled by multiple towers
"""
DEMO_NUMBER = 2

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
print("Part 1")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json")
schedule = scheduler.determine_schedule_from_launch_time(flight_plan, when)
simulator.simulate_schedule(schedule)#, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.json'), 'w') as f:
    f.write(json.dumps(schedule.to_dict(), cls=Encoder))
