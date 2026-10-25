"""Conservative event-lifecycle playing time, independent of API and plotting."""
from math import isfinite

import pandas as pd

NOMINAL_SECONDS = {1: 2700, 2: 2700, 3: 900, 4: 900}
MINUTES_PROVENANCE = (
    "StatsBomb Starting XI + substitution replacement IDs + dismissal events + "
    "period-relative timestamps and Half Start/Half End; elapsed pitch time including "
    "added time, excluding intervals and shootouts. Temporary off/on spells are unsupported."
)


def clock_seconds(value: object) -> float:
    """Parse provider HH:MM:SS.sss; reject absent, negative and malformed clocks."""
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError("Expected HH:MM:SS timestamp")
    hours, minutes, seconds = map(float, parts)
    if not all(isfinite(x) for x in (hours, minutes, seconds)) or hours < 0 or hours != int(hours) or not 0 <= minutes < 60 or minutes != int(minutes) or not 0 <= seconds < 60:
        raise ValueError("Invalid timestamp")
    return hours * 3600 + minutes * 60 + seconds


def period_lengths(events: pd.DataFrame) -> dict[int, float]:
    """Require complete regulation periods and, if present, both extra-time halves.

    Timestamps restart each half, so 45:00 on the match clock cannot simply be
    subtracted from a first-half stoppage-time endpoint. Two team Half Ends can
    differ slightly (audited maximum 0.28 seconds); take their maximum only when
    they agree within one second. No on-ball event is used to infer a whistle.
    Abandoned, missing or conflicting periods fail closed rather than assuming 90.
    """
    if events.period.isna().any() or not events.period.isin([1, 2, 3, 4, 5]).all():
        raise ValueError("Invalid period identifiers")
    periods = set(events.period.astype(int)) - {5}
    expected = [1, 2, 3, 4] if periods & {3, 4} else [1, 2]
    if periods != set(expected):
        raise ValueError("Missing or unsupported periods")
    lengths = {}
    for period in expected:
        half = events.loc[events.period.eq(period)]
        starts = [clock_seconds(t) for t in half.loc[half.type.eq("Half Start"), "timestamp"]]
        ends = [clock_seconds(t) for t in half.loc[half.type.eq("Half End"), "timestamp"]]
        if not starts or min(starts) > 1 or not ends or max(ends) - min(ends) > 1 or max(ends) < NOMINAL_SECONDS[period]:
            raise ValueError("Missing, short or conflicting period boundaries")
        lengths[period] = max(ends)
    return lengths


