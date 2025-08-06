# ==============================================================================
# CSS PARSER AND STYLING ENGINE
# ==============================================================================
# This file handles CSS parsing and applies styles to HTML elements.
#
# Key Components:
# 1. CSSParser - Converts CSS text into selector/property rules
# 2. Selector Classes - Match CSS selectors to HTML elements
# 3. Style Application - Applies CSS rules to HTML tree with inheritance
#
# The CSS processing pipeline:
# CSS Text → Parse Rules → Match Selectors → Apply Styles → Inherit Properties
# ==============================================================================

from requests import Element

# ==============================================================================
# CSS CONSTANTS
# ==============================================================================

# Properties that children inherit from their parents
# If a parent has color: red, all children will also have color: red unless overridden
INHERITED_PROPERTIES = {
    "font-size": "16px",      # Default font size
    "font-style": "normal",   # normal or italic
    "font-weight": "normal",  # normal or bold
    "color": "black",         # Text color
}

# ==============================================================================
# CSS PARSER CLASS
# ==============================================================================

class CSSParser:
    """
    Parses CSS text into a list of (selector, properties) rules.
    
    The parser handles:
    - Tag selectors: h1 { color: red; }
    - Descendant selectors: div p { color: blue; }
    - Property-value pairs with proper syntax
    - Error recovery for malformed CSS
    """
    
    def __init__(self, s):
        """
        Initialize the CSS parser.
        
        :param s: CSS text to parse
        """
        self.s = s # text to parse
        self.i = 0 # current character index

    def selector(self):
        """
        Parse a CSS selector (tag names with descendant relationships).
        
        Examples:
        - "h1" → TagSelector('h1')
        - "div p" → DescendantSelector(TagSelector('div'), TagSelector('p'))
        
        :return: Selector object that can match HTML elements
        """
        # Start with the first tag, casefold() for case-insensitive matching
        out = TagSelector(self.word().casefold())
        self.whitespace()
        
        # Continue reading until open brackets of CSS formatting rule reached
        while self.i < len(self.s) and self.s[self.i] != "{": 
            tag = self.word()
            descendant = TagSelector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        """
        Parse the entire CSS text into a list of rules.
        
        Each rule is a tuple of (selector, properties_dict).
        Handles error recovery for malformed CSS.
        
        :return: List of (selector, properties) tuples
        """
        rules = [] # Parse through the CSS
        while self.i < len(self.s):
            try:
                # Parse one complete CSS rule
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except Exception:
                # Error recovery: skip to next rule
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules

    def whitespace(self):
        """
        Skip over any whitespace characters (spaces, tabs, newlines).
        """
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        """
        Parse a CSS word (identifier, value, or number).
        
        Words can contain letters, numbers, and special characters: #-.%
        
        :return: The parsed word
        :raises Exception: If no valid word is found
        """
        start = self.i # Copy of the start position
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start): # Found no elements to parse
            raise Exception("Parsing Error")
        return self.s[start:self.i]
    
    def literal(self, literal):
        """
        Expect and consume a specific literal character.
        
        :param literal: Character we expect to see (like '{', '}', ':', ';')
        :raises Exception: If the expected character is not found
        """
        # Checks we aren't past the end of the string and that the current character is what we expected
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1

    def pair(self):
        """
        Parse a single CSS property-value pair.
        
        Examples:
        - "color : blue" → ('color', 'blue')
        - "color:blue" → ('color', 'blue')
        
        :return: Tuple of (property_name, value) with lowercase property name
        """
        prop = self.word() # Example - "color : blue" or "color:blue"
        self.whitespace() # whitespace will only add to the index value if a space is detected
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.casefold(), val

    def body(self):
        """
        Parse CSS property declarations within braces.
        
        Parses multiple CSS property-value pairs separated by semicolons.
        Handles error recovery for malformed properties.
        
        :return: Dictionary of property names to values
        """
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair() # Parse multiple CSS property-value pairs separated by semicolons
                pairs[prop] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except Exception:
                # Error recovery: skip to next property or end of rule
                why = self.ignore_until([";","}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def ignore_until(self, chars):
        """
        Skip characters until we find one of the specified characters.
        
        Continue looping until we hit a character we want to see, this is to skip broken or unsupported code.
        Note self.i will now point at the first instance of a character found from "chars".
        Used for error recovery when CSS parsing fails.
        
        :param chars: List of characters to stop at
        :return: The character we stopped at, or None if we hit the end
        """
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None
    
# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def cascade_priority(rule):
    """
    Extract the CSS specificity/priority from a rule.
    
    Used for sorting CSS rules by specificity - more specific rules
    are applied after less specific ones, allowing them to override.
    
    :param rule: (selector, properties) tuple
    :return: Priority value for sorting
    """
    selector, _ = rule
    return selector.priority

# ==============================================================================
# CSS SELECTOR CLASSES
# ==============================================================================

class TagSelector:
    """
    Matches HTML elements by tag name.
    
    Example: h1 { color: red; }
    This selector matches all <h1> elements.
    """
    
    def __init__(self, tag):
        """
        Initialize a tag selector.
        
        :param tag: HTML tag name to match (e.g., 'h1', 'p', 'div')
        """
        self.tag = tag
        self.priority = 1  # CSS specificity (higher = more specific)

    def matches(self, node):
        """
        Check if this selector matches the given HTML element.
        
        :param node: HTML Element to test
        :return: True if the selector matches
        """
        return isinstance(node, Element) and self.tag == node.tag

class DescendantSelector:
    """
    Matches elements that are descendants of other elements.
    
    Example: div p { color: blue; }
    This matches all <p> elements that are inside <div> elements at any depth.
    Note this matches an instance of a ancestor to a descendent at any depth,
    for directly below we would have to support the ">" symbol for direct child.
    """
    
    def __init__(self, ancestor, descendant):
        """
        Initialize a descendant selector.
        
        :param ancestor: Selector for the ancestor element
        :param descendant: Selector for the descendant element (typically TagSelector)
        """
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    # Note this matches an instance of a ancestor to a descendent at an depth,
    # for directly below we would have to support the ">" symbol for direct child
    def matches(self, node):
        """
        Check if this descendant selector matches the given element.
        
        Algorithm:
        1. Check if the node matches the descendant part
        2. Walk up the parent chain looking for the ancestor
        3. Return True if we find a matching ancestor
        
        :param node: HTML Element to test
        :return: True if the selector matches
        """
        # Calling TagSelector matches() not its own one
        if not self.descendant.matches(node): return False 
        
        # Walk up the parent chain looking for the ancestor
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

# ==============================================================================
# STYLE APPLICATION ENGINE
# ==============================================================================

def style(node, rules):
    """
    Apply CSS styles to an HTML element and all its children.
    
    This function implements the CSS cascade:
    1. Set up inheritance (children get parent styles)
    2. Apply matching CSS rules (more specific rules override less specific)
    3. Resolve relative values (like percentages)
    4. Recursively style all children
    
    :param node: HTML Element to style
    :param rules: List of (selector, properties) CSS rules
    """
    node.style = {} # Add style attribute here so only exists if needed

    # Apply inherited styles - children inherit certain properties from parents
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            # Inherit from parent
            node.style[property] = node.parent.style[property]
        else:
            # Use default value (this is the root element)
            node.style[property] = default_value

    # Apply matching CSS rules (rules override inheritance)
    for selector, body in rules:
        if selector.matches(node):
            for prop, val in body.items():
                node.style[prop] = val  # Override inherited/previous values

    # Resolve font-size percentages BEFORE visiting children
    # This ensures children inherit the computed value, not the percentage
    if "font-size" in node.style and node.style["font-size"].endswith("%"):
        pct = float(node.style["font-size"][:-1]) / 100
        if node.parent:
            parent_size = float(node.parent.style["font-size"][:-2])  # "16px" -> 16
        else:
            parent_size = float(INHERITED_PROPERTIES["font-size"][:-2])
        node.style["font-size"] = f"{pct * parent_size}px"

    # Recurse into children - apply styling to all child elements
    for child in node.children:
        style(child, rules)