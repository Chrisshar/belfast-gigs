from .base import Adapter, MissingCredentials
from .citizenticket import CitizenTicket
from .harrison import Harrison
from .limelight import Limelight
from .o2belfast import O2Belfast
from .ticketmaster import Ticketmaster

ADAPTERS: dict[str, type[Adapter]] = {a.name: a for a in (Limelight, O2Belfast, Harrison, CitizenTicket, Ticketmaster)}

__all__ = ["ADAPTERS", "Adapter", "MissingCredentials"]
