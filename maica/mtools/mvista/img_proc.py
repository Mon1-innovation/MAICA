import os
from PIL import Image
from io import BytesIO
import magic

import uuid
from typing import *
from maica.maica_utils import *

_ALLOWED_MIMES = ['image/jpeg', 'image/png', 'image/bmp', 'image/webp']

class ProcessingImg():
    """A wrapped picture to process."""
    _bio: Optional[BytesIO] = None
    _real_path: Optional[str] = None
    _base_path: str = get_inner_path('fs_storage')

    format: str = ''
    is_compressed: bool = False

    @property
    def file_name(self):
        return os.path.basename(self._real_path)

    def _rfb(self, *args, **kwargs):
        self._bio.seek(0)
        b = self._bio.read(*args, **kwargs)
        self._bio.seek(0)
        return b
    
    def _purge(self):
        self._bio.seek(0)
        self._bio.truncate(0)

    def _save(self, path):
        self._bio.seek(0)
        with open(path, 'wb') as f:
            f.write(self._bio.getvalue())

    def _read(self, path):
        self._purge()
        with open(path, 'rb') as f:
            self._bio.write(f.read())

    @overload
    def __init__(self, input: bytes) -> None:
        """Create from binary."""

    @overload
    def __init__(self, input: str) -> None:
        """Read from fs."""

    @overload
    def __init__(self) -> None:
        """Do whatever later manually."""

    def __init__(self, input=None):
        """Automatically select initialization method."""
        self._bio = BytesIO()
        if isinstance(input, str):
            self.extract(input)
        elif input:
            self.perfuse(input)

    def perfuse(self, binary: bytes):
        """Create from binary."""
        self._bio.write(binary)
        self.format = magic.from_buffer(self._rfb(2048), mime=True)
        if not self.format in _ALLOWED_MIMES:
            raise MaicaInputWarning(f'Input file {self.format} is not image')
        self.compress()

    def extract(self, uuid: str):
        """Read from fs."""
        self.det_path(uuid)
        self.read()
        self.format = magic.from_buffer(self._rfb(2048), mime=True)
        if not self.format in _ALLOWED_MIMES:
            raise MaicaInputError(f'Extracted file {self.format} is not image')
        
    def compress(self, mw=1920, mh=1080, q=85):
        """Compresses the wrapped picture."""
        img = Image.open(self._bio)
        img.load()

        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        width, height = img.size
        scale = min(mw / width, mh / height, 1.0)

        if scale < 1.0:
            new_size = (int(width * scale), int(height * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        self._purge()
        img.save(self._bio, format='JPEG', quality=q, optimize=True)
        self.is_compressed = True

    def det_path(self, fname: Optional[str]=None):
        """Just fill the _real_path."""
        def abspath():
            nonlocal fname
            try:
                fname = str(uuid.UUID(fname))
            except Exception as e:
                raise MaicaInputWarning(f'fname {fname} is not uuid')
            return os.path.join(self._base_path, f"{fname}.jpg")
        
        if not fname:
            fname = str(uuid.uuid4())
            while os.path.isfile(abspath()):
                fname = str(uuid.uuid4())
        self._real_path = abspath()
        return fname

    def read(self):
        """Read bytes from desired path."""
        assert os.path.isfile(self._real_path), f"File {self.file_name} not exist"
        self._read(self._real_path)

    def save(self):
        """Save wrapped picture to desired path."""
        assert self._real_path, "Run det_path before save"
        self._save(self._real_path)

    def delete(self):
        """Purge bio and delete desired path."""
        self._purge()
        assert os.path.isfile(self._real_path), f"File {self.file_name} not exist"
        os.remove(self._real_path)

    def to_bio(self):
        """Get stored bio."""
        return self._bio
