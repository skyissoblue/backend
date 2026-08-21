from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import httpx


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until_ready(base_url: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError("FastAPI did not become ready")


def main() -> None:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["SELECTION_ENGINE_DATA_MODE"] = "mock"
    env.pop("REDIS_URL", None)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "selection_engine.api:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
    )
    try:
        wait_until_ready(base_url)
        with httpx.Client(base_url=base_url, timeout=30) as client:
            created = client.post("/api/session").raise_for_status().json()
            session_id = created["session_id"]
            conditions = [
                {"type": "industry", "value": "科技"},
                {"type": "board", "value": "主板"},
                {"type": "ma_cross_weekly"},
                {"type": "ma_deviation_weekly", "max_pct": 10},
                {"type": "rps", "op": ">", "value": 87},
            ]
            counts = [created["total"]]
            for condition in conditions:
                result = client.post(f"/api/session/{session_id}/condition", json=condition).raise_for_status().json()
                assert result["before"] == counts[-1]
                assert result["after"] < result["before"]
                counts.append(result["after"])

            undone = client.delete(f"/api/session/{session_id}/condition/last").raise_for_status().json()
            assert undone["after"] == counts[-2]
            assert undone["after"] > counts[-1]
            print(f"E2E passed: {' -> '.join(map(str, counts))} -> undo {undone['after']}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
