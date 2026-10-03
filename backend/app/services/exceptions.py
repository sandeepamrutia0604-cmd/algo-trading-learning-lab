class TradingError(Exception):
    """Base class for errors that should surface as a 400 response."""


class StockNotFoundError(TradingError):
    pass


class InvalidQuantityError(TradingError):
    pass


class InsufficientFundsError(TradingError):
    pass


class InsufficientSharesError(TradingError):
    pass


class StrategyNotFoundError(TradingError):
    pass


class InvalidStrategyError(TradingError):
    pass


class InvalidStockError(TradingError):
    """A practice stock that can't be created or deleted (bad symbol, name taken, still in use...)."""
