"""Domain exceptions raised across the package (never return None/sentinels)."""


class DataUnavailableError(Exception):
    """A required data artifact (file, panel, description) is missing or unreadable."""


class ModelConfigError(Exception):
    """A configuration or registry lookup is invalid (unknown/duplicate component)."""


class LeakageError(Exception):
    """A target or feature would leak post-report information into a prediction."""
