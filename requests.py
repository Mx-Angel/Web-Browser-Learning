import socket
import sys
import ssl

# Constants
DEFAULT_PAGE = "file://index.html"
SOCKET = None
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

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent
    
    def __repr__(self):
        return repr(self.text)

class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        return "<" + self.tag + ">"

class HTMLParser:
    def __init__(self, body):
        self.body = body
        self.unfinished = []
        self.HEAD_TAGS = [
            "base", "basefont", "bgsound", "noscript",
            "link", "meta", "title", "style", "script",
        ]

    def parse(self) -> list:
        buffer = ""
        in_tag = False
        i = 0

        while i < len(self.body):
            char = self.body[i]
            
            if char == "<":
                # If we have text in buffer, add it as Text object
                if buffer:
                    self.add_text(buffer)
                    buffer = ""
                
                in_tag = True
                i += 1
                
            elif char == ">" and in_tag:
                # End of tag - add Tag object
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
                    # Only add newlines for CLOSING block tags
                    self.add_text("\n")
                
                buffer = ""
                in_tag = False
                i += 1
                
            elif not in_tag and char == "&":
                # Handle entities
                matched = False
                for length in range(4, 8):
                    if i + length <= len(self.body):
                        entity = self.body[i:i+length]
                        if entity in ENTITIES:
                            buffer += ENTITIES[entity]
                            i += length
                            matched = True
                            break
                if not matched:
                    buffer += "&"
                    i += 1
                    
            elif not in_tag:
                # Handle regular text - collapse whitespace
                if char.isspace():
                    if buffer and not buffer.endswith(" "):
                        buffer += " "
                else:
                    buffer += char
                i += 1
            else:
                # We're in a tag, accumulate tag content
                buffer += char
                i += 1
        
        # Add any remaining text
        if not in_tag and buffer:
            self.add_text(buffer)

        return self.finish()
    
    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""
        return tag, attributes
    
    def add_text(self, text):
        """Add a text node to the parser."""
        if text.isspace(): return # Ignore whitespace-only text (for now)
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        """Add a tag node to the parser."""
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"): return
        self.implicit_tags(tag) # Check that the tag is added to the correct area, e.g. head, body
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
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def finish(self):
        """Finish parsing and return the root node."""
        if not self.unfinished:
            self.implicit_tags(None)
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()
    
    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag is not None and tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and tag not in ["/head"] + self.HEAD_TAGS:
                self.add_tag("/head")
            else:
                break

def show_source(body):
    print(body)

class URL:
    def __init__(self, url: str):
        self.scheme = None
        self.host = None
        self.port = None
        self.path = None
        self.entity = None
        self.content = None

        if "data" in url:
            self.entity, immediate_url = url.split(":", 1)
        elif "view-source" in url:
            self.entity, url = url.split(":", 1)
            self.scheme, url = url.split("://", 1)
        else:
            self.scheme, url = url.split("://", 1)
            try:
                assert self.scheme in ["http", "https", "file", "data", "view-source"], f"Unsupported URL scheme: {self.scheme}"
            except AssertionError as e:
                print(f"Error during assert: {e}")
                sys.exit(1) # Fix so directs to about:blank

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
        
        if "/" not in url:
            url = url + "/"
        self.host, url = url.split("/", 1)
        if ":" in self.host:
            self.host, port = self.host.split(":", 1)
            self.port = int(port)
        self.path = "/" + url if url else "/"

    def __str__(self):
        port_part = ":" + str(self.port)
        if self.scheme == "https" and self.port == 443:
            port_part = ""
        if self.scheme == "http" and self.port == 80:
            port_part = ""
        return self.scheme + "://" + self.host + port_part + self.path

    def parse_data_url(self, data_url: str):
        """Parse a data URL and return the content."""
        if data_url == "":
            return "text/plain", "No content provided"

        if "," not in data_url:
            # If no comma, assume it's a plain text URL
            return "text/plain", data_url
        
        _, content = data_url.split(",", 1)
        return "text/plain", content
    
    def blank_page(self):
        """Return a blank HTML page for unsupported URLs."""
        return "<html><head><title>Unable to load page</title></head><body></body></html>"

    def request(self):
        try:
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
                
        request = f"GET {self.path} HTTP/1.1\r\n"
        request += f"Host: {self.host}\r\n"
        request += "User-Agent: Python Browser\r\n"
        request += "Connection: close\r\n\r\n" # Remember to end the headers with a blank line so 2 \r\n is sent
        SOCKET.send(request.encode("utf8"))

        # use "rb" for keep-alive compatibility and .decode manually for reading and remove encoding parameter
        # We decode manually as the content-length can't be tracked when the internal makefile command is converting bytes to text
        # resulting in a hang as it waits for more data that never comes.
        response = SOCKET.makefile("r", encoding="utf8", newline='\r\n')
        status_line = response.readline() # .decode("utf8")
        version, status, reason = status_line.split(" ", 2)

        response_headers = {}
        while True:
            line = response.readline() # .decode("utf8")
            if line == "\r\n": break
            header, value = line.split(":", 1)
            response_headers[header.casefold()] = value.strip()

        if status == "301" or status == "302":
            # Handle redirection
            new_url = self.url_redirect(response_headers)
            if new_url:
                print(f"Redirecting to {new_url}")
                return URL(new_url).request()
            else:
                raise Exception(f"Redirection not supported for {self.scheme} scheme")
        try:
            assert "transfer-encoding" not in response_headers, "Chunked transfer encoding is not supported"
            assert "content-encoding" not in response_headers, "Content encoding is not supported"
        except AssertionError as e:
            print(f"Error during assert: {e}")
            return self.blank_page()

        if "content-length" in response_headers.keys():
            content_length = int(response_headers["content-length"])
    
            # Read the content
            chunk = response.read(content_length)
            
            # Check if it's bytes or string and handle accordingly
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
    
    def resolve(self, url):
            if "://" in url:
                return URL(url)  # Fully qualified URL

            if url.startswith("//"):
                return URL(self.scheme + ":" + url)  # Protocol-relative

            if not url.startswith("/"):
                # Handle relative path resolution and '..'
                dir, _ = self.path.rsplit("/", 1)
                while url.startswith("../"):
                    _, url = url.split("/", 1)
                    if "/" in dir:
                        dir, _ = dir.rsplit("/", 1)
                url = dir + "/" + url

            return URL(f"{self.scheme}://{self.host}:{self.port}{url}")

    
    def url_redirect(self, response_headers=None):
        """Handle URL redirection."""
        if response_headers is None:
            response_headers = {}

        if "location" in response_headers:
            new_url = response_headers["location"]
            if not new_url.startswith("http://") and not new_url.startswith("https://"):
                # If the URL is relative, construct the full URL
                new_url = f"{self.scheme}://{self.host}:{self.port}{new_url}"
            return new_url
        return None
    
def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children:
        print_tree(child, indent + 2)
