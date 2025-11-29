"""
Distance Calculator - Calculate distances between GPS coordinates

Copyright (c) 2025 Douglas Carroll

This work is licensed under the Creative Commons Attribution-ShareAlike 4.0
International License. To view a copy of this license, visit
http://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative Commons,
PO Box 1866, Mountain View, CA 94042, USA.

You are free to:
- Share: copy and redistribute the material in any medium or format
- Adapt: remix, transform, and build upon the material for any purpose, even commercially

Under the following terms:
- Attribution: You must give appropriate credit, provide a link to the license, and indicate
  if changes were made.
- ShareAlike: If you remix, transform, or build upon the material, you must distribute your
  contributions under the same license as the original.

No additional restrictions: You may not apply legal terms or technological measures that
legally restrict others from doing anything the license permits.
"""

import math

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance between two points on Earth given their latitude and longitude.
    Returns the distance in nautical miles.
    
    Args:
        lat1 (float): Latitude of first point in degrees
        lon1 (float): Longitude of first point in degrees
        lat2 (float): Latitude of second point in degrees
        lon2 (float): Longitude of second point in degrees
    
    Returns:
        float: Distance in nautical miles
    """
    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Earth's radius in kilometers
    earth_radius_km = 6371.0
    
    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance_km = earth_radius_km * c
    
    # Convert kilometers to nautical miles (1 nautical mile = 1.852 kilometers)
    distance_nm = distance_km / 1.852
    
    return distance_nm

