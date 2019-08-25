from dataclasses import dataclass

@dataclass
class FlightPlanMeta:
    """
    A FlightPlanMeta contains the dynamic components of a flight plan
    """
    bot_id: str
    bot_model: str
    payload_id: str
    payload_model: str