def playing_time(events: pd.DataFrame, lineups: pd.DataFrame, team_id: int) -> dict[int, dict]:
    """Return minutes, appearance and status by numeric player ID, including benches.

    Minutes are sums of explicit active intervals on a cumulative elapsed-pitch
    timeline. Example: first half 47 minutes, second half 49; a halftime substitute
    plays 49, not 51 or an inferred 45. A red card at 02:48.560 gives 2.8093
    elapsed minutes. A verified unused substitute has zero minutes and False
    appearance. Missing roster/clock/lifecycle yields null and an explanatory
    status. Names never determine identity; touches never define playing-time intervals.

    Temporary absences (including off-camera returns) are deliberately unrated:
    their treatment is not silently conflated with substitution minutes. Position
    histories are retained elsewhere as provider observations, not timed estimates.
    """
    team_events = events.loc[events.team_id.eq(team_id)]
    roster = lineups.loc[lineups.team_id.eq(team_id)] if "team_id" in lineups else pd.DataFrame()
    identities = set(int(v) for v in team_events.get("player_id", pd.Series(dtype=float)).dropna())
    confirmed = set(int(v) for v in team_events.loc[team_events.type.isin(
        ["Pass", "Shot", "Carry", "Dribble", "Interception", "Pressure", "Ball Receipt*"])
        & ~team_events.get("period", pd.Series(index=team_events.index, dtype=float)).eq(5),
        "player_id"].dropna()) if "player_id" in team_events else set()
    for _, row in team_events.iterrows():
        if row.get("period") == 5:
            continue
        if row.type == "Starting XI" and isinstance(row.get("tactics"), dict):
            starters = [int(item["player"]["id"]) for item in row.tactics.get("lineup", [])]
            if len(starters) == 11 and len(set(starters)) == 11:
                identities.update(starters)
                confirmed.update(starters)
        if row.type == "Substitution" and pd.notna(row.get("substitution_replacement_id")):
            replacement = int(row.substitution_replacement_id)
            identities.add(replacement)
            confirmed.add(replacement)
    if "player_id" in roster:
        identities.update(int(v) for v in roster.player_id.dropna())
    def unknown(status):
        return {player_id: {"minutes": None, "appeared": True if player_id in confirmed else None, "minutes_status": status} for player_id in identities}
    if roster.empty:
        return unknown("lineups_unavailable")
    if "player_id" not in roster or roster.player_id.isna().any() or roster.player_id.duplicated().any():
        return unknown("invalid_roster_ids")
    try:
        lengths = period_lengths(events)
        offsets = {period: sum(length for p, length in lengths.items() if p < period) for period in lengths}
        end = sum(lengths.values())
        def elapsed(row):
            period = int(row["period"])
            seconds = clock_seconds(row.get("timestamp"))
            if period not in lengths or seconds > lengths[period] + 1:
                raise ValueError("Event outside period")
            return offsets[period] + min(seconds, lengths[period])
        starting = team_events.loc[team_events.type.eq("Starting XI")]
        if len(starting) != 1:
            return unknown("starting_xi_unavailable")
        if int(starting.iloc[0].period) != 1 or clock_seconds(starting.iloc[0].timestamp) > 1:
            return unknown("invalid_starting_xi_timestamp")
        starters = [int(item["player"]["id"]) for item in starting.iloc[0].tactics["lineup"]]
        roster_ids = set(int(v) for v in roster.player_id)
        if len(starters) != 11 or len(set(starters)) != 11 or not set(starters) <= roster_ids:
            return unknown("invalid_starting_xi")
        active = {player_id: 0.0 for player_id in starters}
        intervals = {player_id: [] for player_id in identities}
        dismissed = set()
        controls = []
        for _, row in team_events.iterrows():
            red = str(row.get("foul_committed_card")) in ("Red Card", "Second Yellow") or str(row.get("bad_behaviour_card")) in ("Red Card", "Second Yellow")
            if row.type == "Substitution" or red:
                if row.get("period") == 5:
                    continue
                controls.append((elapsed(row), row, red))
        for time, row, red in sorted(controls, key=lambda item: item[0]):
            player_id = int(row.player_id)
            if row.type == "Substitution":
                replacement = int(row.substitution_replacement_id)
                if player_id not in active or replacement in active or replacement not in roster_ids or intervals[replacement] or replacement in dismissed:
                    raise ValueError("Conflicting substitution IDs")
                intervals[player_id].append((active.pop(player_id), time))
                active[replacement] = time
            elif red:
                dismissed.add(player_id)
                if player_id in active:  # A bench dismissal does not remove a pitch player.
                    intervals[player_id].append((active.pop(player_id), time))
        for player_id, start in active.items():
            intervals[player_id].append((start, end))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return unknown("incomplete_or_conflicting_lifecycle")
    result = {}
    for player_id in identities:
        spans = intervals[player_id]
        own = team_events.loc[team_events.get("player_id", pd.Series(index=team_events.index, dtype=float)).eq(player_id)]
        positions = roster.loc[roster.player_id.eq(player_id), "positions"].iloc[0] if player_id in roster_ids and "positions" in roster else []
        temporary = own.type.isin(["Player Off", "Player On"]).any() or isinstance(positions, list) and any("Player Off" in str(p.get("end_reason")) or "Player On" in str(p.get("start_reason")) for p in positions)
        status = "verified" if spans else "unused_substitute"
        if player_id not in roster_ids:
            status = "player_missing_from_roster"
        elif temporary:
            status = "temporary_absence_unsupported"
        else:
            try:
                # Events outside a verified active spell expose missing lifecycle
                # information; they never become a substitute for that information.
                for _, row in own.loc[~own.period.eq(5)].iterrows():
                    if row.type in ("Bad Behaviour", "Player Off", "Player On"):
                        continue
                    time = elapsed(row)
                    if not any(start - 1 <= time <= stop + 1 for start, stop in spans):
                        status = "events_outside_active_interval"
                # Nonempty provider position history is direct evidence of
                # participation even for a no-touch substitute. It must never be
                # labelled an unused bench appearance when its entry is missing.
                if isinstance(positions, list) and positions:
                    first_reason = str(positions[0].get("start_reason", ""))
                    last_reason = str(positions[-1].get("end_reason", ""))
                    if not spans or first_reason == "Starting XI" and player_id not in starters:
                        status = "lineup_lifecycle_conflict"
                    if "Substitution - Off" in last_reason and player_id in active:
                        status = "substitution_event_missing"
                    if "Red Card" in last_reason and player_id not in dismissed:
                        status = "dismissal_event_missing"
                cards = roster.loc[roster.player_id.eq(player_id), "cards"].iloc[0] if "cards" in roster else []
                if isinstance(cards, list) and any(card.get("card_type") in ("Red Card", "Second Yellow") for card in cards) and player_id not in dismissed:
                    status = "dismissal_event_missing"
            except (ValueError, TypeError, KeyError):
                status = "invalid_player_timestamp"
        valid = status in ("verified", "unused_substitute") and all(0 <= start <= stop <= end for start, stop in spans)
        result[player_id] = {"minutes": sum(stop - start for start, stop in spans) / 60 if valid else None,
            "appeared": bool(spans) if valid else True if spans or player_id in confirmed else None,
            "minutes_status": status if valid or status not in ("verified", "unused_substitute") else "invalid_minutes"}
    return result
