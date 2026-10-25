import hashlib
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from pydantic import HttpUrl
from sqlalchemy import delete

from app.database import create_database_engine
from app.main import create_app
from app.models import Session

from .runtime import running_api


def remove_test_image(image):
    # Remove only our unique tag, preserving pre-existing tags of the same image.
    from docker.errors import ImageNotFound

    try:
        image.get_docker_client().client.images.remove(image.tag, noprune=True)
    except ImageNotFound:
        pass
    finally:
        image.remove()  # clean_up=False: close the client without deleting by ID.


@pytest.fixture(scope="session")
def real_banks():
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.image import DockerImage
    from testcontainers.core.wait_strategies import HttpWaitStrategy

    root = Path(__file__).resolve().parents[4]
    with ExitStack() as resources:
        urls = []
        for bank, port in [("a", 3001), ("b", 3002)]:
            image = DockerImage(
                root / f"bank-{bank}-mock-api",
                tag=f"credit-e2e-bank-{bank}:{uuid4().hex}",
                clean_up=False,
            )
            resources.callback(remove_test_image, image)
            image.build()
            container = resources.enter_context(
                DockerContainer(str(image))
                .with_exposed_ports(port)
                .with_kwargs(labels={"credit-simulation.test": "end-to-end"})
                .waiting_for(HttpWaitStrategy(port, "/health").for_status_code(200))
            )
            urls.append(
                HttpUrl(
                    f"http://{container.get_container_host_ip()}:{container.get_exposed_port(port)}"
                )
            )
        yield urls


@pytest.fixture
def e2e_payload():
    return {
        "name": "Cliente Fictício",
        "email": "cliente@example.com",
        "cpf": "00000000000",
        "employer_cnpj": "00000000000000",
        "monthly_income_cents": 300000,
        "requested_amount_cents": 100000,
        "term_months": 12,
    }


@pytest_asyncio.fixture
async def real_api(migrated_database, real_banks):
    settings = migrated_database.model_copy(
        update={
            "bank_a_base_url": real_banks[0],
            "bank_b_base_url": real_banks[1],
            "bank_timeout_seconds": 5.0,
            "allowed_origins": ["http://frontend.test"],
            "session_cookie_secure": False,
        }
    )
    hashes = set()

    async def remember_session(response):
        token = response.cookies.get("credit_session")
        if token is not None:
            hashes.add(hashlib.sha256(token.encode("utf-8")).digest())

    engine = create_database_engine(settings)
    try:
        with running_api(create_app(settings)) as url:
            async with httpx.AsyncClient(
                base_url=url,
                timeout=20,
                trust_env=False,
                headers={"Origin": "http://frontend.test"},
                event_hooks={"response": [remember_session]},
            ) as client:
                yield SimpleNamespace(client=client, engine=engine, url=url)
    finally:
        try:
            if hashes:
                async with engine.begin() as cleanup:
                    await cleanup.execute(
                        delete(Session).where(Session.token_hash.in_(hashes))
                    )
        finally:
            await engine.dispose()
