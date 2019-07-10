from src.flight_plan import FlightPlan
from src.scheduler import Scheduler
from src.simulator import Simulator


flight_plan = FlightPlan.from_file("./examples/flight_plan_1.json")

scheduler = Scheduler.from_config_file("./examples/configuration_1.json")
schedule = scheduler.determine_schedule(flight_plan)

simulator = Simulator()
simulator.simulate_schedule(schedule)
