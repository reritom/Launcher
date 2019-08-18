from dataclasses import dataclass

from .payload_schema import PayloadSchema

@dataclass
class Payload:
    """
    A payload is directly related to a physical payload object.
    A payload is effectively an instance of a payload schema
    """
    id: str
    schema: PayloadSchema
    #added: datetime.datetime
