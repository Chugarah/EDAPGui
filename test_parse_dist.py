
from re import search

def parse_distance(text: str) -> float | None:
    """ Parses a distance string like '7.5km', '1.2Mm', '800m'. 
        Returns distance in kilometers.
    """
    # Regex to find number followed by unit
    # Examples: "Coriolis [8.2km]", "Station 1.2Mm"
    # Match number (float) and unit
    match = search(r"([\d\.]+)\s*(Mm|km|m|ls)", text)
    if match:
        val_str = match.group(1)
        unit = match.group(2)
        
        # Clean up common OCR errors
        if ".." in val_str:
            val_str = val_str.replace("..", ".")
        
        try:
            value = float(val_str)
            
            if unit == 'Mm':
                return value * 1000.0
            elif unit == 'km':
                return value
            elif unit == 'm':
                return value / 1000.0
            elif unit == 'ls':
                return value * 299792.0 # roughly, though docking via LS is unlikely
        except ValueError:
            print(f"Failed to parse float: {val_str}")
            return None
    
    return None

# Test cases
print(f"7.5km -> {parse_distance('7.5km')}")
print(f"4..5km -> {parse_distance('4..5km')}")




