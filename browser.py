from requests import URL, Text, Element, HTMLParser
from cssparser import CSSParser, style, cascade_priority
from requests import DEFAULT_PAGE

# Import all layout classes
from layout import DocumentLayout, tree_to_list, paint_tree

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


class DrawText:
    def __init__(self, x1, y1, text, color, font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color
        self.bottom = y1 + font.metrics("linespace")
        
        # Add rect field for consistency
        text_width = font.measure(text)
        text_height = font.metrics("linespace")
        self.rect = Rect(x1, y1, x1 + text_width, y1 + text_height)

    def execute(self, scroll, canvas):
        canvas.create_text(
            self.left,
            self.top - scroll,
            text = self.text,
            font = self.font,
            fill=self.color,
            anchor = "nw"
        )
    

class DrawLine:
    def __init__(self, x1, y1, x2, y2, color, thickness):
        self.color = color
        self.thickness = thickness
        
        # Store the line coordinates in a rect field
        self.rect = Rect(x1, y1, x2, y2)

    def execute(self, scroll, canvas):
        canvas.create_line(
            self.rect.left, self.rect.top - scroll, 
            self.rect.right, self.rect.bottom - scroll, 
            fill=self.color, width=self.thickness
        )

# Also update DrawRect to take a Rect object:
class DrawRect:
    def __init__(self, rect, color):
        self.rect = rect
        self.color = color
        self.top = rect.top
        self.left = rect.left
        self.bottom = rect.bottom
        self.right = rect.right

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.rect.left,
            self.rect.top - scroll,
            self.rect.right,
            self.rect.bottom - scroll,
            width=0,
            fill=self.color
        )


class Browser:
    def __init__(self):
        self.tabs = []
        self.active_tab = None
        
        # Browser owns the window and canvas
        self.window = tk.Tk()
        self.canvas = tk.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT,
            bg="white"
        )
        
        # Working scrollbar setup - Browser owns this
        self.scrollbar = tk.Scrollbar(self.window, orient="vertical", command=self.handle_scroll)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=1)
        
        # Make canvas focusable for keyboard events
        self.canvas.configure(highlightthickness=0)
        self.canvas.focus_set()
        
        # Browser handles all events and forwards to active tab
        self.canvas.bind("<Up>", lambda e: self.handle_scroll_up())   
        self.canvas.bind("<Down>", lambda e: self.handle_scroll_down())
        self.canvas.bind("<Page_Up>", lambda e: self.handle_page_up())
        self.canvas.bind("<Page_Down>", lambda e: self.handle_page_down())
        self.window.bind("<Button-4>", lambda e: self.handle_scroll_up())
        self.window.bind("<Button-5>", lambda e: self.handle_scroll_down())
        self.window.bind("<Button-1>", lambda e: self.handle_click(e))
        self.canvas.bind("<Configure>", lambda e: self.handle_resize(e))
        self.window.bind("<Key>", self.handle_key) # Pick up all key presses
        self.window.bind("<Return>", self.handle_enter)

        self.chrome = Chrome(self)

    def handle_key(self, e):
        if len(e.char) == 0: return
        if not (0x20 <= ord(e.char) < 0x7f): return # Skip keys outside the ASCII range
        self.chrome.keypress(e.char)
        self.draw()

    def handle_enter(self, e):
        self.chrome.enter()
        self.draw()

    def handle_scroll_up(self):
        if self.active_tab:
            self.active_tab.scroll_up()
            self.draw()

    def handle_scroll_down(self):
        if self.active_tab:
            self.active_tab.scroll_down()
            self.draw()

    def handle_page_up(self):
        if self.active_tab:
            self.active_tab.scroll_page_up()
            self.draw()

    def handle_page_down(self):
        if self.active_tab:
            self.active_tab.scroll_page_down()
            self.draw()

    def handle_click(self, event):
        if event.y < self.chrome.bottom:
            self.chrome.click(event.x, event.y)
        else:
            tab_y = event.y - self.chrome.bottom
            self.active_tab.click(event.x, tab_y)
        self.draw()
        # if self.active_tab:
        #     self.active_tab.click(event.x, event.y)
        #     self.draw()

    def handle_scroll(self, action, value):
        if self.active_tab:
            self.active_tab.move(action, value)
            self.draw()

    def handle_resize(self, event):
        if self.active_tab:
            self.active_tab.window_resize(event)
            self.draw()

    def draw(self):
        self.canvas.delete("all")
        if self.active_tab:
            self.active_tab.draw(self.canvas, self.chrome.bottom)
        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)

    def new_tab(self, url):
        new_tab = Tab(self, HEIGHT - self.chrome.bottom)
        new_tab.load(url)
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        self.draw()


