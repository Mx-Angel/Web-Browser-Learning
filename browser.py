# ==============================================================================
# PYTHON BROWSER - Main Application File
# ==============================================================================
# This file contains the core browser functionality including:
# - Browser window management
# - Tab system with multiple pages
# - Chrome UI (tab bar, address bar, back button)
# - Event handling and user interaction
# ==============================================================================

# First-party import statements
from requests import URL, Text, Element, HTMLParser
from cssparser import CSSParser, style, cascade_priority
from layout import DocumentLayout, tree_to_list, paint_tree
from drawing import DrawText, DrawLine, DrawRect, DrawOutline, Rect
from fonts import get_font

# First-party constant imports
from constants import WIDTH, HEIGHT, CANVAS_WIDTH, CANVAS_HEIGHT, SCROLL_STEP, DEFAULT_PAGE, VSTEP

# Standard library imports
import tkinter as tk
import sys

# ==============================================================================
# GLOBAL VARIABLES AND CONSTANTS
# ==============================================================================

# Default CSS rules applied to all pages
DEFAULT_STYLE_SHEET = CSSParser(open("browser.css").read()).parse()

# ==============================================================================
# MAIN BROWSER CLASS
# ==============================================================================

class Browser:
    """
    Main browser application class.
    
    Responsibilities:
    - Owns the tkinter window and canvas
    - Manages the list of tabs and which one is active
    - Handles all user input events (clicks, keyboard, scrolling)
    - Coordinates drawing of tab content and chrome UI
    - Creates new tabs and manages tab switching
    """
    
    def __init__(self):
        """
        Initialize the main browser window and UI components.
        
        Creates the tkinter window, canvas, scrollbar, and chrome UI.
        Sets up all event bindings for user interaction.
        """
        # Tab management
        self.tabs = []           # List of all open tabs
        self.active_tab = None   # Currently visible tab
        
        # Create the main browser window
        self.window = tk.Tk()
        self.canvas = tk.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT,
            bg="white"
        )
        
        # Set up scrollbar for page content
        # Note: The scrollbar is controlled by the active tab
        self.scrollbar = tk.Scrollbar(self.window, orient="vertical", command=self.handle_scroll)
        self.scrollbar.pack(side="right", fill="y") # Scrollbar on the right side, scrollbar must go first
        self.canvas.pack(side="left", fill="both", expand=1) # Canvas fills the rest of the window (left side)
        
        # Make canvas focusable so it can receive keyboard events
        self.canvas.configure(highlightthickness=0)
        self.canvas.focus_set() # Focus the canvas so it can receive keyboard input on startup
        
        # ==============================================================================
        # EVENT BINDING
        # ==============================================================================
        # The Browser class handles ALL events and forwards them to appropriate handlers
        
        # Keyboard scrolling events
        self.canvas.bind("<Up>", lambda e: self.handle_scroll_up())   
        self.canvas.bind("<Down>", lambda e: self.handle_scroll_down())
        self.canvas.bind("<Page_Up>", lambda e: self.handle_page_up())
        self.canvas.bind("<Page_Down>", lambda e: self.handle_page_down())
        
        # Mouse wheel scrolling (Linux)
        self.window.bind("<Button-4>", lambda e: self.handle_scroll_up())
        self.window.bind("<Button-5>", lambda e: self.handle_scroll_down())
        
        # Mouse clicks
        self.window.bind("<Button-1>", lambda e: self.handle_click(e))
        
        # Window resize events
        self.canvas.bind("<Configure>", lambda e: self.handle_resize(e))
        
        # Keyboard input for address bar
        self.window.bind("<Key>", self.handle_key)     # Individual characters
        self.window.bind("<Return>", self.handle_enter) # Enter key

        # Create the chrome (browser UI) - tab bar, address bar, etc.
        self.chrome = Chrome(self)

    # ==============================================================================
    # EVENT HANDLERS
    # ==============================================================================
    # These methods receive events from tkinter and forward them to the right place

    def handle_key(self, e: tk.Event):
        """Handle keyboard character input (for typing in address bar)."""
        # Ignore special keys (arrows, function keys, etc.)
        if len(e.char) == 0: return
        # Only accept printable ASCII characters
        if not (0x20 <= ord(e.char) < 0x7f): return
        
        # Forward to chrome (which handles address bar input)
        self.chrome.keypress(e.char)
        self.draw()  # Redraw to show new character

    def handle_enter(self, e: tk.Event):
        """Handle Enter key press (for submitting address bar)."""
        self.chrome.enter()
        self.draw()

    def handle_scroll_up(self):
        """Scroll the active tab up by one step."""
        if self.active_tab:
            self.active_tab.scroll_up()
            self.draw()

    def handle_scroll_down(self):
        """Scroll the active tab down by one step."""
        if self.active_tab:
            self.active_tab.scroll_down()
            self.draw()

    def handle_page_up(self):
        """Scroll the active tab up by one page."""
        if self.active_tab:
            self.active_tab.scroll_page_up()
            self.draw()

    def handle_page_down(self):
        """Scroll the active tab down by one page."""
        if self.active_tab:
            self.active_tab.scroll_page_down()
            self.draw()

    def handle_click(self, e: tk.Event):
        """
        Handle mouse clicks.
        
        Determines whether the click was in the chrome area (tab bar, address bar)
        or in the page content area, and forwards to the appropriate handler.
        """

        # There are 2 coordinate regions, the chrome and the page content.
        # The chrome is at the top of the window, and the page content starts below it
        if e.y < self.chrome.bottom:
            # Click was in the chrome area (tab bar, address bar, etc.)
            self.chrome.click(e.x, e.y)
        else:
            # Click was in the page content area
            # Adjust y coordinate to account for chrome height
            tab_y = e.y - self.chrome.bottom
            if self.active_tab:
                self.active_tab.click(e.x, tab_y)
        self.draw()

    def handle_scroll(self, action, value):
        """Handle scrollbar drag events."""
        if self.active_tab:
            self.active_tab.move(action, value)
            self.draw()

    def handle_resize(self, event):
        """Handle window resize events."""
        if self.active_tab:
            self.active_tab.window_resize(event)
            self.draw()

    # ==============================================================================
    # DRAWING AND TAB MANAGEMENT
    # ==============================================================================

    def draw(self):
        """
        Main drawing method - renders the entire browser window.
        
        Drawing order:
        1. Clear the canvas
        2. Draw the active tab's page content (if any)
        3. Draw the chrome UI on top (tab bar, address bar, back button, etc.)
        """
        self.canvas.delete("all")  # Clear everything
        
        # Draw the active tab's content first (so chrome appears on top)
        if self.active_tab:
            # Pass chrome.bottom as offset so tab content appears below chrome
            self.active_tab.draw(self.canvas, self.chrome.bottom)
        
        # Draw chrome UI on top (with scroll=0 so it never scrolls)
        for cmd in self.chrome.paint():
            cmd.execute(0, self.canvas)  # scroll=0 keeps chrome fixed

    def new_tab(self, url):
        """
        Create a new tab and make it active.
        
        :param url: URL object to load in the new tab
        """
        # Calculate available height for tab content (total height - chrome height)
        tab_height = HEIGHT - self.chrome.bottom
        
        # Create new tab with reference to this browser
        new_tab = Tab(self, tab_height)
        new_tab.load(url)  # Load the specified URL
        
        # Make this the active tab and add to tabs list
        self.active_tab = new_tab
        self.tabs.append(new_tab)
        
        # Redraw to show the new tab
        self.draw()

