"""Shared coup probabilities at the current loyalty values."""


def coup_probabilities(loyalty, disloyal_count):
    """Return (attempt, success given attempt) for one active adviser.

    disloyal_count includes this adviser and all active advisers below 30.
    These probabilities describe a coup check at unchanged loyalty values.
    """
    if loyalty is None or loyalty >= 30:
        return 0.0, 0.0
    if disloyal_count >= 2:
        return 1.0, 0.5
    if loyalty < 15:
        return 1.0, 0.3
    return 0.0, 0.0
