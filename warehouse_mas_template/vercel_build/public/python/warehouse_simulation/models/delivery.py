from __future__ import annotations

from .task import Task


class Delivery(Task):
    """Backward-compatible name for the original prototype model."""

    def __init__(
        self,
        delivery_id: str,
        pickup_id: str,
        dropoff_id: str,
        box_id: str,
        **kwargs,
    ) -> None:
        super().__init__(
            task_id=delivery_id,
            pickup_id=pickup_id,
            dropoff_id=dropoff_id,
            item_id=box_id,
            **kwargs,
        )
