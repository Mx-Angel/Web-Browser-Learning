# ==============================================================================
# LAYOUT ENGINE - Text and Block Layout System
# ==============================================================================
# This file implements the browser's layout engine, which takes a parsed HTML/CSS
# tree and calculates the precise position and size of every element on the page.
#
# Key Classes:
# - DocumentLayout: Root container for the entire page
# - BlockLayout: Handles block-level elements (divs, paragraphs, etc.)
# - LineLayout: Represents a single line of text within a block
# - TextLayout: Individual words/text fragments within a line
#
# The layout process follows this hierarchy:
# DocumentLayout → BlockLayout → LineLayout → TextLayout
# ==============================================================================

from requests import Text, Element
from drawing import DrawText, DrawRect, Rect
from fonts import get_font
from constants import BLOCK_ELEMENTS, CANVAS_WIDTH, HSTEP, WIDTH, VSTEP

# ==============================================================================
# LINE LAYOUT CLASS
# ==============================================================================

class LineLayout:
    """
    Represents a single line of text within a block element.
    
    A line contains multiple TextLayout objects (individual words) and handles:
    - Baseline alignment for different font sizes on the same line
    - Vertical positioning of words based on font ascent/descent
    - Line height calculation based on the tallest text in the line
    """
    
    def __init__(self, node: Element, parent: 'BlockLayout', previous: 'LineLayout'):
        """
        Initialize a new line layout.
        
        :param node: HTML/CSS node this line belongs to
        :param parent: BlockLayout that contains this line
        :param previous: Previous LineLayout in the same block (for positioning)
        """
        self.node = node           # HTML/CSS node this line represents
        self.parent = parent       # Parent BlockLayout
        self.previous = previous   # Previous line (for vertical positioning)
        self.children = []         # List of TextLayout objects (words)

    def layout(self):
        """
        Calculate the position and size of this line and all words within it.
        
        This method:
        1. Sets line width and X position from parent
        2. Calculates Y position based on previous line
        3. Layouts all child words
        4. Aligns all words to a common baseline
        5. Calculates total line height
        """
        # Line takes full width of parent and aligns to left edge
        self.width = self.parent.width
        self.x = self.parent.x

        # Position vertically after previous line
        if self.previous and self.previous.y is not None:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        # Layout all words in this line first
        for word in self.children:
            word.layout()

        # Calculate baseline alignment for mixed font sizes
        # All text in a line must sit on the same baseline for proper appearance
        if self.children:
            # Find the tallest ascender (part of letter above baseline)
            max_ascent = max([child.font.metrics("ascent") for child in self.children])
            baseline = self.y + max_ascent # Remember that y is the top of the line
            for word in self.children:
                word.y = baseline - word.font.metrics("ascent")
            
            # Calculate line height as tallest ascent + deepest descent
            max_descent = max([word.font.metrics("descent") for word in self.children])
            self.height = max_ascent + max_descent
        else:
            # Empty line has no height
            self.height = 0

    def paint(self):
        """
        Generate drawing commands for this line.
        
        LineLayout itself has nothing to paint - individual words handle their own drawing.
        
        :return: Empty list
        """
        return []

# ==============================================================================
# TEXT LAYOUT CLASS
# ==============================================================================

