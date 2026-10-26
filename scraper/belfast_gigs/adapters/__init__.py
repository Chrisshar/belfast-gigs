from .base import Adapter, MissingCredentials
from .blackbox import BlackBox
from .citizenticket import CitizenTicket
from .deershead import DeersHead
from .duncairn import Duncairn
from .empire import Empire
from .harrison import Harrison
from .limelight import Limelight
from .mandela import MandelaHall
from .movingon import MovingOnMusic
from .o2belfast import O2Belfast
from .ohyeah import OhYeah
from .ticketmaster import Ticketmaster
from .ulsterhall import UlsterHall
from .usc import UlsterSportsClub
from .voodoo import Voodoo

ADAPTERS: dict[str, type[Adapter]] = {
    a.name: a
    for a in (
        Limelight, O2Belfast, UlsterHall, Empire, UlsterSportsClub, Voodoo, MandelaHall, BlackBox, OhYeah,
        Duncairn, DeersHead, MovingOnMusic,
        Harrison, CitizenTicket, Ticketmaster,
    )
}

__all__ = ["ADAPTERS", "Adapter", "MissingCredentials"]
