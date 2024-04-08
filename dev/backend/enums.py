from enum import Enum

class RolesEnum(Enum):
    GUESSER = 'GUESSER'
    MASTERMIND = 'MASTERMIND'

class GameStatusEnum(Enum):
    STARTED = 'STARTED'
    WAITING = 'WAITING'
    FINISHED = 'FINISHED'

class GameTypeEnum(Enum):
    SINGLE = 'SINGLE'
    MULTIPLAYER = 'MULTIPLAYER'