class TextLayout:
    """
    Represents a single word or text fragment within a line.
    
    This is the atomic unit of text layout - each TextLayout object represents
    one word that will be drawn as a single DrawText command.
    """
    
    def __init__(self, node: Element, word: str, parent: LineLayout, previous: 'TextLayout'):
        """
        Initialize a text layout for a single word.
        
        :param node: HTML/CSS node this text belongs to (for styling)
        :param word: The actual text string to display
        :param parent: LineLayout that contains this word
        :param previous: Previous TextLayout in the same line (for horizontal positioning)
        """
        self.node = node           # HTML/CSS node for styling information
        self.word = word           # Text content to display
        self.children = []         # TextLayout has no children (leaf node)
        self.parent = parent       # Parent LineLayout
        self.previous = previous   # Previous word in line (for spacing)

    def layout(self):
        """
        Calculate the position and size of this text element.
        
        This method:
        1. Extracts font styling from CSS properties
        2. Measures the word width using the font
        3. Positions horizontally after previous word (with space)
        4. Sets height based on font line spacing
        """
        # Extract font properties from CSS styles
        weight = self.node.style["font-weight"] # type: ignore
        style = self.node.style["font-style"] # type: ignore
        if style == "normal": style = "roman"  # tkinter uses "roman" instead of "normal"
        
        # Convert CSS pixel size to tkinter points
        size = int(float(self.node.style["font-size"][:-2])) # type: ignore
        self.font = get_font(size, weight, style)

        self.width = self.font.measure(self.word)
        
        # Position horizontally
        if self.previous:
            # Add space between words
            space = self.previous.font.measure(" ")
            if self.previous.x is not None:
                self.x = self.previous.x + self.previous.width + space
        else:
            # First word starts at line's left edge
            self.x = self.parent.x

        # Height is font's total line spacing
        self.height = self.font.metrics("linespace")

    def paint(self):
        """
        Generate drawing command for this text.
        
        :return: List containing one DrawText command
        """
        color = self.node.style["color"] # type: ignore
        return [DrawText(self.x, self.y, self.word, color, self.font)] # type: ignore

# ==============================================================================
# BLOCK LAYOUT CLASS
# ==============================================================================

