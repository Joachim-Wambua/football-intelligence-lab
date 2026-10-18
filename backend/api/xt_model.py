"""Lazy, validated artifact loading. This module never imports training routines."""

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path

import numpy as np
from fastapi import HTTPException

from src.expected_threat import load_model
from backend.api.xt_schemas import XTModelInfo, XTCoverage

MODEL_PATH = Path(__file__).resolve().parents[2] / 'artifacts' / 'xt-v1.json'


@dataclass(frozen=True)
class ActiveXT:
    model: dict
    info: XTModelInfo


def read_xt_model(path: Path) -> ActiveXT:
    """Load one scoring artifact and validate the serving coordinate/coverage contract.

    Returns raw scoring data plus typed public metadata. Bad/missing files produce
    a safe 503; no filesystem paths or parser details reach clients. Counts must
    match the grid, and training/held-out IDs must be disjoint. A file changing
    during reading is rejected so model_id always identifies the served surface.
    """
    try:
        raw = path.read_bytes()
        model = load_model(path)
        if path.read_bytes() != raw:
            raise ValueError('Artifact changed while reading')
        meta, diagnostics = model['metadata'], model['diagnostics']
        if meta['coordinate_system'] != 'StatsBomb 120x80 attacking right':
            raise ValueError('Unsupported coordinate convention')
        nx, ny = model['config']['nx'], model['config']['ny']
        shots = np.asarray(diagnostics['shots'], dtype=float)
        goals = np.asarray(diagnostics['goals'], dtype=float)
        if any(values.shape != (nx * ny,) or not np.isfinite(values).all()
               or (values < 0).any() or (values != np.floor(values)).any() for values in (shots, goals)):
            raise ValueError('Invalid coverage counts')
        if (goals > shots).any() or not diagnostics['converged']:
            raise ValueError('Invalid fit diagnostics')
        residuals = np.asarray(diagnostics['residuals'], dtype=float)
        if residuals.ndim != 1 or len(residuals) != diagnostics['iterations'] or not len(residuals) or not np.isfinite(residuals).all() or (residuals < 0).any() or residuals[-1] > model['config']['tolerance']:
            raise ValueError('Invalid convergence diagnostics')
        if not meta['train_ids'] or set(meta['train_ids']) & set(meta['held_out_ids']):
            raise ValueError('Invalid training partition')
        info = XTModelInfo(model_id=hashlib.sha256(raw).hexdigest(), artifact_version=model['version'],
            nx=nx, ny=ny, surface=model['surface'], shot_counts=shots.astype(int).reshape(ny, nx).tolist(),
            coordinate_system=meta['coordinate_system'], provider=meta['provider'], provenance=meta['provenance'],
            trained_at=meta['trained_at'], competition_id=meta['competition_id'], season_id=meta['season_id'],
            fallback=meta['fallback'], tolerance=model['config']['tolerance'], iterations=diagnostics['iterations'],
            final_residual=float(residuals[-1]), manifest_sha256=meta['manifest_sha256'], event_sha256=meta['event_sha256'],
            coverage=XTCoverage(train_ids=meta['train_ids'], held_out_ids=meta['held_out_ids'],
                published_matches=meta['published_matches'], locally_eligible_matches=meta['locally_eligible_matches'],
                training_shots=int(shots.sum()), training_goals=int(goals.sum()),
                shot_zones=int((shots > 0).sum()), total_zones=nx * ny))
        return ActiveXT(model, info)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise HTTPException(503, 'Experimental xT model unavailable') from exc


@lru_cache(maxsize=1)
def get_xt_model() -> ActiveXT:
    """Cache successful validation per process until restart; failed loads are retried.

    Fixed artifacts are deployment inputs, not mutable request parameters. Restart
    the API after an intentional artifact deployment; this sprint never replaces it.
    """
    return read_xt_model(MODEL_PATH)
