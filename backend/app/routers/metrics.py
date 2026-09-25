from fastapi import APIRouter, Response
from app.core.metrics import metrics

router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def get_prometheus_metrics():
    """
    Expose Prometheus text exposition metrics for scraping.
    Includes request counts, latency histograms, and uptime gauges.
    """
    content = metrics.format_prometheus()
    return Response(
        content=content,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
