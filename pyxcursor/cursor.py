from PIL import Image
from dataclasses import dataclass

__all__ = ('CursorFrame', 'Cursor')

@dataclass
class CursorFrame:
    image: Image.Image
    hot_spot: tuple = (0, 0)
    duration: int = 50  # duration of this frame in milliseconds

    @property
    def size(self) -> tuple:
        return self.image.size

@dataclass
class Cursor:
    frames: list[CursorFrame] = None

