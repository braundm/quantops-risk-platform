"""Rate-limited research-only Monte Carlo endpoint using the optional native engine."""

from fastapi import APIRouter, Depends, HTTPException

from quantops_api.api.dependencies import require_expensive_capacity
from quantops_api.application.monte_carlo import (
    MonteCarloRequest,
    MonteCarloResult,
    analyze_monte_carlo,
)
from quantops_api.infrastructure.monte_carlo import NativeUnavailable

router = APIRouter(prefix="/api/v1/xtb", tags=["Monte Carlo research"])


@router.post(
    "/monte-carlo",
    response_model=MonteCarloResult,
    dependencies=[Depends(require_expensive_capacity)],
)
def monte_carlo(request: MonteCarloRequest) -> MonteCarloResult:
    try:
        return analyze_monte_carlo(request)
    except NativeUnavailable as error:
        raise HTTPException(503, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
