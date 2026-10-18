"""Offline empirical xT. See docs/expected_threat.md for model assumptions."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from numbers import Real
import numpy as np
import pandas as pd

SHOT_OUTCOMES = frozenset(('Goal', 'Saved', 'Off T', 'Post', 'Blocked', 'Wayward',
                           'Saved Off Target', 'Saved to Post'))


def _missing(value):
    """Recognize scalar missing values without truth-testing arrays or pd.NA."""
    return value is None or value is pd.NA or (
        isinstance(value, Real) and np.isnan(value))


@dataclass(frozen=True)
class XTConfig:
    nx: int = 16
    ny: int = 12
    tolerance: float = 1e-10
    max_iterations: int = 10000

    def __post_init__(self):
        for v in (self.nx, self.ny, self.max_iterations):
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                raise ValueError('Grid sizes and iteration limit must be positive integers')
        if isinstance(self.tolerance, bool) or not isinstance(self.tolerance, Real) or not np.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError('Tolerance must be finite and positive')


def zone(location, config=XTConfig(), direction='right'):
    """Row-major zone; closed pitch edges clip to last cell. Invalid -> None.

    Direction is explicit, never inferred from home/away or period. A leftward
    input is rotated 180 degrees, including its lateral coordinate.
    """
    if direction not in ('right', 'left'):
        raise ValueError('Explicit right or left attacking direction required')
    if not isinstance(location, (list, tuple)) or len(location) != 2:
        return None
    if any(isinstance(v, bool) or not isinstance(v, Real) or not np.isfinite(v) for v in location):
        return None
    x, y = location
    if not (0 <= x <= 120 and 0 <= y <= 80):
        return None
    if direction == 'left':
        x, y = 120-x, 80-y
    return min(int(y / 80 * config.ny), config.ny-1)*config.nx + min(int(x / 120 * config.nx), config.nx-1)


def extract_actions(events, config=XTConfig(), direction='right'):
    """Extract flattened StatsBomb events, retaining invalid rows for diagnostics.

    Pass outcome missing/null means complete. Carries represent observed ball
    movement, not attempted dribbles; use carry_end_location, never next event.
    Unknown shot outcomes and shootout period 5 are ineligible.
    """
    if direction not in ('right', 'left'):
        raise ValueError('Explicit right or left attacking direction required')
    if not events.empty and 'type' not in events:
        raise ValueError('Expected flattened StatsBomb event type column')
    rows = []
    for position, e in enumerate(events.to_dict(orient='records')):
        kind = e.get('type')
        if not isinstance(kind, str) or kind not in ('Shot', 'Pass', 'Carry'):
            continue
        if not _missing(e.get('period')) and e.get('period') == 5:
            continue
        outcome = e.get('shot_outcome')
        known_shot = isinstance(outcome, str) and outcome in SHOT_OUTCOMES
        start = zone(e.get('location'), config, direction)
        end = zone(e.get('pass_end_location' if kind == 'Pass' else 'carry_end_location'), config, direction)
        pass_outcome = e.get('pass_outcome')
        known_pass = _missing(pass_outcome) or isinstance(pass_outcome, str)
        success = kind == 'Carry' or (kind == 'Pass' and _missing(pass_outcome))
        valid = start is not None and (kind != 'Shot' or known_shot) and (kind != 'Pass' or known_pass)
        rows.append(dict(position=position, event_id=e.get('id'), player=e.get('player'), type=kind,
                         start=start, end=end, success=success,
                         goal=bool(known_shot and outcome == 'Goal'), eligible=valid))
    result = pd.DataFrame(rows, columns=['position', 'event_id', 'player', 'type', 'start', 'end', 'success', 'goal', 'eligible'])
    result.attrs['grid'] = (config.nx, config.ny)
    return result


def fit(actions, config=XTConfig(), metadata=None):
    """Fit empirical probabilities and the least nonnegative Bellman fixed point.

    Input must be extract_actions output with the SAME config/direction.
    Failed moves and successful moves with unknown endpoints lose continuation.
    Empty zones use an explicit zero fallback, with no invented pseudocounts.
    """
    if not {'type', 'start', 'end', 'success', 'goal', 'eligible'}.issubset(actions):
        raise ValueError('Expected extract_actions output')
    if actions.attrs.get('grid', (config.nx, config.ny)) != (config.nx, config.ny):
        raise ValueError('Extraction and fitting grids differ')
    n = config.nx*config.ny
    shots, goals, moves = (np.zeros(n) for _ in range(3))
    transitions = np.zeros((n, n))
    for e in actions.itertuples():
        if not e.eligible:
            continue
        if pd.isna(e.start) or not float(e.start).is_integer() or not 0 <= e.start < n:
            raise ValueError('Invalid start zone for fitting grid')
        if pd.notna(e.end) and (not float(e.end).is_integer() or not 0 <= e.end < n):
            raise ValueError('Invalid end zone for fitting grid')
        if e.type not in ('Shot', 'Pass', 'Carry'):
            raise ValueError('Unexpected action type')
        i = int(e.start)
        if e.type == 'Shot':
            shots[i] += 1
            goals[i] += e.goal
        else:
            moves[i] += 1
            if e.success and pd.notna(e.end):
                transitions[i, int(e.end)] += 1
    total = shots+moves
    divide = lambda a, b: np.divide(a, b, out=np.zeros_like(a), where=b != 0)
    pshot, pmove = divide(shots, total), divide(moves, total)
    pgoal = divide(goals, shots)
    # Substochastic: denominator ALL move attempts, including failed/invalid end.
    transition = divide(transitions, moves[:, None])
    reward = pshot*pgoal
    value = np.zeros(n)
    residuals = []
    for _ in range(config.max_iterations):
        # einsum avoids launching BLAS thread pools for each tiny grid update.
        updated = reward + pmove*np.einsum('ij,j->i', transition, value, optimize=False)
        residuals.append(float(np.max(np.abs(updated-value))))
        value = updated
        if residuals[-1] <= config.tolerance:
            break
    else:
        raise RuntimeError('xT failed to converge; increase iterations or inspect transitions')
    return dict(version=1, config=asdict(config), surface=value.reshape(config.ny, config.nx).tolist(),
                metadata={**(metadata or {}), 'trained_at': datetime.now(timezone.utc).isoformat(),
                          'coordinate_system': 'StatsBomb 120x80 attacking right', 'fallback': 'zero, no pseudocounts'},
                diagnostics=dict(actions=len(actions), eligible=int(actions.eligible.sum()),
                    excluded=int((~actions.eligible).sum()),
                    by_type={kind: int(actions.type.eq(kind).sum()) for kind in ('Shot', 'Pass', 'Carry')},
                    eligible_by_type={kind: int((actions.type.eq(kind) & actions.eligible).sum()) for kind in ('Shot', 'Pass', 'Carry')},
                    invalid_end_moves=int(((actions.type != 'Shot') & actions.end.isna()).sum()),
                    shots=shots.tolist(), goals=goals.tolist(), moves=moves.tolist(),
                    successful_transitions=transitions.sum(axis=1).tolist(), unobserved_zones=int((total == 0).sum()),
                    p_shot=pshot.tolist(), p_move=pmove.tolist(), p_goal_given_shot=pgoal.tolist(),
                    transition_row_sums=transition.sum(axis=1).tolist(), residuals=residuals,
                    iterations=len(residuals), converged=True))


def rate_actions(events, model, direction='right'):
    """Copy input and add nullable xT; only successful, valid pass/carry scored."""
    config = _validate_model(model)
    values = np.asarray(model['surface']).ravel()
    scores = [None] * len(events)
    for a in extract_actions(events, config, direction).itertuples(index=False):
        if a.type != 'Shot' and a.eligible and a.success and pd.notna(a.end):
            scores[a.position] = float(values[int(a.end)]-values[int(a.start)])
    result = events.copy()
    result['xT'] = pd.array(scores, dtype='Float64')
    return result


def save_model(model, path):
    """Save a validated, versioned artifact; JSON NaN/Infinity are forbidden."""
    _validate_model(model)
    Path(path).write_text(json.dumps(model, indent=2, allow_nan=False), encoding='utf-8')


def load_model(path):
    """Load a versioned artifact and reject corrupt or nonfinite surfaces."""
    model = json.loads(Path(path).read_text(encoding='utf-8'))
    _validate_model(model)
    return model


def _validate_model(model):
    if type(model.get('version')) is not int or model['version'] != 1:
        raise ValueError('Unsupported xT artifact version')
    config = XTConfig(**model['config'])
    surface = np.asarray(model['surface'], dtype=float)
    if surface.shape != (config.ny, config.nx) or not np.isfinite(surface).all() or (surface < 0).any() or (surface > 1+config.tolerance).any():
        raise ValueError('Invalid xT surface')
    if not isinstance(model.get('metadata'), dict) or not isinstance(model.get('diagnostics'), dict):
        raise ValueError('Missing xT model metadata/diagnostics')
    return config
