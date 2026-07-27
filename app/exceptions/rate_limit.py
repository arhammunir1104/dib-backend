class RateLimitException(Exception):
    """Raised when the LLM rate limit is exhausted."""
    pass