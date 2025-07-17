from requests import URL, Text, Element, HTMLParser  # ✅ Add HTMLParser import

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
# SCROLL_STEP = 100 # Not used, tkinter handles scrolling natively

def get_font(size, weight="normal", style="roman"):
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight, slant=style)
        label = tk.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]


class Layout:
    def __init__(self, tree):  # Now takes a tree, not tokens
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 16
        self.line = []
        self.centre_line = False
        self.super_text = False
        
        # Use recurse method for tree traversal
        self.recurse(tree)
        self.flush()  # Flush any remaining words in the last line

    def open_tag(self, tag):
        if tag == "i":
            self.style = "italic"
        elif tag == "b":
            self.weight = "bold"
        elif tag == "small":
            self.size -= 2
        elif tag == "big":
            self.size += 2
        elif tag == "br":
            self.flush()
        elif tag.startswith("h1"):
            self.flush()  # Flush current line before heading
            self.size += 4
        elif tag == "sup":
            self.size //= 2
            self.super_text = True

    def close_tag(self, tag):
        if tag == "i":
            self.style = "roman"
        elif tag == "b":
            self.weight = "normal"
        elif tag == "small":
            self.size += 2
        elif tag == "big":
            self.size -= 2
        elif tag == "p":
            self.flush()
            self.cursor_y += VSTEP  # Extra space between paragraphs
        elif tag == "h1":
            self.centre_line = True
            self.size -= 4
            self.flush()
        elif tag == "sup":
            self.size *= 2
        elif tag in ["div", "section", "article", "header", "footer", "main", "nav"]:
            self.flush()
        elif tag == "br":
            self.flush()

    def recurse(self, tree):
        if isinstance(tree, Text):
            for word in tree.text.split():
                self.word(word)
        else:
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def flush(self):
        if not self.line:
            return
        
        metrics = [font.metrics() for _, _, font, _ in self.line]
        max_ascent = max([metric['ascent'] for metric in metrics])
        max_descent = max([metric['descent'] for metric in metrics])

        if self.centre_line:
            total_width = sum([font.measure(word) for _, word, font, _ in self.line])
            total_space = CANVAS_WIDTH - HSTEP * 2  # Keep some space on the sides
            offset = (total_space - total_width) // 2

            # Adjust for centring (now with 4-tuple)
            self.line = [(x + offset, word, font, is_super) for x, word, font, is_super in self.line]
            self.centre_line = False

        baseline = self.cursor_y + max_ascent

        for x, word, font, is_super in self.line:
            y = baseline - font.metrics("ascent")
            if is_super:
                y = baseline - max_ascent  # Move THIS word up
            self.display_list.append((x, y, word, font))

        # Move cursor down for next line
        self.cursor_y = baseline + max_descent
        self.cursor_x = HSTEP
        self.line = []

    # def token(self, tok): # Replaced by recurse method
    #     if isinstance(tok, Text):
    #         # Split text into lines first (preserve explicit newlines)
    #         lines = tok.text.split('\n')
            
    #         for line_idx, line in enumerate(lines):
    #             # For each line, process word by word
    #             words = line.split()
                
    #             for word in words:
    #                 self.word(word)
                
    #             # After processing all words in a line, move to next line for explicit newline
    #             # (but not after the last line of this text token)
    #             if line_idx < len(lines) - 1:
    #                 self.flush()  # Flush current line
    #                 self.cursor_y += VSTEP # Add extra space for explicit newline
                    
    #     elif isinstance(tok, Element): # Handle formatting tags
    #         if tok.tag == "i":
    #             self.style = "italic"
    #         elif tok.tag == "/i":
    #             self.style = "roman"
    #         elif tok.tag == "b":
    #             self.weight = "bold"
    #         elif tok.tag == "/b":
    #             self.weight = "normal"
    #         elif tok.tag == "small":
    #             self.size -= 2
    #         elif tok.tag == "/small":
    #             self.size += 2
    #         elif tok.tag == "big":
    #             self.size += 2
    #         elif tok.tag == "/big":
    #             self.size -= 2
    #         elif tok.tag == "br":
    #             self.flush()
    #         elif tok.tag == "/p":
    #             self.flush()
    #             self.cursor_y += VSTEP  # Extra space between paragraphs
    #         elif tok.tag.startswith("h1"):
    #             self.flush()  # Flush current line before heading
    #             self.size += 4
    #         elif tok.tag == "/h1":
    #             self.centre_line = True
    #             self.size -= 4
    #         elif tok.tag == "sup":
    #             self.size //= 2
    #             self.super_text = True
    #         elif tok.tag == "/sup":
    #             self.size *= 2

    def word(self, word):
        while word:
            font = get_font(self.size, self.weight, self.style)
            w = font.measure(word)
            
            # Check if word fits on current line
            if self.cursor_x + w > CANVAS_WIDTH - HSTEP:
                split_word = None

                for index, char in enumerate(word):
                    partial_word = word[:index + 1]
                    if self.cursor_x + font.measure(partial_word + "-") < CANVAS_WIDTH - HSTEP:
                        split_word = partial_word
                    else:
                        break

                if not split_word:
                    # If no split word found, just flush current line
                    self.flush()
                else:
                    first_part = split_word + "-"
                    self.add_word_to_line(first_part, font)
                    self.flush()  # Flush current line after adding first part

                    # Print remaining part if word
                    word = word[len(split_word):]
                    continue
            else:
                # Add word to current line
                self.add_word_to_line(word, font)
                break

    def add_word_to_line(self, word, font):
        """Helper method to add word to current line"""
        is_super = False
        w = font.measure(word)
        
        if self.super_text:
            previous_space = font.measure(" ")
            reduced_space = previous_space // 2
            self.cursor_x -= (previous_space + reduced_space)
            is_super = True
        
        self.line.append((self.cursor_x, word, font, is_super))
        
        if self.super_text:
            self.cursor_x += w
            self.super_text = False
        else:
            self.cursor_x += w + font.measure(" ")

