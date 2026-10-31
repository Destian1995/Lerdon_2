"""Truthful battle replay/statistics transforms; no UI and no combat randomness."""


def side_name(value):
    return {'attacker': 'attacking', 'defender': 'defending',
            'attacking': 'attacking', 'defending': 'defending'}.get(value)


def player_side(user, attacking, defending):
    if user and user == attacking:
        return 'attacking'
    if user and user == defending:
        return 'defending'
    return None


def result_caption(winner, user, attacking, defending):
    side = player_side(user, attacking, defending)
    if side is None:
        return 'СРАЖЕНИЕ ЗАВЕРШЕНО', None
    won = side == side_name(winner)
    return ('ПОБЕДА' if won else 'ПОРАЖЕНИЕ'), won


def replay_frames(rounds, limit=18):
    """Condense long battles, preserving real round ranges and summed events."""
    if not rounds:
        return []
    if limit < 2:
        raise ValueError('Replay limit must preserve first and final rounds')
    count = len(rounds)
    indices = list(range(count)) if count <= limit else sorted({round(i * (count - 1) / (limit - 1)) for i in range(limit)})
    frames, previous_index = [], -1
    previous_atk = max(0, rounds[0].get('atk_max', 0))
    previous_def = max(0, rounds[0].get('def_max', 0))
    for index in indices:
        group = rounds[previous_index + 1:index + 1]
        record = dict(rounds[index])
        record['from_round'] = group[0].get('round', previous_index + 2)
        record['round'] = record.get('round', index + 1)
        record['atk_loss'] = max(0, previous_atk - record.get('atk_total', 0))
        record['def_loss'] = max(0, previous_def - record.get('def_total', 0))
        record['atk_crits'] = sum(row.get('atk_crits', 0) for row in group)
        record['def_crits'] = sum(row.get('def_crits', 0) for row in group)
        record['heroes'] = [hero for row in group for hero in row.get('heroes', [])]
        frames.append(record)
        previous_atk, previous_def = record.get('atk_total', 0), record.get('def_total', 0)
        previous_index = index
    return frames


def army_summary(rows):
    initial = sum(max(0, row.get('initial_count', 0)) for row in rows)
    remaining = sum(max(0, row.get('final_count', 0)) for row in rows)
    def permanent(row):
        fallback = max(0, row.get('losses', 0) - row.get('healed', 0)) if 'losses' in row else max(0, row.get('initial_count', 0) - row.get('final_count', 0))
        return max(0, row.get('net_losses', fallback))
    return dict(initial=initial, remaining=remaining,
                battle_losses=sum(max(0, row.get('losses', 0)) for row in rows),
                recovered=sum(max(0, row.get('healed', 0)) for row in rows),
                net_losses=sum(permanent(row) for row in rows),
                reinforcements=sum(max(0, row.get('reinforcements',
                    row.get('final_count', 0) - row.get('initial_count', 0) + permanent(row))) for row in rows),
                survival=remaining / initial if initial else 0)


def report_result(rows, user, attacking, defending):
    side = player_side(user, attacking, defending)
    if side is None:
        return 'ИТОГИ СРАЖЕНИЯ', None
    result = next((row.get('result') for row in rows if row.get('side') == side and row.get('result')), None)
    if result is None:
        return 'ИТОГИ СРАЖЕНИЯ', None
    won = str(result).lower() in ('победа', 'victory')
    return ('ПОБЕДА' if won else 'ПОРАЖЕНИЕ'), won
