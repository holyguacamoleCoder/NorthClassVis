"""Aggregate input semantic binding subsystem."""

from .context import BindingContext, build_binding_context, candidate_for_dataset_id
from .gate import AmbiguityGateResult, check_ambiguity, should_skip_resolver
from .intent import IntentConfig, heuristic_resolve, llm_resolve, resolve_binding_intent
from .pipeline import resolve_aggregate_binding
from .scoring import pick_best_candidate, score_for_ref
from .types import BindMode, BindingCandidate, DatasetBindingDecision
from .validate import validate_decision

__all__ = [
    "AmbiguityGateResult",
    "BindMode",
    "BindingCandidate",
    "BindingContext",
    "DatasetBindingDecision",
    "IntentConfig",
    "build_binding_context",
    "candidate_for_dataset_id",
    "check_ambiguity",
    "heuristic_resolve",
    "llm_resolve",
    "pick_best_candidate",
    "resolve_aggregate_binding",
    "resolve_binding_intent",
    "score_for_ref",
    "should_skip_resolver",
    "validate_decision",
]
