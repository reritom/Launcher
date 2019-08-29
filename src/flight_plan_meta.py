from dataclasses import dataclass, field

@dataclass
class FlightPlanMeta:
    """
    A FlightPlanMeta contains the dynamic components of a flight plan
    """
    bot_id: str = field(default_factory=lambda: None)
    bot_model: str = field(default_factory=lambda: None)
    payload_id: str = field(default_factory=lambda: None)
    payload_model: str = field(default_factory=lambda: None)
