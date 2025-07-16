from requests import URL, lex, show_source, Text, Tag

from requests import DEFAULT_PAGE

import tkinter as tk
import tkinter.font
import sys

# Globals
FONTS = {}

# Constants
WIDTH, HEIGHT = 1280, 720
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
    def __init__(self, tokens):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 16
        self.line = []
        
        for tok in tokens:
            self.token(tok)

        self.flush()  # Flush any remaining words in the last line

    def flush(self):
        if not self.line:
            return
        
        metrics = [font.metrics() for _, _, font in self.line]
        max_ascent = max([metric['ascent'] for metric in metrics])
        max_descent = max([metric['descent'] for metric in metrics])

        baseline = self.cursor_y + max_ascent

        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))

        # Move cursor down for next line
        self.cursor_y = baseline + max_ascent
        self.cursor_x = HSTEP
        self.line = []

    def token(self, tok):
        if isinstance(tok, Text):
            # Split text into lines first (preserve explicit newlines)
            lines = tok.text.split('\n')
            
            for line_idx, line in enumerate(lines):
                # For each line, process word by word
                words = line.split()
                
                for word in words:
                    self.word(word)
                
                # After processing all words in a line, move to next line for explicit newline
                # (but not after the last line of this text token)
                if line_idx < len(lines) - 1:
                    self.flush()  # Flush current line
                    self.cursor_y += VSTEP  # Add extra space for explicit newline
                    
        elif isinstance(tok, Tag):  # Handle formatting tags
            if tok.tag == "i":
                self.style = "italic"
            elif tok.tag == "/i":
                self.style = "roman"
            elif tok.tag == "b":
                self.weight = "bold"
            elif tok.tag == "/b":
                self.weight = "normal"
            elif tok.tag == "small":
                self.size -= 2
            elif tok.tag == "/small":
                self.size += 2
            elif tok.tag == "big":
                self.size += 2
            elif tok.tag == "/big":
                self.size -= 2
            elif tok.tag == "br":
                self.flush()
            elif tok.tag == "/p":
                self.flush()
                self.cursor_y += VSTEP  # Extra space between paragraphs

    def word(self, word):
        font = get_font(self.size, self.weight, self.style)
        
        # Measure the width of this word
        w = font.measure(word)
        
        # Check if word fits on current line
        if self.cursor_x + w > WIDTH - HSTEP:
            # Word doesn't fit, wrap to next line
            self.flush()
        
        # Add word to line list at current position (with font!) but without y axis as it will be calculated later
        # This is due to the possibility of multiple fonts in a single line
        self.line.append((self.cursor_x, word, font))
        
        # Move cursor to end of word plus space
        self.cursor_x += w + font.measure(" ")

class Browser:
    def __init__(self):
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
        global WIDTH, HEIGHT
        WIDTH, HEIGHT = event.width, event.height
        self.display_list = Layout(self.tokens).display_list  # Use Layout class
        self.update_scroll_region()
        self.draw()

    def load(self, url):
        if url.scheme == "file":
            with open(url.path, 'r', encoding='utf8') as f:
                body = f.read()
                tokens = lex(body)  # Now returns tokens, not text
        elif url.entity == "data":
            _, content = url.parse_data_url(url.content)
            tokens = lex(content)  # Now returns tokens, not text
        elif url.entity == "view-source":
            body = url.request()
            tokens = [Text(body)]  # Wrap in Text object for consistency
        else:
            body = url.request()
            tokens = lex(body)  # Now returns tokens, not text

        self.tokens = tokens  # Store tokens instead of text
        self.display_list = Layout(tokens).display_list  # Use Layout class

        # Calculate content height and set scroll region
        if self.display_list:
            self.content_height = max(y for x, y, word, font in self.display_list) + VSTEP
        else:
            self.content_height = 0

        self.update_scroll_region()
        self.draw()

    def update_scroll_region(self):
        """Set the scrollable region of the canvas"""
        self.canvas.configure(scrollregion=(0, 0, WIDTH, self.content_height))

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