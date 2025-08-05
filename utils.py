class Rect:
    """Represents a rectangle with left, top, right, bottom coordinates."""
    
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def contains_point(self, x, y):
        """Check if a point (x, y) is inside this rectangle."""
        return x >= self.left and x < self.right and y >= self.top and y < self.bottom