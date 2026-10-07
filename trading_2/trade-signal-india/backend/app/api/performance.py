from fastapi import APIRouter

router = APIRouter(prefix="/performance", tags=["Performance & Metrics"])


@router.get("", summary="Get Strategy Performance Summary")
async def get_performance_summary():
    """Returns transparent signal performance metrics."""
    return {
        "status": "INSUFFICIENT DATA",
        "message": "Metrics are calculated transparently from verified signal outcomes only.",
        "horizons": {
            "1m": {"signals": 0, "win_rate": None},
            "3m": {"signals": 0, "win_rate": None},
            "5m": {"signals": 0, "win_rate": None},
            "10m": {"signals": 0, "win_rate": None},
            "15m": {"signals": 0, "win_rate": None},
            "20m": {"signals": 0, "win_rate": None}
        },
        "disclaimer": "No fabricated numbers. Statistics will reflect recorded signals."
    }
