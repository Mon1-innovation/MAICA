import asyncio
import os
import aiofiles
import aiofiles.os
from PIL import Image, UnidentifiedImageError
from io import BytesIO

import sqlalchemy
from sqlalchemy.orm import load_only

import uuid
from typing import *
from maica.maica_utils import *

_ALLOWED_FORMATS = {"JPEG", "PNG", "BMP", "WEBP"}
_FORMAT_MIMES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "BMP": "image/bmp",
    "WEBP": "image/webp",
}
# Uploaded images are resized to 1920x1080, so decoding extremely large source
# images only creates a denial-of-service risk and has no user-visible benefit.
_MAX_SOURCE_PIXELS = 40_000_000

_base_path: str = get_inner_path('fs_storage/mv_img')

class ImgByUuid():
    """
    A wrapped picture to process.
    Usage:
        - Read:
            pi = await ImgByUuid.create(uuid)
            img_bytes = pi.get_bio()
        - Write:
            pi = await ImgByUuid.create(bytes)
            await pi.save()
        - Delete:
            pi = ImgByUuid()
            pi.uuid = uuid
            await pi.delete()
    """

    _bio: Optional[BytesIO] = None
    _uuid: Optional[str] = None

    format: str = ''
    is_compressed: bool = False

    @property
    def uuid(self):
        return self._uuid
    @uuid.setter
    def uuid(self, v):
        self._uuid = str(uuid.UUID(v))

    @property
    def file_name(self):
        if not self.uuid:
            raise RuntimeError("No UUID for this image instance")
        return self.uuid + ".jpg"
    
    @property
    def real_path(self):
        return os.path.join(_base_path, self.file_name)

    async def gen_uuid(self):
        if not self.uuid:
            self.uuid = str(uuid.uuid4())
            while await aiofiles.os.path.isfile(self.real_path):
                self.uuid = str(uuid.uuid4())
        return self.uuid

    def _rfb(self, *args, **kwargs):
        self._bio.seek(0)
        b = self._bio.read(*args, **kwargs)
        self._bio.seek(0)
        return b
    
    def _purge(self):
        self._bio.seek(0)
        self._bio.truncate(0)

    async def _save(self, path):
        self._bio.seek(0)
        temporary_path = path + ".tmp"
        try:
            async with aiofiles.open(temporary_path, 'wb') as f:
                await f.write(self._bio.getvalue())
                await f.flush()
                await asyncio.to_thread(os.fsync, f.fileno())
            await aiofiles.os.replace(temporary_path, path)
        finally:
            if await aiofiles.os.path.exists(temporary_path):
                await aiofiles.os.remove(temporary_path)

    async def _read(self, path):
        self._purge()
        async with aiofiles.open(path, 'rb') as f:
            self._bio.write(await f.read())

    def __init__(self):
        """Create an empty wrapper without accessing the filesystem."""
        self._bio = BytesIO()

    @classmethod
    async def create(cls, input: bytes | str | None = None) -> Self:
        """Create from binary data or read an existing image by UUID."""
        img = cls()
        if isinstance(input, str):
            await img.extract(input)
        elif input:
            await asyncio.to_thread(img.perfuse, input)
            await img.gen_uuid()
        return img

    def perfuse(self, binary: bytes):
        """Create from binary."""
        self._bio.write(binary)
        self.compress()

    async def extract(self, fuuid: str):
        """Read from fs."""
        self.uuid = fuuid

        await self.read()
        try:
            with Image.open(self._bio) as img:
                if img.format not in _ALLOWED_FORMATS:
                    raise MaicaInputError(f"Extracted file format {img.format!r} is not supported")
                self.format = _FORMAT_MIMES[img.format]
        except (UnidentifiedImageError, OSError) as exc:
            raise MaicaInputError("Extracted file is not a valid image") from exc

    def compress(self, mw=1920, mh=1080, q=85):
        """Compresses the wrapped picture."""
        try:
            img = Image.open(BytesIO(self._rfb()))
            if img.format not in _ALLOWED_FORMATS:
                raise MaicaInputWarning(f"Input file format {img.format!r} is not supported")
            self.format = _FORMAT_MIMES[img.format]
            width, height = img.size
            if width <= 0 or height <= 0 or width * height > _MAX_SOURCE_PIXELS:
                raise MaicaInputWarning(
                    f"Input image dimensions {width}x{height} are not acceptable"
                )
            img.load()
        except MaicaInputWarning:
            raise
        except (UnidentifiedImageError, OSError) as exc:
            raise MaicaInputWarning("Input file is not a valid image") from exc

        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        scale = min(mw / width, mh / height, 1.0)

        if scale < 1.0:
            new_size = (int(width * scale), int(height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        self._purge()
        img.save(self._bio, format='JPEG', quality=q, optimize=True)
        img.close()
        self.format = "image/jpeg"
        self.is_compressed = True

    async def _check_existence(self):
        if not await aiofiles.os.path.isfile(self.real_path):
            raise MaicaInputWarning(f"File {self.file_name} not exist", 404)

    async def read(self):
        """Read bytes from desired path."""
        await self._check_existence()
        await self._read(self.real_path)

    async def save(self):
        """Save wrapped picture to desired path."""
        await self._save(self.real_path)

    async def delete(self):
        """Purge bio and delete desired path."""
        await self._check_existence()
        await aiofiles.os.remove(self.real_path)
        self._purge()

    def get_bio(self):
        """Get stored bio."""
        self._bio.seek(0)
        return self._bio

    # Database methods
    async def register(self, user_id):
        if not self.uuid:
            raise RuntimeError("No UUID for this image instance")
        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():

                stmt = sqlalchemy.insert(SqlMvMeta).values(
                    user_id=user_id,
                    uuid=self.uuid,
                )
                await dbs.execute(stmt)

    async def unregister(self):
        if not self.uuid:
            raise RuntimeError("No UUID for this image instance")
        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():

                stmt = sqlalchemy.delete(SqlMvMeta).where(
                    SqlMvMeta.uuid == self.uuid,
                )
                await dbs.execute(stmt)

    @classmethod
    async def load(cls, user_id):
        async with DatabaseUtils.SessionData() as dbs:
            async with dbs.begin():

                stmt = sqlalchemy.select(SqlMvMeta).where(
                    SqlMvMeta.user_id == user_id,
                ).order_by(
                    SqlMvMeta.timestamp.desc(),
                    SqlMvMeta.id.desc(),
                ).options(
                    load_only(SqlMvMeta.uuid),
                )
                objs = (await dbs.scalars(stmt)).all()

        imgs = []
        for obj in objs:
            img = cls()
            img.uuid = obj.uuid
            imgs.append(img)

        return imgs
