from rest_framework.throttling import UserRateThrottle


class PurchaseRateThrottle(UserRateThrottle):
    """A tighter limit for the endpoint that spends stock."""

    scope = 'purchase'
