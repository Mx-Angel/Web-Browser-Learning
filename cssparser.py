from requests import Element


# Constants
INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}

class CSSParser:
    def __init__(self, s):
        self.s = s # text
        self.i = 0 # index

    def selector(self):
        out = TagSelector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{": # Continue reading until open brackets of CSS formatting
            tag = self.word()
            descendant = TagSelector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out
    
    def parse(self):
        rules = [] # Parse through the CSS
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i # Copy of the start
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start): # Found no elements to parse
            raise Exception("Parsing Error")
        return self.s[start:self.i]
    
    def literal(self, literal):
        # Checks we aren't past the end of the string and that the current character is what we expected
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1

    def pair(self):
        prop = self.word() # Example - "color : blue" or "color:blue"
        self.whitespace() # whitespace will only add to the index value if a space is detected
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val
    
    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair() # Parse multiple CSS property-value pairs separated by semicolons
                pairs[prop] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                why = self.ignore_until([";","}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs
    
    # Continue looping until we hit a character we want to see, this is to skip broken or unsupported code
    # Note self.i will now point at the first instance of a character found from "chars"
    # Not sure what it does with that but guessing something happens later -> check body and how it skips broken CSS definitions
    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None
    
def cascade_priority(rule):
    selector, _ = rule
    return selector.priority

class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag

class DescendantSelector:
    def __init__(self, ancestor: TagSelector, descendant: TagSelector):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    # Note this matches an instance of a ancestor to a descendent at an depth,
    # for directly below we would have to support the ">" symbol for direct child
    def matches(self, node):
        if not self.descendant.matches(node): return False # Calling TagSelector matches() not its own one
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False


def style(node, rules):
    node.style = {} # Add style attribute here so only exists if needed

    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value
    
    # For each matching selector, apply its style declarations to the node
    for selector, body in rules:
        if not selector.matches(node): continue
        for property, value in body.items():
            node.style[property] = value

    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items(): # For dictionaries .items() needs to be used
            node.style[property] = value

    for child in node.children:
        style(child, rules)

    if node.style["font-size"].endswith("%"):
        if node.parent:
            parent_font_size = node.parent.style["font-size"]
        else:
            parent_font_size = INHERITED_PROPERTIES["font-size"]
        node_pct = float(node.style["font-size"][:-1]) / 100
        parent_px = float(parent_font_size[:-2])
        node.style["font-size"] = str(node_pct * parent_px) + "px"