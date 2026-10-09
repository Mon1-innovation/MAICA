import asyncio
import datetime
from contextlib import asynccontextmanager
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from quart import Quart
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from werkzeug.datastructures import FileStorage

from maica.common_schedule import CommonScheduler
from maica.maica_http import ShortConnHandler
from maica.maica_utils import DatabaseUtils, G, SqlMvMeta
from maica.mtools.mvista import img_proc
from maica.mtools.mvista.img_proc import ImgByUuid


@asynccontextmanager
async def image_database(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(DatabaseUtils, "SessionData", async_sessionmaker(engine, expire_on_commit=False))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SqlMvMeta.__table__.create)
        yield
    finally:
        await engine.dispose()


@pytest.fixture
def image_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(img_proc, "_base_path", str(tmp_path))
    source = BytesIO()
    Image.new("RGB", (32, 24), "red").save(source, format="PNG")
    return tmp_path, source.getvalue()


@pytest.fixture
def vista_client():
    handler = object.__new__(ShortConnHandler)
    handler.val = False
    handler.settings = SimpleNamespace(verification=SimpleNamespace(user_id=1))
    test_app = Quart(__name__)
    test_app.config["TESTING"] = True
    for endpoint, method in (("upload_vista", "POST"), ("download_vista", "GET"), ("delete_vista", "DELETE")):
        test_app.add_url_rule("/vista", endpoint=endpoint, methods=[method], view_func=getattr(handler, endpoint))
    return test_app.test_client()


def test_vista_http_upload_download_retention_and_delete(image_storage, vista_client, monkeypatch) -> None:
    path, binary = image_storage
    monkeypatch.setattr(G.A, "KEEP_MVISTA", "1")

    async def scenario() -> None:
        async with image_database(monkeypatch):
            uuids = []
            for _ in range(2):
                response = await vista_client.post(
                    "/vista",
                    form={"access_token": "token"},
                    files={"content": FileStorage(stream=BytesIO(binary), filename="image.png")},
                )
                assert response.status_code == 200
                image_uuid = (await response.get_json())["content"]
                uuids.append(image_uuid)
                assert (path / f"{image_uuid}.jpg").is_file()

            assert not (path / f"{uuids[0]}.jpg").exists()
            assert [image.uuid for image in await ImgByUuid.load(1)] == [uuids[1]]

            response = await vista_client.get("/vista", query_string={"content": uuids[1]})
            assert response.status_code == 200
            assert await response.get_data() == (path / f"{uuids[1]}.jpg").read_bytes()
            assert f"{uuids[1]}.jpg" in response.headers["Content-Disposition"]

            response = await vista_client.delete(
                "/vista", json={"access_token": "token", "content": uuids[1]}
            )
            assert response.status_code == 200
            assert (await response.get_json())["success"] is True
            assert await ImgByUuid.load(1) == []
            assert list(path.iterdir()) == []

    asyncio.run(scenario())


def test_vista_upload_removes_file_when_registration_fails(image_storage, vista_client, monkeypatch) -> None:
    path, binary = image_storage
    monkeypatch.setattr(G.A, "KEEP_MVISTA", "1")

    async def fail_register(self, user_id):
        assert (path / self.file_name).is_file()
        raise RuntimeError("registration failed")

    monkeypatch.setattr(ImgByUuid, "register", fail_register)

    async def scenario() -> None:
        with pytest.raises(RuntimeError, match="registration failed"):
            await vista_client.post(
                "/vista",
                form={"access_token": "token"},
                files={"content": FileStorage(stream=BytesIO(binary), filename="image.png")},
            )
        assert list(path.iterdir()) == []

    asyncio.run(scenario())


def test_scheduled_image_rotation_removes_old_files_and_stale_metadata(image_storage, monkeypatch) -> None:
    path, binary = image_storage
    monkeypatch.setattr(G.A, "ROTATE_MVISTA", "1")

    async def scenario() -> None:
        async with image_database(monkeypatch):
            old, missing, recent = [await ImgByUuid.create(binary) for _ in range(3)]
            await old.save()
            await recent.save()
            now = datetime.datetime.now()
            async with DatabaseUtils.SessionData() as dbs, dbs.begin():
                dbs.add_all([
                    SqlMvMeta(user_id=1, uuid=image.uuid, timestamp=timestamp)
                    for image, timestamp in (
                        (old, now - datetime.timedelta(hours=2)),
                        (missing, now - datetime.timedelta(hours=2)),
                        (recent, now),
                    )
                ])

            scheduler = object.__new__(CommonScheduler)
            await scheduler.rotate_mv_imgs.__wrapped__(scheduler)

            assert not (path / old.file_name).exists()
            assert (path / recent.file_name).is_file()
            assert [image.uuid for image in await ImgByUuid.load(1)] == [recent.uuid]

    asyncio.run(scenario())