class Browser:
    def __init__(self):
        self.nodes = []
        self.window = tk.Tk()
        self.canvas = tk.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        # Working scrollbar setup
        self.scrollbar = tk.Scrollbar(self.window, orient="vertical", command=self.canvas.yview)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.pack(side="left", fill="both", expand=1)
        
        # Connect canvas to scrollbar
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Use in-built scrolling mechanism
        # Make canvas focusable for keyboard events
        self.canvas.configure(highlightthickness=0)
        self.canvas.focus_set()
        
        # Bind arrow keys to canvas
        self.canvas.bind("<Up>", lambda e: self.canvas.yview_scroll(-1, "units"))   
        self.canvas.bind("<Down>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.canvas.bind("<Page_Up>", lambda e: self.canvas.yview_scroll(-1, "pages"))
        self.canvas.bind("<Page_Down>", lambda e: self.canvas.yview_scroll(1, "pages"))
        self.window.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "pages"))
        self.window.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "pages"))
        
        # Keep resize event
        self.canvas.bind("<Configure>", self.window_resize)

    def window_resize(self, event):
        global CANVAS_WIDTH, CANVAS_HEIGHT
        CANVAS_WIDTH, CANVAS_HEIGHT = event.width, event.height

        if hasattr(self, 'tree'):
            self.display_list = Layout(self.tree).display_list
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
            tree = Text(body, None)  # Create a text node
        else:
            body = url.request()
            tree = HTMLParser(body).parse()  # Returns single Element tree

        self.tree = tree
        
        # Set initial canvas dimensions if not set
        global CANVAS_WIDTH, CANVAS_HEIGHT
        if CANVAS_WIDTH == 0:
            self.window.update_idletasks()
            CANVAS_WIDTH = self.canvas.winfo_width()
            CANVAS_HEIGHT = self.canvas.winfo_height()
        
        self.display_list = Layout(tree).display_list  # Pass tree directly
        
        # Calculate content height and set scroll region
        if self.display_list:
            self.content_height = max(y for x, y, word, font in self.display_list) + VSTEP
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

    def draw(self):
        self.canvas.delete("all")
        # Draw ALL content - tkinter will handle what's visible
        for x, y, word, font in self.display_list:
            self.canvas.create_text(x, y, text=word, font=font, anchor="nw")


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