# ==============================================================================
# TAB CLASS
# ==============================================================================

class Tab:
    """
    Represents a single browser tab containing one web page.
    
    Responsibilities:
    - Load and parse HTML/CSS content
    - Manage page scrolling state
    - Handle page-specific clicks (like following links)
    - Draw page content to the canvas
    - Maintain browsing history
    """

    def __init__(self, browser: Browser, tab_height: int):
        """
        Initialize a new browser tab.
        
        :param browser: Reference to the main Browser instance
        :param tab_height: Available height in pixels for page content
        """
        self.browser = browser
        self.tab_height = tab_height
        
        # Browsing history for back button
        self.history = []
        
        # Legacy - kept for compatibility with tutorial code
        self.nodes = []
        
        # Page state
        self.scroll = 0              # Current scroll position (Rename to scroll positon?)
        self.url = None              # Current page URL
        self.document = None         # Root of layout tree
        self.display_list = []       # List of drawing commands for page content
        self.content_height = 0      # Total height of page content

    def go_back(self):
        """Navigate to the previous page in history."""
        if len(self.history) > 1:
            # Remove current page from history
            self.history.pop()
            # Get previous page
            back = self.history.pop()
            # Load it (this will add it back to history)
            self.load(back)

    # ==============================================================================
    # SCROLLING METHODS
    # ==============================================================================

    # Mouse scrolling methods
    def scroll_up(self):
        """Scroll up by one step, updating scrollbar."""
        self.scroll = max(self.scroll - SCROLL_STEP, 0)
        # Update scrollbar position to reflect new scroll state
        self.browser.scrollbar.set(
            self.scroll / self.content_height if self.content_height > 0 else 0,
            (self.scroll + self.tab_height) / self.content_height if self.content_height > 0 else 1
        )

    def scroll_down(self):
        """Scroll down by one step, updating scrollbar."""
        if self.document and self.document.height is not None:
            # Calculate maximum scroll (don't scroll past end of content)
            max_y = max(self.document.height + 2 * VSTEP - self.tab_height, 0)
            self.scroll = min(self.scroll + SCROLL_STEP, max_y)
            # Update scrollbar
            self.browser.scrollbar.set(
                self.scroll / self.content_height if self.content_height > 0 else 0,
                (self.scroll + HEIGHT) / self.content_height if self.content_height > 0 else 1
            )

    # Keyboard scrolling methods
    def scroll_page_up(self):
        """Scroll up by one full page."""
        self.scroll = max(self.scroll - HEIGHT, 0)

    def scroll_page_down(self):
        """Scroll down by one full page."""
        if self.document and self.document.height is not None:
            max_y = max(self.document.height + 2 * VSTEP - HEIGHT, 0)
            self.scroll = min(self.scroll + HEIGHT, max_y)

    # ==============================================================================
    # USER INTERACTION
    # ==============================================================================

    def click(self, x: int, y: int):
        """
        Handle clicks within the page content area.
        
        This method:
        1. Converts canvas coordinates to document coordinates
        2. Finds all layout objects at the click position
        3. Determines the most specific element clicked
        4. Checks if it's a link and follows it if so

        :param x: X coordinate of the click (canvas coordinates)
        :param y: Y coordinate of the click (canvas coordinates)
        :return: None
        """
        # Convert canvas coordinates to document coordinates
        # (add how far the page has scrolled, as text content will differ depending on scroll position)
        y += self.scroll
        
        if not self.document:
            return
            
        # Find all layout objects that contain the click point
        # tree_to_list flattens the layout tree into a list
        objs = [obj for obj in tree_to_list(self.document, []) if obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height]
        
        if not objs: 
            return  # Click didn't hit any content
            
        # Get the most specific (deepest) element at the click position
        # objs[-1] is the last in the list, which is the most nested
        # When looping to create the list the x and y values will become more and more "true"
        # as we go deeper into the tree, this means the last element is the most specific element
        # and the element we want to interact with
        elt = objs[-1].node
        
        # Walk up the DOM tree looking for a clickable element, though we got the most specific element
        # we still need to check if it is a link or not, as the most specific element may not be a link
        # (e.g. it could be a text node or a div)
        # We will keep going up the tree until we find an anchor tag or reach the root
        # This allows us to follow links even if they are nested inside other elements
        while elt:
            if isinstance(elt, Text):
                # Text nodes can't be links themselves
                pass
            elif elt.tag == "a" and "href" in elt.attributes:
                # Found a link! Follow it
                if self.url is not None:
                    url = self.url.resolve(elt.attributes["href"])
                    return self.load(url)
                else:
                    raise Exception("Cannot resolve link without a base URL")
            elt = elt.parent  # Move up to parent element

    # ==============================================================================
    # PAGE LOADING AND LAYOUT
    # ==============================================================================

    def window_resize(self, e: tk.Event):
        """Handle window resize by re-laying out the page."""
        global CANVAS_WIDTH, CANVAS_HEIGHT
        CANVAS_WIDTH, CANVAS_HEIGHT = e.width, e.height

        if hasattr(self, 'document') and self.document:
            # Re-layout with new dimensions
            self.document.layout()
            self.display_list = []
            paint_tree(self.document, self.display_list)
            self.update_scroll_region()

    def load(self, url: URL):
        """
        Load a new page from the given URL.
        
        This is the main page loading pipeline:
        1. Add URL to history
        2. Fetch and parse HTML content
        3. Load and parse CSS stylesheets
        4. Apply CSS styles to HTML elements
        5. Create layout tree
        6. Generate display list (drawing commands)
        7. Update scrolling region

        :param url: URL object representing the page to load
        """
        # Add to browsing history
        self.history.append(url)
        self.url = url
        
        # ==============================================================================
        # STEP 1: FETCH AND PARSE HTML
        # ==============================================================================
        
        if url.scheme == "file":
            # Load local file
            if url.path is None:
                raise ValueError("File URL does not have a valid path")
            with open(url.path, 'r', encoding='utf8') as f:
                body = f.read()
                tree = HTMLParser(body).parse()
        elif url.entity == "data":
            # Handle data: URLs
            if url.content is not None:
                _, content = url.parse_data_url(url.content)
            tree = HTMLParser(content).parse()
        elif url.entity == "view-source":
            # Show page source as plain text
            body = url.request()
            tree = Text(body, None)
        else:
            # Fetch from web server
            body = url.request()
            tree = HTMLParser(body).parse()

        self.tree = tree  # Store parsed HTML tree
        
        # ==============================================================================
        # STEP 2: LOAD CSS STYLESHEETS
        # ==============================================================================
        
        # Start with default browser styles
        rules = DEFAULT_STYLE_SHEET.copy()

        # Find linked stylesheets in the HTML
        links = [ # Figure this out again
            node.attributes["href"]
            for node in tree_to_list(tree, [])
            if isinstance(node, Element)
            and node.tag == "link"
            and node.attributes.get("rel") == "stylesheet"
            and "href" in node.attributes
        ]

        # Load each stylesheet and parse its CSS rules
        for link in links:
            style_url = url.resolve(link)
            try:
                body = style_url.request()
                rules.extend(CSSParser(body).parse())
            except:
                continue  # Skip failed stylesheets

        # ==============================================================================
        # STEP 3: APPLY CSS STYLES
        # ==============================================================================
        
        # Apply all CSS rules to HTML elements
        # cascade_priority determines which rules take precedence
        style(self.tree, sorted(rules, key=cascade_priority)) # Figure out how cascade_priority works again

        # ==============================================================================
        # STEP 4: CREATE LAYOUT TREE
        # ==============================================================================
        
        # Ensure canvas dimensions are set
        global CANVAS_WIDTH, CANVAS_HEIGHT
        if CANVAS_WIDTH == 0:
            self.browser.window.update_idletasks() # Force idle tasks to complete so we can get accurate dimensions
            CANVAS_WIDTH = self.browser.canvas.winfo_width()
            CANVAS_HEIGHT = self.browser.canvas.winfo_height()

        # Create layout tree and compute positions/sizes
        self.document = DocumentLayout(self.tree)
        self.document.layout()
        
        # ==============================================================================
        # STEP 5: GENERATE DISPLAY LIST
        # ==============================================================================
        
        # Create list of drawing commands from layout tree
        self.display_list = []
        paint_tree(self.document, self.display_list)
        
        # Calculate total content height for scrolling
        if self.display_list:
            # Find the maximum bottom position of all commands, but only the last command
            # will be assigned to self.content_height as y coordinates are relative to the top of the canvas
            # and the bottom of the canvas is at the bottom of the last command
            self.content_height = max(cmd.bottom for cmd in self.display_list) + VSTEP
        else:
            self.content_height = 0

        self.update_scroll_region()

    def update_scroll_region(self):
        """Configure the canvas scroll region for this tab's content."""
        if hasattr(self, 'content_height'):
            self.browser.canvas.configure(scrollregion=(0, 0, CANVAS_WIDTH, self.content_height))
        else:
            # Fall back to window dimensions
            actual_width = self.browser.canvas.winfo_width() or WIDTH
            actual_height = self.browser.canvas.winfo_height() or HEIGHT
            self.browser.canvas.configure(scrollregion=(0, 0, actual_width, actual_height))

    def move(self, action: str, value: float):
        """
        Handle scrollbar drag events.
        
        :param action: "moveto" for scrollbar dragging
        :param value: Fraction (0.0 to 1.0) representing scroll position
        """
        if not self.document:
            return

        # Calculate maximum scroll position
        if self.document.height is not None: # Note document means the whole canvas, not just the visible area
            # 2 * VSTEP is added to account for vertical padding in the layout
            max_scroll = max(self.document.height + 2 * VSTEP - self.tab_height, 0)

        if action == "moveto":
            # Convert fraction to actual scroll position
            fraction = float(value)
            fraction = max(0.0, min(fraction, 1.0))  # Clamp to valid range
            self.scroll = int(fraction * max_scroll)

        # Update scrollbar thumb position
        if self.document.height is not None: 
            content_height = self.document.height + 2 * VSTEP

        # What fraction of the content is visible in the tab
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

    def draw(self, canvas: tk.Canvas, offset: float):
        """
        Draw this tab's content to the canvas.

        :param canvas: tkinter Canvas to draw on
        :param offset: Vertical offset (height of chrome area)
        """
        for cmd in self.display_list:
            # Skip drawing commands that are outside the visible area
            if cmd.top > self.scroll + self.tab_height: 
                continue  # Below visible area
            if cmd.bottom < self.scroll: 
                continue  # Above visible area
            
            # Execute the drawing command with combined scroll and offset
            # self.scroll moves content up/down with page scrolling
            # offset moves content down to make room for chrome at top
            cmd.execute(self.scroll - offset, canvas)

