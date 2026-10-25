import socket
import threading
import time
from contextlib import contextmanager

import httpx
import uvicorn


@contextmanager
def running_api(app):
    """Serve the real ASGI app on an OS-assigned loopback port, then close it."""
    errors = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                log_level="warning",
                access_log=False,
                lifespan="on",
                timeout_graceful_shutdown=5,
            )
        )

        def run():
            try:
                server.run(sockets=[listener])
            except (OSError, RuntimeError, SystemExit) as error:
                errors.append(error)

        thread = threading.Thread(target=run, name="credit-e2e-api", daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 30
            with httpx.Client(timeout=1, trust_env=False) as probe:
                while time.monotonic() < deadline:
                    if errors:
                        raise RuntimeError("API failed during startup") from errors[0]
                    if not thread.is_alive():
                        raise RuntimeError("API stopped before becoming ready")
                    if server.started:
                        try:
                            response = probe.get(f"{url}/api/simulations")
                            if response.status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                    time.sleep(0.05)
                else:
                    raise TimeoutError("API did not become ready within 30 seconds")
            yield url
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                server.force_exit = True
                thread.join(timeout=2)
            if thread.is_alive():
                raise RuntimeError("API thread did not stop")
            if errors:
                raise RuntimeError("API server failed") from errors[0]
