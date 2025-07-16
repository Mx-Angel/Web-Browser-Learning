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

class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

def lex(body) -> list:
    out = []
    buffer = ""
    in_tag = False
    i = 0

    # Block elements that should create line breaks
    block_start_tags = ["div", "h1", "h2", "h3", "h4", "h5", "h6", "li"]

    while i < len(body):
        char = body[i]
        
        if char == "<":
            # If we have text in buffer, add it as Text object
            if buffer:
                out.append(Text(buffer))
                buffer = ""
            
            in_tag = True
            i += 1
            
        elif char == ">" and in_tag:
            # End of tag - add Tag object
            tag_content = buffer.strip()
            out.append(Tag(tag_content))
            
            # Extract clean tag name for block element checking
            # Remove any attributes and clean up the tag name
            clean_tag = tag_content.split()[0] if tag_content else ""
            if clean_tag.startswith('/'):
                clean_tag = clean_tag[1:]  # Remove closing slash
            clean_tag = clean_tag.lower()
            
            # Handle block elements - add newline after certain tags
            if clean_tag == "br":
                out.append(Text("\n"))
            elif clean_tag in block_start_tags and tag_content.startswith('/'):
                # Only add newlines for CLOSING block tags
                out.append(Text("\n"))
            
            buffer = ""
            in_tag = False
            i += 1
            
        elif not in_tag and char == "&":
            # Handle entities
            matched = False
            for length in range(4, 8):
                if i + length <= len(body):
                    entity = body[i:i+length]
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
        out.append(Text(buffer))

    return out

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