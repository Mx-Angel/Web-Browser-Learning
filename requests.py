# ==============================================================================
# HTTP CLIENT AND HTML PARSER
# ==============================================================================
# This file handles two main responsibilities:
# 1. HTTP networking - fetching web pages from servers
# 2. HTML parsing - converting raw HTML text into a structured tree
#
# Key Classes:
# - URL: Handles different URL schemes (http, https, file, data, view-source)
# - HTMLParser: Converts HTML text into Element/Text node tree
# - Element: Represents HTML tags with attributes and children
# - Text: Represents plain text content within HTML
# ==============================================================================

import socket
import sys
import ssl

from constants import SOCKET, ENTITIES, SELF_CLOSING_TAGS

# ==============================================================================
# HTML NODE CLASSES
# ==============================================================================
# These classes represent the parsed HTML document structure

class Text:
    """
    Represents a text node in the HTML document tree.
    
    Text nodes contain actual content that will be displayed to the user,
    like the text inside a paragraph or heading.
    """
    
    def __init__(self, text: str, parent):
        """
        Initialize a text node.
        
        :param text: The actual text content
        :param parent: Parent Element that contains this text
        """
        self.text = text        # The actual text content
        self.children = []      # Text nodes have no children (always empty)
        self.parent = parent    # Parent element in the HTML tree
    
    def __repr__(self):
        """String representation for debugging."""
        return repr(self.text)

class Element:
    """
    Represents an HTML element (tag) in the document tree.
    
    Elements have a tag name (like 'div', 'p', 'a'), attributes (like 'href', 'class'),
    and can contain child elements or text nodes.
    """
    
    def __init__(self, tag: str, attributes: dict, parent):
        """
        Initialize an HTML element.
        
        :param tag: HTML tag name (e.g., 'div', 'p', 'a')
        :param attributes: Dictionary of HTML attributes (e.g., {'href': 'http://example.com'})
        :param parent: Parent Element that contains this element
        """
        self.tag = tag              # HTML tag name (e.g., 'div', 'p', 'a')
        self.attributes = attributes # Dictionary of attributes like {'class': 'header'}
        self.children = []          # List of child Element or Text nodes
        self.parent = parent        # Parent element in the HTML tree

    def __repr__(self):
        """String representation for debugging."""
        return "<" + self.tag + ">"

# ==============================================================================
# HTML PARSER CLASS
# ==============================================================================

