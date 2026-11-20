"""Share model instances between startup, intake and resolution suggestions."""

from functools import lru_cache, wraps
from pathlib import Path
from threading import Lock
from time import monotonic

from app.core.config import settings


def shared_model(factory):
    # lru_cache alone allows two concurrent cold calls to load the same weights.
    cached = lru_cache(maxsize=1)(factory)
    lock = Lock()
    retry_at = 0.0

    @wraps(factory)
    def get():
        nonlocal retry_at
        with lock:
            if monotonic() < retry_at:
                raise RuntimeError(f"{factory.__name__} is temporarily unavailable")
            try:
                return cached()
            except Exception:
                # Concurrent requests should not all retry a failed model download.
                retry_at = monotonic() + 30
                raise
    return get


@shared_model
def configure_inference():
    import torch

    torch.set_num_threads(min(torch.get_num_threads(), settings.AI_CPU_THREADS))


def load_model(model_id, loader, *, hub_id=None):
    """Use an installed snapshot without making Hub requests for optional files."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    configure_inference()
    if Path(model_id).is_dir():
        return loader(model_id)
    try:
        snapshot = snapshot_download(hub_id or model_id, local_files_only=True)
    except LocalEntryNotFoundError:
        return loader(model_id)
    try:
        return loader(snapshot)
    except OSError:
        # An interrupted first download can leave an incomplete snapshot.
        return loader(model_id)
