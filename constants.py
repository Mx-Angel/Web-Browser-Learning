# Font cache - stores tkinter Font objects to avoid recreating them with each re-draw
FONTS = {}

# Browser window dimensions
WIDTH, HEIGHT = 1280, 720
CANVAS_WIDTH, CANVAS_HEIGHT = 0, 0

# Horizontal and vertical spacing constraints
HSTEP, VSTEP = 13, 18

# HTML elements that create block-level layout (as opposed to inline)
BLOCK_ELEMENTS = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
]

# How many pixels to scroll with each scroll step
SCROLL_STEP = 20

# Default page to load when no URL is specified
DEFAULT_PAGE = "file://index.html"

# Default user agent string for HTTP requests
SOCKET = None

# HTML entities and their replacements
ENTITIES = {
    "&lt;": "<",
    "&gt;": ">",
    "&amp;": "&",
    "&quot;": '"',
    "&apos;": "'",
    "&nbsp;": " ",
    "&copy;": "©",
    "&ndash;": "-"
}

SELF_CLOSING_TAGS = [
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
]