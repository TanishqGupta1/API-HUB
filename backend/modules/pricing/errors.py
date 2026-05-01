"""Per-quote pricing errors. The HTTP layer maps these to 4xx responses."""


class PricingError(Exception):
    """Base for pricing errors that should surface as 4xx, not 5xx."""


class BoundsError(PricingError):
    """Width/height/qty fell outside the bounds declared on the product."""


class MissingPricingDataError(PricingError):
    """Required pricing data (variant, prices, formula) is not on disk."""
