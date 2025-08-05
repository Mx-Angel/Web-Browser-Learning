from utils import Rect
from requests import Text, Element
from browser import DrawText, DrawRect, get_font

from browser import BLOCK_ELEMENTS, CANVAS_WIDTH, HSTEP, WIDTH, HSTEP, VSTEP

# Import constants from browser module
def get_constants():
    """This will be set by browser.py when it imports this module"""
    pass

class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        # Calculate baseline (only if there are children)
        if self.children:
            max_ascent = max([child.font.metrics("ascent") for child in self.children])
            baseline = self.y + max_ascent # Remember that y is the top of the line
            for word in self.children:
                word.y = baseline - word.font.metrics("ascent")
            max_descent = max([word.font.metrics("descent") for word in self.children])
            self.height = max_ascent + max_descent
        else:
            self.height = 0

    def paint(self):
        return []


class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous

    def layout(self):
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal": style = "roman"
        size = int(float(self.node.style["font-size"][:-2])) # Convert CSS px to Tk points
        self.font = get_font(size, weight, style)

        self.width = self.font.measure(self.word)
        
        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + self.previous.width + space
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")

    def paint(self):
        color = self.node.style["color"]
        return [DrawText(self.x, self.y, self.word, color, self.font)]


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        
        # Properties for inline layout mode (old system compatibility)
        self.cursor_x = 0
        self.cursor_y = 0
        self.line = []
        self.display_list = []
        self.centre_line = False
        
    def layout(self):
        self.x = self.parent.x
        self.width = self.parent.width
        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        
        mode = self.layout_mode()
        if mode == "block":
            previous = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next

            for child in self.children:
                child.layout()
        else:
            # Inline mode
            self.new_line()
            self.recurse(self.node)
            
            # Layout all line children
            for child in self.children:
                child.layout()

        self.height = sum([child.height for child in self.children])

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)
        return cmds

    def layout_mode(self):        
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and \
                  child.tag in BLOCK_ELEMENTS
                  for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"

    def recurse(self, node):
        if isinstance(node, Text):
            for word in node.text.split():
                self.word(node, word)
        else:
            if node.tag == "br": # Create a new line for line breaks
                self.new_line()
            if node.tag == "h1":
                self.centre_line = True
            for child in node.children:
                self.recurse(child)

    def layout_intermediate(self):
        previous = None
        for child in self.node.children:
            next = BlockLayout(child, self, previous)
            self.children.append(next)
            previous = next

    def flush(self):
        if not self.line:
            return
        
        metrics = [font.metrics() for x, word, font, color, is_super in self.line]
        max_ascent = max([metric['ascent'] for metric in metrics])
        max_descent = max([metric['descent'] for metric in metrics])

        if self.centre_line:
            total_width = sum([font.measure(word) for x, word, font, color, is_super in self.line])
            total_space = CANVAS_WIDTH - HSTEP * 2  # Keep some space on the sides
            offset = (total_space - total_width) // 2

            # Adjust for centring (now with 4-tuple)
            self.line = [(x + offset, word, font, color, is_super) for x, word, font, color, is_super in self.line]
            self.centre_line = False

        baseline = self.cursor_y + max_ascent

        for rel_x, word, font, color, is_super in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            if is_super:
                y = self.y + baseline - max_ascent  # Move THIS word up
            self.display_list.append(DrawText(x, y, word, color, font))

        # Move cursor down for next line
        self.cursor_y = baseline + max_descent
        self.cursor_x = 0
        self.line = []

    def word(self, node, word):
        
        # Read style info from node.style
        weight = node.style.get("font-weight", "normal")
        style = node.style.get("font-style", "normal")
        if style == "normal":
            style = "roman"
        size_str = node.style.get("font-size", "16px")
        size = int(float(size_str[:-2]))  # Convert CSS px to Tk points
        color = node.style.get("color", "black")

        font = get_font(size, weight, style)
        w = font.measure(word)

        # Get the current line (or create one if it doesn't exist)
        if not self.children:
            self.new_line()
        line = self.children[-1]

        # Does the word fit?
        if self.width is not None and self.cursor_x + w > self.width:
            self.new_line()
            line = self.children[-1]

        # Add word to current line
        self.add_word_to_line(node, word, line)

    def add_word_to_line(self, node, word, line):
        """Helper method to add a TextLayout object to the current line"""
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word)
        line.children.append(text)
        
        # For now, just estimate the cursor position for word wrapping
        # The actual layout will happen later when LineLayout.layout() is called
        font = get_font(16, "normal", "roman")  # Use default font for estimation
        space = font.measure(" ") if previous_word else 0
        self.cursor_x += font.measure(word) + space

    def new_line(self):
        """Creates a new LineLayout and resets cursor_x"""
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

    def self_rect(self):
        return Rect(self.x, self.y,
            (self.x or 0) + (self.width or 0), (self.y or 0) + (self.height or 0))


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def layout(self):        
        # Set document dimensions first
        self.width = WIDTH - 2*HSTEP
        self.x = HSTEP
        self.y = VSTEP
        
        # Create child BlockLayout
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        
        # Layout the child (this creates child.display_list)
        child.layout()
        
        # We don't need a display list as the root has nothing to paint
        self.height = child.height

    def paint(self):
        return []


def tree_to_list(tree, list):
    """Utility function to flatten a layout tree into a list"""
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


def paint_tree(layout_object, display_list):
    """Recursively collect all paint commands from a layout tree"""
    display_list.extend(layout_object.paint())
    
    for child in layout_object.children:
        paint_tree(child, display_list)