class HTMLParser:
    """
    Converts raw HTML text into a structured tree of Element and Text nodes.
    
    The parser handles:
    - HTML tags with attributes
    - Self-closing tags (like <br>, <img>)
    - Nested elements
    - HTML entities (like &amp;, &lt;)
    - Implicit tag insertion (automatic <html>, <head>, <body>)
    - Whitespace normalization
    """
    
    def __init__(self, body: str):
        """
        Initialize the HTML parser.
        
        :param body: Raw HTML text to parse
        """
        self.body = body            # Raw HTML text to parse
        self.unfinished = []        # Stack of currently open tags (not yet closed)
        
        # Tags that belong in the document <head> section
        self.HEAD_TAGS = [
            "base", "basefont", "bgsound", "noscript",
            "link", "meta", "title", "style", "script",
        ]

    def parse(self) -> Element:
        """
        Parse the HTML text and return the root element.
        
        This is the main parsing method that:
        1. Scans through each character in the HTML
        2. Identifies tags vs text content
        3. Handles HTML entities
        4. Normalizes whitespace
        5. Builds the element tree structure
        
        :return: Root HTML element containing the entire parsed tree
        """
        buffer = ""         # Accumulates characters as we build tags/text
        in_tag = False     # Whether we're currently inside angle brackets < >
        i = 0              # Current position in the HTML text

        # Main parsing loop - process each character
        while i < len(self.body):
            char = self.body[i]
            
            if char == "<":
                # Start of an HTML tag
                # If we have accumulated text, add it as a Text node
                if buffer:
                    self.add_text(buffer)
                    buffer = ""
                
                in_tag = True
                i += 1
                
            elif char == ">" and in_tag:
                # End of an HTML tag
                tag_content = buffer.strip()
                self.add_tag(tag_content)
                
                # Extract clean tag name for block element checking
                # Remove any attributes and clean up the tag name
                clean_tag = tag_content.split()[0] if tag_content else ""
                if clean_tag.startswith('/'):
                    clean_tag = clean_tag[1:]  # Remove closing slash
                clean_tag = clean_tag.lower()
                
                # Handle block elements - add newline after certain tags
                if clean_tag == "br":
                    self.add_text("\n")
                elif tag_content.startswith('/'):
                    # Closing block tags often create line breaks for readability
                    self.add_text("\n")
                
                buffer = ""
                in_tag = False
                i += 1
                
            elif not in_tag and char == "&":
                # Handle HTML entities like &amp;, &lt;, &gt;
                matched = False
                
                # Try different entity lengths (most are 4-7 characters)
                for length in range(4, 8):
                    if i + length <= len(self.body):
                        entity = self.body[i:i+length]
                        if entity in ENTITIES:
                            buffer += ENTITIES[entity]
                            i += length
                            matched = True
                            break
                            
                if not matched:
                    # Not a valid entity, treat as literal '&'
                    buffer += "&"
                    i += 1
                    
            elif not in_tag:
                # Regular text content (not inside a tag)
                # Normalize whitespace - collapse multiple spaces/newlines into single space
                if char.isspace():
                    if buffer and not buffer.endswith(" "):
                        buffer += " "
                else:
                    buffer += char
                i += 1
            else:
                # We're inside a tag, accumulate the tag content
                buffer += char
                i += 1
        
        # Add any remaining text at the end
        if not in_tag and buffer:
            self.add_text(buffer)

        return self.finish()
    
    def get_attributes(self, text: str) -> tuple[str, dict]:
        """
        Parse HTML tag text to extract tag name and attributes.
        
        Examples:
        - "div class='header' id='main'" → ('div', {'class': 'header', 'id': 'main'})
        - "br" → ('br', {})
        - "a href=http://example.com" → ('a', {'href': 'http://example.com'})
        
        :param text: Raw tag content (everything between < and >)
        :return: Tuple of (tag_name, attributes_dict)
        """
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        
        # Process each attribute in the tag
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                
                # Remove quotes around attribute values
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""
                
        return tag, attributes
    
    def add_text(self, text: str):
        """
        Add a text node to the current parent element.
        
        :param text: Text content to add
        """
        # Skip whitespace-only text nodes to keep tree clean
        if text.isspace(): 
            return
            
        # Ensure we have proper document structure (html, head, body)
        self.implicit_tags(None) # type: ignore
        
        # Add text to the most recently opened element
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag: str):
        """
        Add an HTML tag element to the document tree.
        
        Handles three types of tags:
        1. Opening tags: <div> - start a new element
        2. Closing tags: </div> - finish an element
        3. Self-closing tags: <br> - complete element with no content
        
        :param tag: Raw tag content (without < >)
        """
        tag, attributes = self.get_attributes(tag)
        
        # Skip HTML comments and declarations
        if tag.startswith("!"): 
            return
            
        # Ensure proper document structure
        self.implicit_tags(tag)
        
        if tag.startswith("/"):
            # We do it like this as there can never be a case where a tag is open, a second one is opened
            # but then the first is closed, the one nested within it must always be closed before the one
            # wrapping it can
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1] if self.unfinished else None
            if parent:
                parent.children.append(node)
                
        elif tag in SELF_CLOSING_TAGS:
            # Self-closing tag: <br>, <img>, <input>, etc.
            # Create element and immediately add to parent (don't push to stack)
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
            
        else:
            # Opening tag: <div>
            # Create element and push to stack (waiting for closing tag)
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def finish(self) -> Element:
        """
        Complete parsing and return the root element.
        
        This method:
        1. Ensures we have a root element
        2. Closes any unclosed tags
        3. Returns the final document tree
        
        :return: Root HTML element
        """
        # Ensure we have at least one element
        if not self.unfinished:
            self.implicit_tags(None) # type: ignore
            
        # Close any remaining open tags
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
            
        return self.unfinished.pop()
    
    def implicit_tags(self, tag: str):
        """
        Automatically insert required HTML structure tags.
        
        HTML documents must have a specific structure:
        <html>
          <head>...</head>
          <body>...</body>
        </html>
        
        This method automatically inserts missing structural tags
        to ensure valid HTML hierarchy.
        
        :param tag: Current tag being processed (or None)
        """
        while True:
            open_tags = [node.tag for node in self.unfinished]
            
            if open_tags == [] and tag != "html":
                # No open tags and we're not starting with <html>
                # → Insert implicit <html>
                self.add_tag("html")
                
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                # We have <html> but need <head> or <body>
                if tag is not None and tag in self.HEAD_TAGS:
                    # Tag belongs in head → Insert <head>
                    self.add_tag("head")
                else:
                    # Tag belongs in body → Insert <body>
                    self.add_tag("body")
                    
            elif open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS:
                # We're in <head> but encountering body content
                # → Close <head> and continue (body will be added next iteration)
                self.add_tag("/head")
                
            else:
                # Structure is correct, stop adjusting
                break

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def show_source(body: str):
    """
    Display raw HTML source code.
    
    :param body: HTML source code to display
    """
    print(body)

