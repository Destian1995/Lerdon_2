"""Shared coup probabilities at the current loyalty values."""


def coup_probabilities(loyalty, disloyal_count):
    """Return (attempt, success given attempt) for one active adviser.

    disloyal_count includes this adviser and all active advisers below 30.
    These probabilities describe a coup check at unchanged loyalty values.
    """
    if loyalty is None or disloyal_count < 1 or loyalty >= 30:
        return 0.0, 0.0
    loyalty = max(0.0, loyalty)
    if disloyal_count >= 2:
        return (30 - loyalty) / 30, 0.5
    if loyalty < 15:
        return (15 - loyalty) / 15, 0.3
    return 0.0, 0.0


def council_coup_probabilities(loyalties):
    """One coup check per turn: probability that at least one adviser initiates it.

    Each eligible adviser has the personal initiation probability shown in
    their card. An attempt happens if any of those independent risks triggers.
    """
    loyalties = [loyalty for loyalty in loyalties if loyalty is not None]
    disloyal_count = sum(loyalty < 30 for loyalty in loyalties)
    no_attempt = 1.0
    success_chance = 0.0
    for loyalty in loyalties:
        attempt, success = coup_probabilities(loyalty, disloyal_count)
        no_attempt *= 1 - attempt
        success_chance = max(success_chance, success)
    return 1 - no_attempt, success_chance