class BlockLayout:
    """
    Handles layout for block-level elements (divs, paragraphs, headings, etc.).
    
    Block elements:
    - Take full width of their container
    - Stack vertically
    - Can contain other blocks OR inline content (text/images)
    - Create new formatting contexts
    
    This class handles both "block mode" (containing other blocks) and 
    "inline mode" (containing text that wraps into lines).
    """
    
    def __init__(self, node: Element, parent: 'DocumentLayout', previous: 'BlockLayout'):
        """
        Initialize a block layout element.
        
        :param node: HTML element this block represents
        :param parent: Parent layout object (DocumentLayout or BlockLayout)
        :param previous: Previous sibling block (for vertical positioning)
        """
        self.node = node           # HTML element
        self.parent = parent       # Parent layout object
        self.previous = previous   # Previous sibling block
        self.children = []         # Child layout objects
        
        # Position and size (calculated during layout)
        self.x = None
        self.y = None
        self.width = None
        self.height = None
        
        # Properties for inline layout mode (legacy compatibility)
        # These are used when the block contains text instead of other blocks
        self.cursor_x = 0          # Horizontal position for next word
        self.cursor_y = 0          # Vertical position for current line
        self.line = []             # Current line being built (old system)
        self.display_list = []     # Drawing commands (old system)
        self.centre_line = False   # Whether to center the current line

    def layout(self):
        """
        Calculate layout for this block and all its children.
        
        This method:
        1. Sets position and width based on parent
        2. Determines layout mode (block vs inline)
        3. Creates and layouts child elements appropriately
        4. Calculates total height from children
        """
        # Block takes full width of parent and aligns to left
        self.x = self.parent.x
        self.width = self.parent.width
        
        # Position vertically after previous sibling block
        if self.previous and self.previous.y is not None and self.previous.height is not None:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y
        
        # Determine how to layout children
        mode = self.layout_mode()
        if mode == "block":
            # Block mode: children are other block elements
            # Create BlockLayout objects for each child element
            previous = None
            for child in self.node.children:
                next_block = BlockLayout(child, self, previous) # type: ignore
                self.children.append(next_block)
                previous = next_block

            # Layout all child blocks
            for child in self.children:
                child.layout()
        else:
            # Inline mode: children are text that flows into lines
            # Create line structure for text content
            self.new_line()
            self.recurse(self.node)
            
            # Layout all line children
            for child in self.children:
                child.layout()

        # Total height is sum of all child heights
        self.height = sum([child.height for child in self.children])

    def paint(self):
        """
        Generate drawing commands for this block's background.
        
        :return: List of drawing commands (background rectangle if specified)
        """
        cmds = []
        
        # Draw background color if specified in CSS
        bgcolor = self.node.style.get("background-color", "transparent") # type: ignore
        if bgcolor != "transparent":
            rect = DrawRect(self.self_rect(), bgcolor)
            cmds.append(rect)
        return cmds

    def layout_mode(self):
        """
        Determine whether this block should use block or inline layout.
        
        Block mode: Contains other block elements (divs, paragraphs, etc.)
        Inline mode: Contains text and inline elements that flow into lines
        
        :return: "block" or "inline"
        """
        if isinstance(self.node, Text):
            return "inline"
        elif any([isinstance(child, Element) and child.tag in BLOCK_ELEMENTS
                  for child in self.node.children]):
            return "block"
        elif self.node.children:
            return "inline"
        else:
            return "block"

    def recurse(self, node):
        """
        Recursively process node tree to extract text and create lines.
        
        This method walks through the HTML tree and:
        - Splits text nodes into individual words
        - Handles special elements like <br> (line breaks)
        - Processes styling elements like <h1> (centering)
        
        :param node: Current HTML node to process
        """
        if isinstance(node, Text):
            # Text node: split into words and add each to current line
            for word in node.text.split():
                self.word(node, word) # type: ignore
        else:
            # Element node: handle special cases and process children
            if node.tag == "br":
                # Line break: force new line
                self.new_line()
            if node.tag == "h1":
                self.centre_line = True
            for child in node.children:
                self.recurse(child)

    def flush(self):
        """
        Complete the current line and prepare for next line (legacy method).
        
        This method handles the old inline layout system and is kept
        for compatibility. The new system uses LineLayout and TextLayout instead.
        """
        if not self.line:
            return
        
        # Calculate baseline alignment for mixed fonts
        metrics = [font.metrics() for x, word, font, color, is_super in self.line]
        max_ascent = max([metric['ascent'] for metric in metrics])
        max_descent = max([metric['descent'] for metric in metrics])

        if self.centre_line:
            total_width = sum([font.measure(word) for x, word, font, color, is_super in self.line])
            total_space = CANVAS_WIDTH - HSTEP * 2  # Keep margins
            offset = (total_space - total_width) // 2

            # Adjust all word positions for centering
            self.line = [(x + offset, word, font, color, is_super) 
                        for x, word, font, color, is_super in self.line]
            self.centre_line = False

        baseline = self.cursor_y + max_ascent

        # Create DrawText commands for each word
        for rel_x, word, font, color, is_super in self.line:
            x = self.x + rel_x
            y = self.y + baseline - font.metrics("ascent")
            if is_super:
                y = self.y + baseline - max_ascent  # Superscript positioning
            self.display_list.append(DrawText(x, y, word, color, font))

        # Move cursor down for next line
        self.cursor_y = baseline + max_descent
        self.cursor_x = 0
        self.line = []

    def word(self, node: Element, word: str):
        """
        Add a word to the current line, handling word wrapping.
        
        This method:
        1. Extracts font styling from the node
        2. Measures word width
        3. Checks if word fits on current line
        4. Creates new line if needed
        5. Adds word to appropriate line
        
        :param node: HTML node containing this word (for styling)
        :param word: Text content of the word
        """
        # Extract CSS font properties
        weight = node.style.get("font-weight", "normal") # type: ignore
        style = node.style.get("font-style", "normal") # type: ignore
        if style == "normal":
            style = "roman"
        size_str = node.style.get("font-size", "16px") # type: ignore
        size = int(float(size_str[:-2]))  # Convert CSS px to Tk points
        color = node.style.get("color", "black") # type: ignore

        font = get_font(size, weight, style)
        w = font.measure(word)

        # Get the current line (or create one if it doesn't exist)
        if not self.children:
            self.new_line()
        line = self.children[-1]

        # Check if word fits on current line
        if self.width is not None and self.cursor_x + w > self.width:
            self.new_line()
            line = self.children[-1]

        # Add word to current line
        self.add_word_to_line(node, word, line)

    def add_word_to_line(self, node: Element, word: str, line: LineLayout):
        """
        Add a TextLayout object to the specified line.
        
        :param node: HTML node for styling
        :param word: Text content
        :param line: LineLayout to add the word to
        """
        # Find previous word in line for positioning
        previous_word = line.children[-1] if line.children else None
        text = TextLayout(node, word, line, previous_word) # type: ignore
        line.children.append(text)
        
        # Update cursor position for word wrapping (rough estimate)
        # Actual positioning happens in TextLayout.layout()
        font = get_font(16, "normal", "roman")  # Default font for estimation
        space = font.measure(" ") if previous_word else 0
        self.cursor_x += font.measure(word) + space

    def new_line(self):
        """
        Create a new LineLayout and reset horizontal cursor.
        
        This method:
        1. Resets horizontal cursor to start of line
        2. Creates new LineLayout object
        3. Links it to previous line for vertical positioning
        4. Adds it to children list
        """
        self.cursor_x = 0
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line) # type: ignore
        self.children.append(new_line)

    def self_rect(self):
        """
        Get the bounding rectangle for this block.
        
        :return: Rect object representing this block's bounds
        """
        return Rect(
            self.x or 0, self.y or 0,
            (self.x or 0) + (self.width or 0), 
            (self.y or 0) + (self.height or 0)
        )