def print_tree(node, indent: int = 0):
    """
    Print a visual representation of the HTML tree structure.
    
    :param node: Root node to start printing from
    :param indent: Current indentation level (for recursive calls)
    """
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)

# ==============================================================================
# URL CLASS
# ==============================================================================

class URL:
    """
    Represents and handles different types of URLs.
    
    Supports multiple URL schemes:
    - http://example.com/page.html - Standard web pages
    - https://secure.com/login - Secure web pages  
    - file:///path/to/local.html - Local files
    - data:text/html,<h1>Hello</h1> - Inline data
    - view-source:http://example.com - View page source
    """
    
    def __init__(self, url: str):
        """
        Parse a URL string into its components.
        
        :param url: URL string to parse
        """
        # Initialize all URL components
        self.scheme = None    # http, https, file, data, view-source
        self.host = None      # www.example.com
        self.port = None      # 80, 443, 8080, etc.
        self.path = None      # /page.html
        self.entity = None    # Special marker for data: and view-source:
        self.content = None   # Content for data: URLs

        # Parse special URL schemes first
        if "data" in url:
            self.entity, immediate_url = url.split(":", 1)
        elif "view-source" in url:
            self.entity, url = url.split(":", 1)
            self.scheme, url = url.split("://", 1)
        else:
            # Standard URL: scheme://rest
            self.scheme, url = url.split("://", 1)
            
            # Validate supported schemes
            try:
                assert self.scheme in ["http", "https", "file", "data", "view-source"], f"Unsupported URL scheme: {self.scheme}"
            except AssertionError as e:
                print(f"Error during assert: {e}")
                sys.exit(1) # Fix so directs to about:blank

        # Set default ports based on scheme
        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443
        elif self.scheme == "file":
            self.path = url
            return
        elif self.entity == "data":
            self.content = immediate_url
            return
        
        if self.entity == "view-source":
            self.path = url
        
        # Parse host and path from remaining URL
        if "/" not in url:
            url = url + "/"
        self.host, url = url.split("/", 1)
        
        # Handle custom ports in host:port format
        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)
        self.path = "/" + url if url else "/"

    def __str__(self) -> str:
        """
        Convert URL back to string representation.
        
        :return: Full URL string
        """
        port_part = ":" + str(self.port) if self.port is not None else ""
        scheme = self.scheme if self.scheme is not None else ""
        host = self.host if self.host is not None else ""
        path = self.path if self.path is not None else ""
        
        # Don't show default ports
        if scheme == "https" and self.port == 443:
            port_part = ""
        if scheme == "http" and self.port == 80:
            port_part = ""
            
        return scheme + "://" + host + port_part + path

    def parse_data_url(self, data_url: str) -> tuple[str, str]:
        """
        Parse a data URL and extract the content.
        
        Data URLs format: data:[mediatype],content
        Example: data:text/html,<h1>Hello</h1>
        
        :param data_url: Data URL content part
        :return: Tuple of (media_type, content)
        """
        if data_url == "":
            return "text/plain", "No content provided"

        if "," not in data_url:
            # If no comma, assume it's a plain text URL
            return "text/plain", data_url
        
        # Split at first comma to separate media type from content
        _, content = data_url.split(",", 1)
        return "text/plain", content
    
    def blank_page(self) -> str:
        """
        Return a blank HTML page for error cases.
        
        :return: Basic HTML document
        """
        return "<html><head><title>Unable to load page</title></head><body></body></html>"

    def request(self) -> str:
        """
        Fetch the content from this URL.
        
        This method:
        1. Opens a socket connection to the server
        2. Sends an HTTP request
        3. Receives and parses the HTTP response
        4. Handles redirects
        5. Returns the content
        
        :return: Content of the web page (HTML, CSS, etc.)
        """
        try:
            # Create and configure socket connection
            global SOCKET
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            s.settimeout(30)
            s.connect((self.host, self.port))
            if self.scheme == "https":
                ctx = ssl.create_default_context()
                SOCKET = ctx.wrap_socket(s, server_hostname=self.host)
            else:
                SOCKET = s
                
        except socket.error as e:
            print(f"Socket error: {e}")
            return self.blank_page()
        
        # Build HTTP request
        request = f"GET {self.path} HTTP/1.1\r\n"
        request += f"Host: {self.host}\r\n"
        request += "User-Agent: Python Browser\r\n"
        request += "Connection: close\r\n\r\n" # Remember to end the headers with a blank line so 2 \r\n is sent
        SOCKET.send(request.encode("utf8"))

        # use "rb" for keep-alive compatibility and .decode manually for reading and remove encoding parameter
        # We decode manually as the content-length can't be tracked when the internal makefile command is converting bytes to text
        # resulting in a hang as it waits for more data that never comes.
        response = SOCKET.makefile("r", encoding="utf8", newline='\r\n')
        
        # Parse status line: "HTTP/1.1 200 OK"
        status_line = response.readline()
        version, status, reason = status_line.split(" ", 2)

        # Parse response headers
        response_headers = {}
        while True:
            line = response.readline() # .decode("utf8")
            if line == "\r\n": break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        # Handle HTTP redirects
        if status == "301" or status == "302":
            new_url = self.url_redirect(response_headers)
            if new_url:
                print(f"Redirecting to {new_url}")
                return URL(new_url).request()
            else:
                raise Exception(f"Redirection not supported for {self.scheme} scheme")
        
        # Check for unsupported encodings
        try:
            assert "transfer-encoding" not in response_headers, "Chunked transfer encoding is not supported"
            assert "content-encoding" not in response_headers, "Content encoding is not supported"
        except AssertionError as e:
            print(f"Error during assert: {e}")
            return self.blank_page()

        # Read response body
        if "content-length" in response_headers.keys():
            content_length = int(response_headers["content-length"])
            chunk = response.read(content_length)
            
            # Handle both bytes and string responses
            if isinstance(chunk, bytes):
                # Binary mode - we got bytes
                content = chunk.decode("utf8")
            else:
                # Text mode - we got a string
                content = chunk
        else:
            # If no content-length, read until end of file
            content = response.read()

        SOCKET.close()
        return content
    
    def resolve(self, url: str) -> 'URL':
        """
        Resolve a relative URL against this URL's base.
        
        Examples:
        - base: http://example.com/page.html, relative: "other.html" 
          → http://example.com/other.html
        - base: http://example.com/dir/, relative: "../other.html"
          → http://example.com/other.html
        
        :param url: URL to resolve (can be relative or absolute)
        :return: New URL object with resolved address
        """
        if "://" in url:
            # Already a fully qualified URL
            return URL(url)

        if url.startswith("//") and self.scheme is not None:
            # Protocol-relative URL: //example.com/path
            return URL(self.scheme + ":" + url)

        if not url.startswith("/") and self.path is not None:
            # Relative path: resolve against current directory
            dir, _ = self.path.rsplit("/", 1)
            
            # Handle ../ navigation
            while url.startswith("../"):
                _, url = url.split("/", 1)
                if "/" in dir:
                    dir, _ = dir.rsplit("/", 1)
                    
            url = dir + "/" + url

        return URL(f"{self.scheme}://{self.host}:{self.port}{url}")
    
    def url_redirect(self, response_headers: dict):
        """
        Handle HTTP redirect responses.
        
        :param response_headers: HTTP response headers containing Location
        :return: New URL to redirect to, or None if no redirect
        """
        if response_headers is None:
            response_headers = {}

        if "location" in response_headers:
            new_url = response_headers["location"]
            
            # Handle relative redirect URLs
            if not new_url.startswith("http://") and not new_url.startswith("https://"):
                new_url = f"{self.scheme}://{self.host}:{self.port}{new_url}"
                
            return new_url
        return None