class Tab:
    def __init__(self, browser, tab_height):
        self.browser = browser  # Reference to browser for accessing canvas/scrollbar
        self.history = []
        self.nodes = []  # Not used but referenced in book (worried if I remove it something later on will need it)
        
        # Tab-specific state (moved from Browser)
        self.scroll = 0
        self.url = None
        self.document = None
        self.display_list = []
        self.content_height = 0
        self.tab_height = tab_height

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    def scroll_up(self):
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        # Update scrollbar
        self.browser.canvas.configure(yscrollcommand=self.browser.scrollbar.set(
            self.scroll / self.content_height if self.content_height > 0 else 0,
            (self.scroll + self.tab_height) / self.content_height if self.content_height > 0 else 1
        ))

    def scroll_down(self):
        if self.document:
            max_y = max(self.document.height + 2*VSTEP - self.tab_height, 0)
            self.scroll = min(self.scroll + SCROLL_STEP, max_y)
            # Update scrollbar
            self.browser.canvas.configure(yscrollcommand=self.browser.scrollbar.set(
                self.scroll / self.content_height if self.content_height > 0 else 0,
                (self.scroll + HEIGHT) / self.content_height if self.content_height > 0 else 1
            ))

    def scroll_page_up(self):
        self.scroll = max(self.scroll - HEIGHT, 0)

    def scroll_page_down(self):
        if self.document:
            max_y = max(self.document.height + 2*VSTEP - HEIGHT, 0)
            self.scroll = min(self.scroll + HEIGHT, max_y)

    def click(self, x, y):
        # Convert canvas coordinates to document coordinates
        y += self.scroll
        
        # Find all objects that contain the click point
        if not self.document:
            return
            
        objs = [obj for obj in tree_to_list(self.document, []) 
                if obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height]
        if not objs: 
            return
            
        elt = objs[-1].node  # Most specific element
        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "a" and "href" in elt.attributes:
                url = self.url.resolve(elt.attributes["href"])
                return self.load(url)
            elt = elt.parent

    def window_resize(self, event):
        global CANVAS_WIDTH, CANVAS_HEIGHT
        CANVAS_WIDTH, CANVAS_HEIGHT = event.width, event.height

        if hasattr(self, 'document') and self.document:
            self.document.layout()
            self.display_list = []
            paint_tree(self.document, self.display_list)
            self.update_scroll_region()

    def load(self, url):
        self.history.append(url)
        self.url = url
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
            self.browser.window.update_idletasks()
            CANVAS_WIDTH = self.browser.canvas.winfo_width()
            CANVAS_HEIGHT = self.browser.canvas.winfo_height()

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

    def update_scroll_region(self):
        """Set the scrollable region of the canvas"""
        if hasattr(self, 'content_height'):
            self.browser.canvas.configure(scrollregion=(0, 0, CANVAS_WIDTH, self.content_height))
        else:
            # Use actual canvas dimensions as fallback
            actual_width = self.browser.canvas.winfo_width() or WIDTH
            actual_height = self.browser.canvas.winfo_height() or HEIGHT
            self.browser.canvas.configure(scrollregion=(0, 0, actual_width, actual_height))

    def move(self, action, value):
        if not self.document:
            return

        max_scroll = max(self.document.height + 2*VSTEP - self.tab_height, 0)

        if action == "moveto":
            fraction = float(value)
            fraction = max(0.0, min(fraction, 1.0))
            self.scroll = int(fraction * max_scroll)

        # Update scrollbar thumb position
        content_height = self.document.height + 2 * VSTEP
        visible_fraction = self.tab_height / content_height if content_height > 0 else 1.0

        if max_scroll > 0:
            scroll_fraction = self.scroll / max_scroll
            scroll_fraction = min(scroll_fraction, 1.0 - visible_fraction)
            scroll_fraction = max(scroll_fraction, 0.0)

            top = scroll_fraction
            bottom = top + visible_fraction
        else:
            top, bottom = 0, 1

        self.browser.scrollbar.set(top, bottom)

    def draw(self, canvas, offset):
        for cmd in self.display_list:
            if cmd.top > self.scroll + self.tab_height: 
                continue
            if cmd.bottom < self.scroll: 
                continue
            cmd.execute(self.scroll - offset, canvas)