# ==============================================================================
# DOCUMENT LAYOUT CLASS
# ==============================================================================

class DocumentLayout:
    """
    Root layout object representing the entire document.
    
    The DocumentLayout:
    - Sets up the document's overall dimensions and margins
    - Contains one child BlockLayout for the <html> element
    - Provides the root coordinate system for all other elements
    - Handles the interface between the browser and layout system
    """
    
    def __init__(self, node: Element):
        """
        Initialize the document layout.
        
        :param node: Root HTML element (usually <html>)
        """
        self.node = node        # Root HTML element
        self.parent = None      # Document has no parent
        self.children = []      # Will contain one BlockLayout child
        
        # Position and size (calculated during layout)
        self.x = None
        self.y = None
        self.width = None
        self.height = None

    def layout(self):
        """
        Calculate layout for the entire document.
        
        This method:
        1. Sets document dimensions with margins
        2. Creates root BlockLayout for HTML content
        3. Performs layout of all content
        4. Calculates total document height
        """
        # Set document dimensions with horizontal margins
        self.width = WIDTH - 2 * HSTEP  # Leave margins on left/right
        self.x = HSTEP                  # Start content after left margin
        self.y = VSTEP                  # Start content after top margin
        
        # Create single child BlockLayout for all content
        child = BlockLayout(self.node, self, None) # type: ignore
        self.children.append(child)
        
        # Layout all content (this recursively layouts everything)
        child.layout()
        self.height = child.height

    def paint(self):
        """
        Generate drawing commands for the document.
        
        The document itself has nothing to paint - all content
        is painted by child elements.
        
        :return: Empty list
        """
        return []

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def tree_to_list(tree, list):
    """
    Flatten a layout tree into a list by walking all nodes.
    
    This utility function recursively visits every node in the layout tree
    and adds it to a flat list. Useful for operations that need to process
    all layout objects regardless of hierarchy.
    
    :param tree: Root layout object to start from
    :param list: List to append nodes to
    :return: The modified list
    """
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

def paint_tree(layout_object, display_list):
    """
    Recursively collect all drawing commands from a layout tree.
    
    This function walks the entire layout tree and calls paint() on each
    object, collecting all drawing commands into a single display list.
    The browser can then execute these commands to render the page.
    
    :param layout_object: Layout object to start painting from
    :param display_list: List to append drawing commands to
    """
    # Add this object's drawing commands
    display_list.extend(layout_object.paint())
    
    for child in layout_object.children:
        paint_tree(child, display_list)