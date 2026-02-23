"""Run async coroutines on one long-lived event loop for Streamlit."""

# solves the following streamlit errors (streamlit is single threaded):
# Event loop is closed
# another operation is in progress

from __future__ import annotations
import asyncio
import atexit
import threading
from typing import Any, Coroutine, Optional
import streamlit as st


class _AsyncRunner:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="dashboard-async-loop")
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, Any], timeout: Optional[float] = None) -> Any:
        with self._lock:
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return fut.result(timeout=timeout)

    def close(self) -> None:
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread.is_alive():
            self._thread.join(timeout=1)


@st.cache_resource
def get_async_runner() -> _AsyncRunner:
    runner = _AsyncRunner()
    atexit.register(runner.close)
    return runner


def run_async(coro: Coroutine[Any, Any, Any], timeout: Optional[float] = None) -> Any:
    return get_async_runner().run(coro, timeout=timeout)
