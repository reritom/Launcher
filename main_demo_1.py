from src.flight_plan import FlightPlan
from src.scheduler import Scheduler
from src.simulator import Simulator
from src.tower import Tower
from src.bot_schema import BotSchema
from src.bot import Bot
from src.payload import Payload
from src.payload_schema import PayloadSchema
from src.tools import Encoder
from src.resource_manager import ResourceManager, Resource
import datetime, sys, os, json

"""
This demo creates the raw files for showing the evolution of a single energy deficient flight plan into
a plan with refuel points and refueler sub plans
"""
DEMO_NUMBER = 1

""" Common """
towers = Tower.from_catalogue_file(f"./examples/demo_{DEMO_NUMBER}/towers_1.json")
bot_schemas = BotSchema.from_catalogue_file(f"./examples/demo_{DEMO_NUMBER}/bots_1.json")

with open(f'./examples/demo_{DEMO_NUMBER}/towers_1.json', 'r') as f:
    tower_json = json.load(f)

# Create the payload manager
with open(f"./examples/demo_{DEMO_NUMBER}/payloads_1.json", 'r') as f:
    payloads_json = json.load(f)

payloads = [
    Payload(id=payload['id'], schema=payload['payload_model'])
    for payload in payloads_json['payloads']
]

payload_manager = ResourceManager(payloads)

# The payloads need an initial allocation for location context coming from the Tower jsons
payload_schemas = [
    PayloadSchema(id=payload_model['id'], compatable_bots=payload_model['compatable_bots'])
    for payload_model in payloads_json['payload_models']
]

# Create the bot manager
with open(f"./examples/demo_{DEMO_NUMBER}/bots_1.json", 'r') as f:
    bot_json = json.load(f)

bots = [
    Bot(id=bot['id'], schema=bot['bot_model'])
    for bot in bot_json['bots']
]

bot_manager = ResourceManager(bots)

# The BotManager and PayloadManager need their trackers initialised using the data from the tower_json
# which says the initial inventory of each tower
for tower in tower_json:
    for bot_id in tower.get('initial_bots', []):
        bot_manager.set_tracker(bot_id, {"tower_id": tower['id']})

    for payload_id in tower.get('initial_payloads', []):
        payload_manager.set_tracker(payload_id, {"tower_id": tower['id']})


scheduler = Scheduler(
    towers=towers,
    bot_schemas=bot_schemas,
    payload_schemas=payload_schemas,
    bot_manager=bot_manager,
    payload_manager=payload_manager,
    refuel_duration=60,
    remaining_flight_time_at_refuel=300,
    refuel_anticipation_buffer=60
)

simulator = Simulator(towers=towers, bot_schemas=bot_schemas)
when = datetime.datetime.now() + datetime.timedelta(days=1)

# Prepare the storage
dir = os.path.dirname(os.path.realpath(__file__))

if not f'demo_{DEMO_NUMBER}' in os.listdir(os.path.join(dir, 'demo')):
    os.mkdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}'))

if not 'raw' in os.listdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}')):
    os.mkdir(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw'))

""" 1) a) Section for showing flight plan running out of fuel """
print("Part 1")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json")
scheduler.add_positions_to_action_waypoints(flight_plan)
simulator.simulate_flight_plan(flight_plan)#, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'raw_flight_plan.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'raw_flight_plan.json'), 'w') as f:
    f.write(json.dumps(flight_plan.to_dict(), cls=Encoder))


""" 1) b) Section showing the same flight plan but with refuel points added (without schedule)"""
print("Part 2")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json")
schedule = scheduler.determine_schedule_from_launch_time(flight_plan, when)
simulator.simulate_flight_plan(flight_plan)#, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'calculated_flight_plan.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'calculated_flight_plan.json'), 'w') as f:
    f.write(json.dumps(flight_plan.to_dict(), cls=Encoder))


""" 1) c) Section showing the schedule for the refuelers """
print("Part 3")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json")
schedule = scheduler.determine_schedule_from_launch_time(flight_plan, when)
simulator.simulate_schedule(schedule)#, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.json'), 'w') as f:
    f.write(json.dumps(schedule.to_dict(), cls=Encoder))
