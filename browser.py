from requests import URL, Text, Element, HTMLParser
from cssparser import CSSParser, style, cascade_priority

from requests import DEFAULT_PAGE

import tkinter as tk
import tkinter.font
import sys

# Globals
FONTS = {}

# Constants
WIDTH, HEIGHT = 1280, 720
CANVAS_WIDTH, CANVAS_HEIGHT = 0, 0
HSTEP, VSTEP = 13, 18
BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]
SCROLL_STEP = 20
DEFAULT_STYLE_SHEET = CSSParser(open("browser.css").read()).parse()

def get_font(size, weight="normal", style="roman"):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=style)
        label = tk.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]


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

            self.height = sum([child.height for child in self.children])
            
            self.display_list = []
            for child in self.children:
                if hasattr(child, 'display_list'):
                    self.display_list.extend(child.display_list)
        else:
            # Inline mode
            self.display_list = []
            self.cursor_x = 0
            self.cursor_y = 0
            self.weight = "normal"
            self.style = "roman"
            self.size = 16
            self.line = []
            self.centre_line = False
            self.super_text = False
            
            self.recurse(self.node)
            self.flush()
            
            # Height is based on how much text we laid out
            self.height = self.cursor_y

    def paint(self):
        cmds = []
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            cmds.append(rect)
        if self.layout_mode() == "inline":
            cmds.extend(self.display_list)
            # for x, y, word, font, color in self.display_list: Don't change this line, something wrong with instructions I think?
            #     cmds.append(DrawText(x, y, word, font, color))
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
            if node.tag == "br": # Fix this so that h1 tags are big again and centring works again
                self.flush()
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
            print("Here")
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

        while word:
            w = font.measure(word)
            
            # Check if word fits on current line
            if self.cursor_x + w > self.width:
                split_word = None

                for index, char in enumerate(word):
                    partial_word = word[:index + 1]
                    # Split words across lines
                    if self.cursor_x + font.measure(partial_word + "-") < CANVAS_WIDTH - HSTEP:
                        split_word = partial_word
                    else:
                        break

                if not split_word:
                    self.flush()
                else:
                    first_part = split_word + "-"
                    self.add_word_to_line(first_part, font, color)
                    self.flush()  # Flush current line after adding first part

                    # Print remaining part if word
                    word = word[len(split_word):]
                    continue
            else:
                self.add_word_to_line(word, font, color)
                break

    def add_word_to_line(self, word, font, color):
        """Helper method to add word to current line"""
        is_super = False
        w = font.measure(word)
        
        if self.super_text:
            previous_space = font.measure(" ")
            reduced_space = previous_space // 2
            self.cursor_x -= (previous_space + reduced_space)
            is_super = True
        
        self.line.append((self.cursor_x, word, font, color, is_super))
        
        if self.super_text:
            self.cursor_x += w
            self.super_text = False
        else:
            self.cursor_x += w + font.measure(" ")

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

class DrawText:
    def __init__(self, x1, y1, text, color, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left,
            self.top - scroll,
            text = self.text,
            font = self.font,
            fill=self.color,
            anchor = "nw"
        )
    
