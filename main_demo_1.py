import datetime, sys, os, json
import logging
import logging.config

os.system("rm -f logfile.log")
logging.config.fileConfig("log.ini", disable_existing_loggers=False)
logger = logging.getLogger(__name__)

from src.flight_plan import FlightPlan
from src.flight_plan_meta import FlightPlanMeta
from src.scheduler import Scheduler
from src.simulator import Simulator
from src.tower import Tower
from src.bot_schema import BotSchema
from src.bot import Bot
from src.payload import Payload
from src.payload_schema import PayloadSchema
from src.tools import Encoder
from src.resource_manager import ResourceManager, Resource
from src.resource_tools import construct_flight_plan_meta, get_bot_schema_by_model, get_payload_schema_by_model

"""
This demo creates the raw files for showing the evolution of a single energy deficient flight plan into
a plan with refuel points and refueler sub plans
"""
DEMO_NUMBER = 1

""" Common """
towers = Tower.from_catalogue_file(f"./examples/demo_{DEMO_NUMBER}/towers_1.json")

with open(f"./examples/demo_{DEMO_NUMBER}/bots_1.json", 'r') as f:
    bots_dict = json.load(f)
    bot_schemas_list = bots_dict['bot_models']

bot_schemas = [
    BotSchema.from_dict(schema_dict)
    for schema_dict in bot_schemas_list
]

with open(f'./examples/demo_{DEMO_NUMBER}/towers_1.json', 'r') as f:
    tower_json = json.load(f)

# Create the payload manager
with open(f"./examples/demo_{DEMO_NUMBER}/payloads_1.json", 'r') as f:
    payloads_json = json.load(f)

payload_schemas = [
    PayloadSchema(
        model=payload_model['model'],
        compatable_bots=[
            get_bot_schema_by_model(model, bot_schemas)
            for model in payload_model['compatable_bots']
        ]
    )
    for payload_model in payloads_json['payload_models']
]

payloads = [
    Payload(
        id=payload['id'],
        schema=get_payload_schema_by_model(
            payload['payload_model'],
            payload_schemas
        )
    )
    for payload in payloads_json['payloads']
]

payload_manager = ResourceManager(payloads)

# Create the bot manager
with open(f"./examples/demo_{DEMO_NUMBER}/bots_1.json", 'r') as f:
    bot_json = json.load(f)

bots = [
    Bot(
        id=bot['id'],
        schema=get_bot_schema_by_model(bot['bot_model'], bot_schemas)
    )
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

with open(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json", 'r') as f:
    flight_plan_dict = json.load(f)

scheduler = Scheduler(
    towers=towers,
    bot_schemas=bot_schemas,
    payload_schemas=payload_schemas,
    bot_manager=bot_manager,
    payload_manager=payload_manager,
    refuel_duration=datetime.timedelta(seconds=60),
    remaining_flight_time_at_refuel=datetime.timedelta(seconds=300),
    refuel_anticipation_buffer=datetime.timedelta(seconds=60)
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
logger.info("Part 1")
meta = construct_flight_plan_meta(
    payload_id="1",
    payloads=payloads,
    bots=bots
)
meta.bot_model = get_bot_schema_by_model("GypsyMarkI", bot_schemas) # This shouldnt be needed
assert meta.bot_model is not None

flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json")
flight_plan.set_meta(meta)
scheduler.add_positions_to_action_waypoints(flight_plan)
simulator.simulate_flight_plan(flight_plan)#, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'raw_flight_plan.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'raw_flight_plan.json'), 'w') as f:
    f.write(json.dumps(flight_plan.to_dict(), cls=Encoder))


""" 1) b) Section showing the same flight plan but with refuel points added (without schedule)"""
logger.info("Part 2")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json")
flight_plan.set_meta(meta)
schedule = scheduler.determine_schedule(flight_plan=flight_plan, launch_time=when)
simulator.simulate_flight_plan(flight_plan)#, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'calculated_flight_plan.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', 'calculated_flight_plan.json'), 'w') as f:
    f.write(json.dumps(flight_plan.to_dict(), cls=Encoder))


""" 1) c) Section showing the schedule for the refuelers """
logger.info("Part 3")
flight_plan = FlightPlan.from_file(f"./examples/demo_{DEMO_NUMBER}/flight_plan_1.json")
flight_plan.set_meta(meta)
schedule = scheduler.determine_schedule(flight_plan=flight_plan, launch_time=when)
simulator.simulate_schedule(schedule)#, save_path=os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.mp4'))

with open(os.path.join(dir, 'demo', f'demo_{DEMO_NUMBER}', 'raw', f'schedule.json'), 'w') as f:
    f.write(json.dumps(schedule.to_dict(), cls=Encoder))
