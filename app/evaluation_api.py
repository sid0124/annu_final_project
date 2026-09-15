"""
VTR-Agent: Evaluation API Endpoints

Evaluation harness API endpoints for benchmarking and metric collection.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from vtr_agent.api.schemas import (
    BenchmarkScenario, EvaluationRun, BaselineResult,
    EvaluationRunRequest, EvaluationRunResponse
)
from vtr_agent.core.database.session import get_db
from vtr_agent.core.database.models import User
from vtr_agent.evaluation import (
    evaluation_framework, run_evaluation, compare_baselines,
    run_ablation, test_reproducibility, SCENARIOS, get_scenario
)
from vtr_agent.api.auth import get_current_user

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationRun)
def run_evaluation_endpoint(
    request: EvaluationRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run a complete evaluation."""
    # Get scenario
    scenario = get_scenario(request.scenario_name)
    
    run = run_evaluation(
        scenario=scenario,
        task_description=request.task_description,
    )
    
    return run


@router.post("/compare-balines", response_model=Dict)
def compare_baselines_endpoint(
    request: EvaluationRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compare baselines for a scenario."""
    scenario = get_scenario(request.scenario_name)
    comparisons = compare_baselines(scenario, request.task_description)
    
    # Convert to serializable dict
    result = {}
    for name, baseline in comparisons.items():
        result[name] = {
            "baseline_name": baseline.baseline_name,
            "task_success": baseline.task_success,
            "unsupported_claim_rate": baseline.unsupported_claim_rate,
            "unsafe_action_block_rate": baseline.unsafe_action_block_rate,
            "human_effort": baseline.human_effort,
            "latency": baseline.latency,
            "safety_violations": baseline.safety_violations,
            "claims_verified": baseline.claims_verified,
            "total_claims": baseline.total_claims,
        }
    
    return {"comparisons": result, "scenario": request.scenario_name}


@router.run_ablation, response_model=Dict)
def run_ablation_endpoint(
    request: EvaluationRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run ablation study."""
    scenario = get_scenario(request.scenario_name)
    results = run_ablation(scenario, request.task_description, request.variants)
    
    # Convert to serializable dict
    result = {}
    for variant_name, baseline in results.items():
        result[variant_name] = {
            "baseline_name": baseline.baseline_name,
            "task_success": baseline.task_success,
            "unsupported_claim_rate": baseline.unsupported_claim_rate,
            "unsafe_action_block_rate": baseline.unsafe_action_block_rate,
            "human_effort": baseline.human_effort,
            "latency": baseline.latency,
            "safety_violations": baseline.safety_violations,
            "claims_verified": baseline.claims_verified,
            "total_claims": baseline.total_claims,
        }
    
    return {"results": result, "scenario": request.scenario_name}


@router.run_stress_test, response_model=BaselineResult)
def run_stress_test_endpoint(
    request: EvaluationRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run stress test."""
    scenario = get_scenario(request.scenario_name)
    result = evaluation_framework.run_stress_test(scenario, request.task_description, request.stress_factor)
    
    return {
        "baseline_name": "vtr_agent",
        "task_success": result.task_success,
        "unsupported_claim_rate": result.unsupported_claim_rate,
        "unsafe_action_block_rate": result.unsafe_action_block_rate,
        "human_effort": result.human_effort,
        "latency": result.latency,
        "safety_violations": result.safety_violations,
        "claims_verified": result.claims_verified,
        "total_claims": result.total_claims,
    }


@router.run_reproducibility_test, response_model=Dict)
def run_reproducibility_test_endpoint(
    request: EvaluationRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run reproducibility test."""
    results = test_reproducibility(request.task_description, request.repetitions)
    
    return {
        "repetitions": results["repetitions"],
        "success_rate": results["success_rate"],
        "average_latency": results["average_latency"],
        "average_unsupported_claim_rate": results["average_unsupported_claim_rate"],
        "reproducible": results["reproducible"],
    }


@router.get("/scenarios", response_model=List[str])
def get_scenarios():
    """Get available benchmark scenarios."""
    return list(SCENARIOS.keys())


@router.get("/metrics/{scenario_name}", response_model=Dict)
def get_scenario_metrics(
    scenario_name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get metrics for a specific scenario."""
    scenario = get_scenario(scenario_name)
    run = run_evaluation(scenario, f"Metrics evaluation for {scenario_name}")
    
    return run.overall_metrics