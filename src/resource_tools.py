from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

from .payload import Payload
from .payload_schema import PayloadSchema
from .flight_plan_meta import FlightPlanMeta
from .bot import Bot
from .bot_schema import BotSchema

def print_waypoints(flight_plan):
    logger.debug("Print waypoints")
    for waypoint in flight_plan.waypoints:
        logger.debug(repr(waypoint))
    logger.debug("End of printing waypoints")

def get_payload_by_id(id: str, payloads: List[Payload]) -> Optional[Payload]:
    """
    For a given list of payloads, return the payload with the given id
    """
    for payload in payloads:
        if payload.id == id:
            return payload

def get_bot_by_id(id: str, bots: List[Bot]) -> Optional[Bot]:
    """
    For a given list of bots, return the bot with the given id
    """
    for bot in bots:
        if bot.id == id:
            return bot

def get_bot_schema_by_model(model: str, schemas: List[BotSchema]) -> Optional[BotSchema]:
    """
    For a given list of bot schemas, return the bot schema for the given model name
    """
    for schema in schemas:
        if schema.model == model:
            return schema

def get_payload_schema_by_model(model: str, schemas: List[PayloadSchema]) -> Optional[PayloadSchema]:
    """
    For a given list of payload schemas, return the payload schema for the given model
    """
    for schema in schemas:
        if schema.model == model:
            return schema

def construct_flight_plan_meta(
    payload_id: str = None,
    payload_model: str = None,
    payloads: List[Payload] = None,
    bot_id: str = None,
    bot_model: str = None,
    bots: List[Bot] = None
    ) -> FlightPlanMeta:
    """
    For given parameters, attempt to construct the most complete FlightPlanMeta
    """
    assert isinstance(payloads, list)
    assert isinstance(bots, list)

    if payload_id and not payload_model:
        payload_model = get_payload_by_id(payload_id, payloads).schema.model

    if bot_id and not bot_model:
        bot_model = get_bot_by_id(bot_id, bots).schema.model

    return FlightPlanMeta(
        payload_id=payload_id,
        payload_model=payload_model,
        bot_id=bot_id,
        bot_model=bot_model
    )
