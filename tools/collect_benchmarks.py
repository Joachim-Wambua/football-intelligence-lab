"""Explicit network audit/collection. Pin an upstream revision, never run in HTTP.

python tools/collect_benchmarks.py --cache research/benchmarks/raw --output docs/benchmark_catalogue.json
Inventories every catalogue and tree entry; downloads all 2023 Women's World Cup
events/lineups for deep inspection by src.benchmark_prepare. Other catalogues'
file presence is tree evidence, not a claim that their contents were validated.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import gzip
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


def fetch(url):
    """Retry transient public-host failures; do not classify them as absent data."""
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'football-intelligence-audit'}), timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(attempt + 1)


def collect(cache, output, revision=None):
    """Separate catalogue-level evidence from fully downloaded content evidence."""
    revision = revision or json.loads(fetch('https://api.github.com/repos/statsbomb/open-data/commits/master'))['sha']
    base = f'https://raw.githubusercontent.com/statsbomb/open-data/{revision}/'
    tree_bytes = fetch(f'https://api.github.com/repos/statsbomb/open-data/git/trees/{revision}?recursive=1')
    tree = json.loads(tree_bytes)
    if tree.get('truncated'):
        raise ValueError('Truncated upstream inventory')
    paths = {entry['path'] for entry in tree['tree']}
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    revision_file = cache / 'revision.txt'
    reuse = revision_file.exists() and revision_file.read_text() == revision
    revision_file.write_text(revision)
    def download(path):
        local = cache / path.removeprefix('data/')
        compressed = path.startswith('data/events/')
        if compressed:
            local = local.with_suffix('.json.gz')
            if reuse and local.exists():
                try:
                    content = gzip.decompress(local.read_bytes())
                    json.loads(content)
                    return content
                except (OSError, ValueError, EOFError):
                    pass
        content = fetch(base + path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(gzip.compress(content, mtime=0) if compressed else content)
        return content
    competitions_bytes = download('data/competitions.json')
    competitions = json.loads(competitions_bytes)
    def inventory(pair):
        path = f"data/matches/{pair['competition_id']}/{pair['season_id']}.json"
        content = download(path)
        matches = json.loads(content)
        team_counts = {}
        for match in matches:
            for side in ('home', 'away'):
                team_id = match[f'{side}_team'][f'{side}_team_id']
                team_counts[str(team_id)] = team_counts.get(str(team_id), 0) + 1
        missing = {kind: sorted(row['match_id'] for row in matches
                               if f"data/{kind}/{row['match_id']}.json" not in paths)
                   for kind in ('events', 'lineups')}
        return {**pair, 'catalogue_sha256': hashlib.sha256(content).hexdigest(),
            'available_matches': len(matches), 'teams': len(team_counts),
            'team_match_counts': dict(sorted(team_counts.items())), 'missing_tree_files': missing,
            'players': None, 'lineup_completeness': 'not_content_audited',
            'match_ids': sorted(row['match_id'] for row in matches)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        inventory_rows = list(pool.map(inventory, competitions))
    selected = next(row for row in inventory_rows if row['competition_id'] == 72 and row['season_id'] == 107)
    selected_paths = [f'data/{kind}/{mid}.json' for mid in selected['match_ids'] for kind in ('events', 'lineups')
                      if f'data/{kind}/{mid}.json' in paths]
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(download, selected_paths))
    for path in ('README.md', 'LICENSE.pdf'):
        download(path)
    result = {'source': 'https://github.com/statsbomb/open-data', 'upstream_revision': revision,
        'tree_sha256': hashlib.sha256(tree_bytes).hexdigest(),
        'competitions_sha256': hashlib.sha256(competitions_bytes).hexdigest(),
        'terms_sha256': {name: hashlib.sha256((cache / name).read_bytes()).hexdigest()
                         for name in ('README.md', 'LICENSE.pdf')},
        'selected_content_audit': {'competition_id': 72, 'season_id': 107},
        'catalogues': inventory_rows}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(f'Inventoried {len(inventory_rows)} pairs at {revision}; collected {len(selected_paths)} match files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revision')
    args = parser.parse_args()
    collect(args.cache, args.output, args.revision)