# ==============================================================================
# CHROME (BROWSER UI) CLASS
# ==============================================================================

class Chrome:
    """
    Browser chrome (user interface elements).
    
    "Chrome" refers to all the parts of a browser that aren't webpage content:
    - Tab bar with individual tabs and "+" button
    - Address bar for entering URLs
    - Back button for navigation
    - Any other browser controls
    
    This class manages the layout and interaction of these UI elements.
    """

    def __init__(self, browser: Browser):
        """
        Initialize the browser chrome (UI elements).
        
        :param browser: Reference to the main Browser instance
        """
        self.browser = browser  # Reference to main browser
        
        # Font and spacing for chrome UI
        self.font = get_font(20, "normal", "roman")
        self.font_height = self.font.metrics("linespace")
        self.padding = 5
        
        # ==============================================================================
        # TAB BAR LAYOUT
        # ==============================================================================
        
        # Tab bar occupies the top of the chrome area
        self.tabbar_top = 0
        self.tabbar_bottom = self.font_height + 2 * self.padding
        
        # "+" button for creating new tabs
        plus_width = self.font.measure("+") + 2 * self.padding
        self.newtab_rect = Rect(
            self.padding, self.padding, 
            self.padding + plus_width, self.padding + self.font_height
        )
        
        # Total chrome height so far
        self.bottom = self.tabbar_bottom
        
        # ==============================================================================
        # ADDRESS BAR LAYOUT
        # ==============================================================================
        
        # Address bar goes below the tab bar
        self.urlbar_top = self.tabbar_bottom
        self.urlbar_bottom = self.urlbar_top + self.font_height + 2 * self.padding
        
        # Update total chrome height
        self.bottom = self.urlbar_bottom
        
        # Back button (shows "<")
        back_width = self.font.measure("<") + 2 * self.padding
        self.back_rect = Rect(
            self.padding, self.urlbar_top + self.padding, 
            self.padding + back_width, self.urlbar_bottom - self.padding
        )
        
        # Address input field (takes up remaining width)
        self.address_rect = Rect(
            self.back_rect.right + self.padding, self.urlbar_top + self.padding, 
            WIDTH - self.padding, self.urlbar_bottom - self.padding
        )
        
        # Address bar state
        self.focus = None # Which UI element has focus (None or "address bar")
        self.address_bar = "" # Current text in address bar

    # ==============================================================================
    # INPUT HANDLING
    # ==============================================================================

    def keypress(self, char: str):
        """Handle character input (typing in address bar)."""
        if self.focus == "address bar":
            self.address_bar += char  # Add character to address bar text

    def enter(self):
        """Handle Enter key (submit address bar)."""
        if self.focus == "address bar":
            # Load the URL from address bar in the active tab
            if self.browser.active_tab:
                self.browser.active_tab.load(URL(self.address_bar))
            self.focus = None  # Remove focus from address bar

    # ==============================================================================
    # LAYOUT HELPERS
    # ==============================================================================

    def tab_rect(self, i: int) -> Rect:
        """
        Calculate the rectangle for tab number i.
        
        :param i: Tab index (0 for first tab, 1 for second, etc.)
        :return: Rect object representing the tab's bounds
        """
        # Tabs start after the "+" button
        tabs_start = self.newtab_rect.right + self.padding
        
        # Calculate tab width (using "Tab X" as width estimate)
        tab_width = self.font.measure("Tab X") + 2 * self.padding
        
        # Calculate this tab's position
        return Rect(
            tabs_start + tab_width * i, self.tabbar_top, 
            tabs_start + tab_width * (i + 1), self.tabbar_bottom
        )

    # ==============================================================================
    # DRAWING
    # ==============================================================================

    def paint(self):
        """
        Generate drawing commands for the entire chrome UI.
        
        :return: List of drawing command objects
        """
        cmds = []
        
        # ==============================================================================
        # BACKGROUND AND SEPARATOR
        # ==============================================================================
        
        # White background for entire chrome area
        cmds.append(DrawRect(Rect(0, 0, WIDTH, self.bottom), "white"))
        
        # Black line separating chrome from page content
        cmds.append(DrawLine(0, self.bottom, WIDTH, self.bottom, "black", 1))
        
        # ==============================================================================
        # NEW TAB BUTTON
        # ==============================================================================
        
        # Border around "+" button
        cmds.append(DrawOutline(self.newtab_rect, "black", 1))
        
        # "+" text inside button
        cmds.append(DrawText(
            self.newtab_rect.left + self.padding, self.newtab_rect.top, 
            "+", "black", self.font
        ))
        
        # ==============================================================================
        # TAB BAR
        # ==============================================================================
        
        # Draw each open tab
        for i, tab in enumerate(self.browser.tabs):
            bounds = self.tab_rect(i)
            
            # Left and right borders of tab
            cmds.append(DrawLine(bounds.left, 0, bounds.left, bounds.bottom, "black", 1))
            cmds.append(DrawLine(bounds.right, 0, bounds.right, bounds.bottom, "black", 1))
            
            # Tab label
            cmds.append(DrawText(
                bounds.left + self.padding, bounds.top + self.padding, 
                "Tab {}".format(i), "black", self.font
            ))
            
            # Highlight active tab by drawing bottom border around other tabs
            if tab == self.browser.active_tab:
                # Draw bottom border to left and right of active tab
                cmds.append(DrawLine(0, bounds.bottom, bounds.left, bounds.bottom, "black", 1))
                cmds.append(DrawLine(bounds.right, bounds.bottom, WIDTH, bounds.bottom, "black", 1))
        
        # ==============================================================================
        # ADDRESS BAR
        # ==============================================================================
        
        # Address bar content depends on whether it has focus
        if self.focus == "address bar":
            # Show user's typing with cursor
            cmds.append(DrawText(
                self.address_rect.left + self.padding,
                self.address_rect.top,
                self.address_bar, "black", self.font
            ))
            
            # Red cursor line at end of text
            w = self.font.measure(self.address_bar)
            cmds.append(DrawLine(
                self.address_rect.left + self.padding + w,
                self.address_rect.top,
                self.address_rect.left + self.padding + w,
                self.address_rect.bottom,
                "red", 1
            ))
        else:
            # Show current page URL
            if self.browser.active_tab and self.browser.active_tab.url:
                url = str(self.browser.active_tab.url)
                cmds.append(DrawText(
                    self.address_rect.left + self.padding,
                    self.address_rect.top,
                    url, "black", self.font
                ))
        
        # ==============================================================================
        # BACK BUTTON
        # ==============================================================================
        
        # Back button border
        cmds.append(DrawOutline(self.back_rect, "black", 1))
        
        # "<" symbol in back button
        cmds.append(DrawText(
            self.back_rect.left + self.padding, self.back_rect.top, 
            "<", "black", self.font
        ))
        
        return cmds

    # ==============================================================================
    # CLICK HANDLING
    # ==============================================================================

    def click(self, x: int, y: int):
        """
        Handle clicks within the chrome area.
        
        Determines which UI element was clicked and takes appropriate action:
        - New tab button: Create new tab
        - Address bar: Focus for typing
        - Back button: Go to previous page
        - Tab: Switch to that tab

        :param x: X coordinate of the click (canvas coordinates)
        :param y: Y coordinate of the click (canvas coordinates)
        """
        # Remove focus from any previously focused element
        self.focus = None
        
        # Check which UI element was clicked
        if self.newtab_rect.contains_point(x, y):
            # New tab button clicked
            self.browser.new_tab(URL("https://browser.engineering/"))
            
        elif self.address_rect.contains_point(x, y):
            # Address bar clicked - focus it for typing
            self.focus = "address bar"
            self.address_bar = ""  # Clear current text
            
        elif self.back_rect.contains_point(x, y):
            # Back button clicked
            if self.browser.active_tab:
                self.browser.active_tab.go_back()
                
        else:
            # Check if a tab was clicked
            for i, tab in enumerate(self.browser.tabs):
                if self.tab_rect(i).contains_point(x, y):
                    self.browser.active_tab = tab  # Switch to clicked tab
                    break

# ==============================================================================
# MAIN APPLICATION ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    print("Welcome to the Python Browser!\n")
    
    # Create the main browser instance
    browser = Browser()
    
    # Handle command line arguments for initial pages to load
    if len(sys.argv) == 1:
        # No arguments - load default page
        browser.new_tab(URL(DEFAULT_PAGE))
    elif len(sys.argv) >= 2:
        # Arguments provided - try to load each as a URL
        web_urls = sys.argv[1:]
        for web_url in web_urls:
            try:
                browser.new_tab(URL(web_url))
            except Exception as e:
                print(f"Error loading {web_url}: {e}")
    else:
        # This case shouldn't happen with current logic, but kept for safety
        print("Usage: python browser.py <url>")
        sys.exit(1)
    
    # Start the tkinter event loop - this keeps the browser running
    # until the user closes the window
    tk.mainloop()