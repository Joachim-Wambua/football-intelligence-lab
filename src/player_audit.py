"""Reproduce the playing-time audit on actual local StatsBomb open-data JSON files.

Run: python -m src.player_audit path/to/open-data/data --output docs/player_audit.json
Only an evidence manifest is written; raw match files are never copied into Git.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from src.playing_time import playing_time, period_lengths

AUDITED_IDS = [3895052, 3895060, 8656, 7541]


def audit_match(root: Path, match_id: int) -> dict:
    """Record byte hashes, period boundaries and ID-level support, not inferred minutes.

    Raw documents retain provenance while this small adapter extracts only fields
    needed to verify participation. Provider-period timestamps, explicit IDs and
    lifecycle records are the same inputs used by the flattened statsbombpy source.
    """
    files = {kind: (root / kind / f'{match_id}.json').read_bytes() for kind in ('events', 'lineups')}
    raw_events = json.loads(files['events'])
    rows = []
    for event in raw_events:
        rows.append({'type': event['type']['name'], 'team_id': event['team']['id'],
            'team': event['team']['name'], 'player_id': event.get('player', {}).get('id'),
            'period': event['period'], 'timestamp': event['timestamp'], 'tactics': event.get('tactics'),
            'substitution_replacement_id': event.get('substitution', {}).get('replacement', {}).get('id'),
            'foul_committed_card': event.get('foul_committed', {}).get('card', {}).get('name'),
            'bad_behaviour_card': event.get('bad_behaviour', {}).get('card', {}).get('name')})
    events = pd.DataFrame(rows)
    roster = pd.DataFrame([{'team_id': team['team_id'], 'team': team['team_name'],
        'player_id': player['player_id'], 'positions': player.get('positions'), 'cards': player.get('cards')}
        for team in json.loads(files['lineups']) for player in team['lineup']])
    teams = []
    for team_id in sorted(roster.team_id.unique()):
        timing = playing_time(events, roster, int(team_id))
        teams.append({'team_id': int(team_id), 'team': roster.loc[roster.team_id.eq(team_id), 'team'].iloc[0],
            'verified_appearance_ids': sorted(pid for pid, row in timing.items() if row['minutes_status'] == 'verified'),
            'verified_unused_ids': sorted(pid for pid, row in timing.items() if row['minutes_status'] == 'unused_substitute'),
            'null_minutes': {str(pid): row['minutes_status'] for pid, row in sorted(timing.items()) if row['minutes'] is None}})
    return {'match_id': match_id, 'sha256': {key: hashlib.sha256(value).hexdigest() for key, value in files.items()},
        'period_seconds': period_lengths(events), 'teams': teams}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data_root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audited-on', default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()
    results = {'source': 'https://github.com/statsbomb/open-data', 'audited_on': args.audited_on,
        'policy': 'Elapsed pitch minutes including added time, excluding intervals/shootouts. Null for unsupported temporary absences.',
        'matches': [audit_match(args.data_root, match_id) for match_id in AUDITED_IDS]}
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
