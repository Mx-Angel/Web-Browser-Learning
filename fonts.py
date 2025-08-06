import tkinter as tk
import tkinter.font
from constants import FONTS

def get_font(size: int, weight: str = "normal", style: str = "roman") -> tkinter.font.Font:
    """
    Get a tkinter Font object with specified properties.
    Uses caching to avoid creating duplicate fonts.

    :param size: Font size in points
    :param weight: "normal" or "bold"
    :param style: "roman" (normal) or "italic"
    :return: tkinter.font.Font object
    """
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(
            size=size,
            weight="bold" if weight == "bold" else "normal",
            slant="italic" if style == "italic" else "roman"
        )
        label = tk.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]