class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left,
            self.top - scroll,
            self.right,
            self.bottom - scroll,
            width=0,
            fill=self.color
        )

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list
class Browser:
    def __init__(self):
        self.nodes = [] # Not used but referenced in book in chapter 6, will leave for now
        self.window = tk.Tk()
        self.canvas = tk.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT,
            bg="white"
        )
        # Working scrollbar setup
        self.scrollbar = tk.Scrollbar(self.window, orient="vertical", command=self.move)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.pack(side="left", fill="both", expand=1)
        
        # Connect canvas to scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Use in-built scrolling mechanism
        # Make canvas focusable for keyboard events
        self.canvas.configure(highlightthickness=0)
        self.canvas.focus_set()
        
        # Bind arrow keys to canvas
        self.scroll = 0
        self.canvas.bind("<Up>", lambda e: self.canvas.yview_scroll(-1, "units"))   
        self.canvas.bind("<Down>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.canvas.bind("<Page_Up>", lambda e: self.canvas.yview_scroll(-1, "pages"))
        self.canvas.bind("<Page_Down>", lambda e: self.canvas.yview_scroll(1, "pages"))
        self.window.bind("<Button-4>", lambda e: self.scroll_up(e))
        self.window.bind("<Button-5>", lambda e: self.scroll_down(e))
        
        # Keep resize event
        self.canvas.bind("<Configure>", self.window_resize)

    def window_resize(self, event):
        global CANVAS_WIDTH, CANVAS_HEIGHT
        CANVAS_WIDTH, CANVAS_HEIGHT = event.width, event.height

        if hasattr(self, 'document'):
            self.document.layout()
            self.display_list = []
            paint_tree(self.document, self.display_list)
            self.update_scroll_region()
            self.draw()

    def load(self, url):
        if url.scheme == "file":
            with open(url.path, 'r', encoding='utf8') as f:
                body = f.read()
                tree = HTMLParser(body).parse()
        elif url.entity == "data":
            _, content = url.parse_data_url(url.content)
            tree = HTMLParser(content).parse()
        elif url.entity == "view-source":
            body = url.request()
            tree = Text(body, None)
        else:
            body = url.request()
            tree = HTMLParser(body).parse()

        self.tree = tree
        rules = DEFAULT_STYLE_SHEET.copy()

        # Look for linked stylesheets in the document
        links = [
            node.attributes["href"]
            for node in tree_to_list(tree, [])
            if isinstance(node, Element)
            and node.tag == "link"
            and node.attributes.get("rel") == "stylesheet"
            and "href" in node.attributes
        ]

        # Try loading and parsing each stylesheet
        for link in links:
            style_url = url.resolve(link)
            try:
                body = style_url.request()
            except:
                continue
            rules.extend(CSSParser(body).parse())

        # Apply all styles to the tree
        style(self.tree, sorted(rules, key=cascade_priority))

        
        # Set initial canvas dimensions if not set
        global CANVAS_WIDTH, CANVAS_HEIGHT
        if CANVAS_WIDTH == 0:
            self.window.update_idletasks()
            CANVAS_WIDTH = self.canvas.winfo_width()
            CANVAS_HEIGHT = self.canvas.winfo_height()

        self.document = DocumentLayout(self.tree)
        self.document.layout()
        
        self.display_list = []
        paint_tree(self.document, self.display_list)
        
        # Calculate content height and set scroll region
        if self.display_list:
            self.content_height = max(cmd.bottom for cmd in self.display_list) + VSTEP
        else:
            self.content_height = 0

        self.update_scroll_region()
        self.draw()

    def update_scroll_region(self):
        """Set the scrollable region of the canvas"""
        if hasattr(self, 'content_height'):
            self.canvas.configure(scrollregion=(0, 0, CANVAS_WIDTH, self.content_height))
        else:
            # Use actual canvas dimensions as fallback
            actual_width = self.canvas.winfo_width() or WIDTH
            actual_height = self.canvas.winfo_height() or HEIGHT
            self.canvas.configure(scrollregion=(0, 0, actual_width, actual_height))

    def move(self, action, value): # Semi-broken for the end of the page the scrollbar will be incorrect
        max_scroll = max(self.document.height + 2*VSTEP - HEIGHT, 0) # How much content is scrollable

        if action == "moveto":
            fraction = float(value)
            fraction = max(0.0, min(fraction, 1.0))  # clamp numerically
            self.scroll = int(fraction * max_scroll) # Fraction of where we are multiplied by maximum scroll

        self.draw()

        # Update scrollbar thumb position
        content_height = self.document.height + 2 * VSTEP
        # Fraction of total content that is visible on screen
        visible_fraction = HEIGHT / content_height if content_height > 0 else 1.0

        if max_scroll > 0:
            scroll_fraction = self.scroll / max_scroll # Decimal between 0 and 1 representing the fraction of how far you are down the page
            scroll_fraction = min(scroll_fraction, 1.0 - visible_fraction) # Stops going over
            scroll_fraction = max(scroll_fraction, 0.0) # Stops going under

            top = scroll_fraction
            bottom = top + visible_fraction
        else:
            top, bottom = 0, 1

        self.scrollbar.set(top, bottom)

    def scroll_up(self, e):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        # Both of these are measure in decimals, these represent where the scrollbar starts and ends
        # Example: Your total content height is content_height pixels (e.g. 2000 px).
        # Your visible window height is HEIGHT pixels (e.g. 720 px).
        # Your current scroll offset from the top is self.scroll pixels (e.g. 300 px).
        # self.scroll / self.content_height = fraction where visible region starts (e.g. 300/2000 = 0.15).
        # (self.scroll + HEIGHT) / self.content_height = fraction where visible region ends (e.g. (300 + 720)/2000 = 0.51).
        # Sets the thumb size to cover from 0.15 to 0.51 (i.e., roughly 36% of the track length).
        self.canvas.configure(yscrollcommand=self.scrollbar.set(
            self.scroll / self.content_height, # Represents the top left
            (self.scroll + HEIGHT) / self.content_height # Represents the bottom right
            )
        )
        self.draw()

    def scroll_down(self, e):
        max_y = max(self.document.height + 2*VSTEP - HEIGHT, 0)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)
        self.canvas.configure(yscrollcommand=self.scrollbar.set(
            self.scroll / self.content_height,
            (self.scroll + HEIGHT) / self.content_height
            )
        )
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            # if hasattr(cmd, "font") and hasattr(cmd, "text"):
            #     if cmd.text == "Applying":
            #         print(f"Text: '{cmd.text}' - Font Size: {cmd.font.actual('size')}")
            if cmd.top > self.scroll + HEIGHT: continue
            if cmd.bottom < self.scroll: continue
            cmd.execute(self.scroll, self.canvas)

def paint_tree(layout_object, display_list):
    display_list.extend(layout_object.paint())

    for child in layout_object.children:
        paint_tree(child, display_list)

if __name__ == "__main__":
    print("Welcome to the Python Browser!\n")
    if len(sys.argv) == 1:
        Browser().load(URL(DEFAULT_PAGE))
    elif len(sys.argv) >= 2:
        web_urls = sys.argv[1:]
        for web_url in web_urls:
            try:
                Browser().load(URL(web_url))
            except Exception as e:
                print(f"Error loading {web_url}: {e}")
    else:
        print("Usage: python browser.py <url>")
        sys.exit(1)
    tk.mainloop()