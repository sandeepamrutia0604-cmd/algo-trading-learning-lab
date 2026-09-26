from .base import StrategyDef
from .bollinger_bands import BOLLINGER_BANDS
from .breakout import BREAKOUT
from .combined import COMBINED
from .ma_crossover import MA_CROSSOVER
from .mean_reversion import MEAN_REVERSION
from .rsi_reversal import RSI_REVERSAL

STRATEGY_TYPES: dict[str, StrategyDef] = {
    d.key: d for d in (MA_CROSSOVER, RSI_REVERSAL, BOLLINGER_BANDS, BREAKOUT, MEAN_REVERSION, COMBINED)
}


def get_definition(key: str) -> StrategyDef:
    definition = STRATEGY_TYPES.get(key)
    if definition is None:
        raise ValueError(f"Unknown strategy type: {key}")
    return definition


def list_definitions() -> list[StrategyDef]:
    return list(STRATEGY_TYPES.values())