# "browser chrome" (or just "chrome") refers to all the parts of a web browser's interface that are not the actual webpage content.
# Basically, it's everything that frames and surrounds the "canvas", e.g. URL bar, back and forward buttons etc.
class Chrome:
    def __init__(self, browser):
        self.browser = browser
        self.font = get_font(20, "normal", "roman")
        self.font_height = self.font.metrics("linespace")
        self.padding = 5
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding
        plus_width = self.font.measure("+") + 2 * self.padding
        self.newtab_rect = Rect(self.padding, self.padding, self.padding + plus_width, self.padding + self.font_height)
        self.bottom = self.tabbar_bottom
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2 * self.padding
        self.bottom = self.urlbar_bottom
        back_width = self.font.measure("<") + 2 * self.padding
        self.back_rect = Rect(self.padding, self.urlbar_top + self.padding, self.padding + back_width, self.urlbar_bottom - self.padding)
        self.address_rect = Rect(self.back_rect.top + self.padding, self.urlbar_top + self.padding, WIDTH - self.padding, self.urlbar_bottom - self.padding)
        self.focus = None
        self.address_bar = ""

    def keypress(self, char):
        if self.focus == "address bar":
            self.address_bar += char

    def enter(self):
        if self.focus == "address bar":
            self.browser.active_tab.load(URL(self.address_bar))
            self.focus = None

    def tab_rect(self, i):
        tabs_start = self.newtab_rect.right + self.padding
        tab_width = self.font.measure("Tab X") + 2 * self.padding # Using "Tab X" as a placeholder for tab width as the letter X is usually the widest letter
        return Rect(tabs_start + tab_width * i, self.tabbar_top, tabs_start + tab_width * (i + 1), self.tabbar_bottom)

    def paint(self):
        cmds = []
        # White background for the tab bar
        cmds.append(DrawRect(Rect(0, 0, WIDTH, self.bottom), "white"))
        cmds.append(DrawLine(0, self.bottom, WIDTH, self.bottom, "black", 1))
        cmds.append(DrawOutline(self.newtab_rect, "black", 1))
        # Fix: swap font and color parameters
        cmds.append(DrawText(self.newtab_rect.left + self.padding, self.newtab_rect.top, "+", "black", self.font))
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            # Draw tab outline and text
            cmds.append(DrawLine(bounds.left, 0, bounds.left, bounds.bottom, "black", 1))
            cmds.append(DrawLine(bounds.right, 0, bounds.right, bounds.bottom, "black", 1))
            # Fix: swap font and color parameters
            cmds.append(DrawText(bounds.left + self.padding, bounds.top + self.padding, "Tab {}".format(i), "black", self.font))
            
            # Highlight the active tab
            if tab == self.browser.active_tab:
                cmds.append(DrawLine(0, bounds.bottom, bounds.left, bounds.bottom, "black", 1))
                cmds.append(DrawLine(bounds.right, bounds.bottom, WIDTH, bounds.bottom, "black", 1))

            if self.focus == "address bar":
                cmds.append(DrawText(
                    self.address_rect.left + self.padding,
                    self.address_rect.top,
                    self.address_bar, "black", self.font))
                w = self.font.measure(self.address_bar)
                cmds.append(DrawLine(
                    self.address_rect.left + self.padding + w,
                    self.address_rect.top,
                    self.address_rect.left + self.padding + w,
                    self.address_rect.bottom,
                    "red", 1))
            else:
                url = str(self.browser.active_tab.url)
                cmds.append(DrawText(
                    self.address_rect.left + self.padding,
                    self.address_rect.top,
                    url, "black", self.font))

            cmds.append(DrawOutline(self.back_rect, "black", 1))
            cmds.append(DrawText(self.back_rect.left + self.padding, self.back_rect.top, "<", "black", self.font))
        return cmds

    def click(self, x, y):
        self.focus = None
        if self.newtab_rect.contains_point(x, y):
            self.browser.new_tab(URL("https://browser.engineering/"))
        elif self.address_rect.contains_point(x, y):
            self.focus = "address bar"
            self.address_bar = ""
        elif self.back_rect.contains_point(x, y):
            self.browser.active_tab.go_back()
        else:
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).contains_point(x, y):
                    self.browser.active_tab = tab
                    break

class DrawOutline: # Draws a rectangle border for the new tab button and other elements
    def __init__(self, rect, color, thickness):
        self.rect = rect
        self.color = color
        self.thickness = thickness

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.rect.left, self.rect.top - scroll,
            self.rect.right, self.rect.bottom - scroll,
            width=self.thickness,
            outline=self.color)

class Rect:
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def contains_point(self, x, y):
        return x >= self.left and x < self.right and y >= self.top and y < self.bottom

if __name__ == "__main__":
    print("Welcome to the Python Browser!\n")
    browser = Browser()
    if len(sys.argv) == 1:
        browser.new_tab(URL(DEFAULT_PAGE))
    elif len(sys.argv) >= 2:
        web_urls = sys.argv[1:]
        for web_url in web_urls:
            try:
                browser.new_tab(URL(web_url))
            except Exception as e:
                print(f"Error loading {web_url}: {e}")
    else:
        print("Usage: python browser.py <url>")
        sys.exit(1)
    tk.mainloop()