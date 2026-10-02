"""GPU memory management for the pipeline worker.

Two concerns live here, both about a small (4GB) card shared by several large models:

* **Classifying CUDA failures.** ``torch.cuda.OutOfMemoryError`` ("CUDA out of
  memory ...") is an allocation that failed cleanly — freeing memory and
  retrying can work. A ``torch.AcceleratorError`` ("CUDA error: ...", including
  "CUDA error: out of memory") is raised from a failed kernel launch/sync and
  leaves the process's CUDA context unusable: every later call fails the same
  way until the process restarts. The worker treats the two differently.
* **Keeping one heavy model on the GPU at a time.** ``GpuResidency`` parks every
  other registered model's weights in host RAM (not run there — only parked) and
  moves the one about to run onto the GPU, so two large VLMs never compete for
  VRAM. Moving weights between host RAM and VRAM takes seconds; reloading a
  model from disk can take minutes.

No ``torch`` import at module scope, so the error classifiers are safe to import
anywhere.
"""
from __future__ import annotations

import contextlib
import gc
import threading
from typing import Any, Iterator

from src.logging_config import get_logger

logger = get_logger(__name__)


def _error_chain(exc: BaseException | None) -> Iterator[BaseException]:
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        yield exc
        exc = exc.__cause__ or exc.__context__


def is_cuda_fatal(exc: BaseException) -> bool:
    """True when the CUDA context is probably unusable and the process should restart."""
    for err in _error_chain(exc):
        if type(err).__name__ == "AcceleratorError" or "CUDA error" in str(err):
            return True
    return False


def is_cuda_oom(exc: BaseException) -> bool:
    """True for a clean, recoverable allocation failure (not a corrupted context)."""
    if is_cuda_fatal(exc):
        return False
    for err in _error_chain(exc):
        if type(err).__name__ == "OutOfMemoryError" or "out of memory" in str(err).lower():
            return True
    return False


def release_gpu_memory() -> None:
    """Drop unreachable tensors and hand cached CUDA blocks back to the driver."""
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        logger.warning("Could not release cached GPU memory", exc_info=True)


class GpuResidency:
    """At most one registered model's weights on the GPU at any moment.

    ``use(key, module, device)`` is a context manager held for the whole
    inference call: it parks whatever else was resident, moves ``module`` onto
    ``device``, and keeps other threads from swapping it out mid-generation.
    Heavy-model inference is therefore serialized, which is what a 4GB card needs
    anyway. A CPU ``device`` is a no-op (nothing to manage).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._resident: tuple[str, Any] | None = None

    @property
    def resident_key(self) -> str | None:
        return self._resident[0] if self._resident else None

    @contextlib.contextmanager
    def use(self, key: str, module: Any, device: str) -> Iterator[None]:
        if device == "cpu":
            yield
            return
        with self._lock:
            if self._resident and self._resident[0] != key:
                self._park()
            if self._resident is None:
                try:
                    module.to(device)
                except BaseException:
                    # A move that dies halfway leaves weights split across devices.
                    with contextlib.suppress(Exception):
                        module.to("cpu")
                    release_gpu_memory()
                    raise
                self._resident = (key, module)
            yield

    def park_all(self) -> None:
        with self._lock:
            self._park()

    def _park(self) -> None:
        if self._resident is None:
            return
        key, module = self._resident
        self._resident = None
        module.to("cpu")
        logger.info("Parked %s in host memory to free GPU memory", key)
        release_gpu_memory()


residency = GpuResidency()
