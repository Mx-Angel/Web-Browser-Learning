import tkinter
import tkinter.font

class Rect:
    """Represents a rectangle with left, top, right, bottom coordinates."""
    
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def contains_point(self, x, y):
        """Check if a point (x, y) is inside this rectangle."""
        return x >= self.left and x < self.right and y >= self.top and y < self.bottom

class DrawText:
    """Draws text at a specific position with given font and color."""

    def __init__(self, x1: int, y1: int, text: str, color: str, font: tkinter.font.Font):
        """
        Initialize a text drawing command.
        
        :param x1: X coordinate of the text's top-left corner
        :param y1: Y coordinate of the text's top-left corner
        :param text: Text string to display
        :param color: Text color (e.g., "black", "red", "#FF0000")
        :param font: tkinter Font object for text styling
        """
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color
        self.bottom = y1 + font.metrics("linespace")
        
        text_width = font.measure(text)
        text_height = font.metrics("linespace")
        self.rect = Rect(x1, y1, x1 + text_width, y1 + text_height)

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        """Draw the text on the canvas."""
        canvas.create_text(
            self.left,
            self.top - scroll,
            text=self.text,
            font=self.font,
            fill=self.color,
            anchor="nw"
        )

class DrawLine:
    """Draws a line between two points."""

    def __init__(self, x1: int, y1: int, x2: int, y2: int, color: str, thickness: int):
        """Initialize a line drawing command."""
        self.color = color
        self.thickness = thickness
        self.rect = Rect(x1, y1, x2, y2)

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        """Draw the line on the canvas with scroll offset applied."""
        canvas.create_line(
            self.rect.left, self.rect.top - scroll, 
            self.rect.right, self.rect.bottom - scroll, 
            fill=self.color, width=self.thickness
        )

class DrawRect:
    """Draws a filled rectangle."""

    def __init__(self, rect: Rect, color: str):
        """Initialize a rectangle drawing command."""
        self.rect = rect
        self.color = color
        self.top = rect.top
        self.left = rect.left
        self.bottom = rect.bottom
        self.right = rect.right

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        """Draw the filled rectangle on the canvas."""
        canvas.create_rectangle(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
            width=0,
            fill=self.color
        )

class DrawOutline:
    """Draws a rectangle border (outline only, no fill)."""

    def __init__(self, rect: Rect, color: str, thickness: int):
        """Initialize an outline drawing command."""
        self.rect = rect
        self.color = color
        self.thickness = thickness

    def execute(self, scroll: int, canvas: tkinter.Canvas):
        """Draw the rectangle outline on the canvas."""
        canvas.create_rectangle(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            width=self.thickness,
            outline=self.color,
            fill=""
        )