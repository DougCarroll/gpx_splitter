"""
GPX Track Splitter - Core GPX splitting functionality

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

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging
from distance_calculator import calculate_distance

logger = logging.getLogger(__name__)

def generate_track_name(start_lat, start_lon, end_lat, end_lon):
    """
    Generate a track name based on start and end coordinates.
    
    Args:
        start_lat (float): Start latitude
        start_lon (float): Start longitude
        end_lat (float): End latitude
        end_lon (float): End longitude
        
    Returns:
        str: Generated track name
    """
    try:
        # Create a simple coordinate-based name
        start_coords = f"{start_lat:.4f},{start_lon:.4f}"
        end_coords = f"{end_lat:.4f},{end_lon:.4f}"
        
        # If start and end are very close, use a timestamp-based name
        distance = calculate_distance(start_lat, start_lon, end_lat, end_lon)
        if distance < 0.1:  # Less than 0.1 nautical miles
            return f"Track_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        return f"{start_coords} to {end_coords}"
    except Exception as e:
        logger.error(f"Error generating track name: {str(e)}")
        return f"Track_{datetime.now().strftime('%Y%m%d_%H%M')}"

def parse_gpx_file(gpx_content):
    """
    Parse GPX content and extract individual tracks.
    
    Args:
        gpx_content (str): The GPX file content as a string
        
    Returns:
        list: List of dictionaries with track info and points
    """
    try:
        # Parse the GPX XML
        root = ET.fromstring(gpx_content)
        
        # Define the GPX namespace
        namespace = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        
        # Find all track elements
        tracks = []
        
        # Try different approaches to find tracks
        trk_elements = []
        
        # Method 1: Try with namespace
        trk_elements = root.findall('.//gpx:trk', namespace)
        logger.debug(f"Found {len(trk_elements)} tracks with namespace")
        
        # Method 2: If no tracks found, try without namespace
        if not trk_elements:
            trk_elements = root.findall('.//trk')
            logger.debug(f"Found {len(trk_elements)} tracks without namespace")
        
        # Method 3: Try alternative namespace formats
        if not trk_elements:
            for ns in ['http://www.topografix.com/GPX/1/0', 'http://www.topografix.com/GPX/1/1']:
                alt_namespace = {'gpx': ns}
                trk_elements = root.findall('.//gpx:trk', alt_namespace)
                if trk_elements:
                    logger.debug(f"Found {len(trk_elements)} tracks with namespace {ns}")
                    break
        
        # Process each track
        for i, trk in enumerate(trk_elements):
            try:
                # Get track name
                track_name = f"Track_{i+1:03d}"
                name_elem = trk.find('gpx:name', namespace)
                if name_elem is None:
                    name_elem = trk.find('name')
                if name_elem is not None and name_elem.text:
                    track_name = name_elem.text.strip()
                
                # Get track points
                track_points = []
                
                # Find all track points in this track
                trkpts = trk.findall('.//gpx:trkpt', namespace)
                if not trkpts:
                    trkpts = trk.findall('.//trkpt')
                
                for j, trkpt in enumerate(trkpts):
                    try:
                        lat = float(trkpt.get('lat'))
                        lon = float(trkpt.get('lon'))
                        
                        # Get timestamp if available
                        timestamp = None
                        time_elem = trkpt.find('gpx:time', namespace)
                        if time_elem is None:
                            time_elem = trkpt.find('time')
                        
                        if time_elem is not None and time_elem.text:
                            timestamp_str = time_elem.text.strip()
                            try:
                                if timestamp_str.endswith('Z'):
                                    timestamp_str = timestamp_str.replace('Z', '+00:00')
                                timestamp = datetime.fromisoformat(timestamp_str)
                            except ValueError:
                                try:
                                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%SZ')
                                except ValueError:
                                    try:
                                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S')
                                    except ValueError:
                                        # Generate synthetic timestamp
                                        timestamp = datetime.now() + timedelta(minutes=j)
                        else:
                            # Generate synthetic timestamp
                            timestamp = datetime.now() + timedelta(minutes=j)
                        
                        track_points.append({
                            'lat': lat,
                            'lon': lon,
                            'timestamp': timestamp
                        })
                        
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error processing track point: {str(e)}")
                        continue
                
                # Sort points by timestamp
                track_points.sort(key=lambda x: x['timestamp'])
                
                if track_points:
                    # Calculate track statistics
                    start_time = track_points[0]['timestamp']
                    end_time = track_points[-1]['timestamp']
                    duration = end_time - start_time
                    
                    # Calculate total distance
                    total_distance = 0
                    for j in range(1, len(track_points)):
                        total_distance += calculate_distance(
                            track_points[j-1]['lat'], track_points[j-1]['lon'],
                            track_points[j]['lat'], track_points[j]['lon']
                        )
                    
                    tracks.append({
                        'name': track_name,
                        'points': track_points,
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration': duration,
                        'total_distance_nm': total_distance,
                        'point_count': len(track_points)
                    })
                
            except Exception as e:
                logger.warning(f"Error processing track {i}: {str(e)}")
                continue
        
        logger.info(f"Parsed {len(tracks)} tracks from GPX file")
        return tracks
        
    except ET.ParseError as e:
        logger.error(f"Error parsing GPX XML: {str(e)}")
        raise ValueError(f"Invalid GPX file format: {str(e)}")
    except Exception as e:
        logger.error(f"Error parsing GPX file: {str(e)}")
        raise ValueError(f"Error processing GPX file: {str(e)}")

def create_gpx_content(track_points, track_name="Track"):
    """
    Create GPX content for a list of track points.
    
    Args:
        track_points (list): List of track point dictionaries
        track_name (str): Name for the track
        
    Returns:
        str: GPX XML content as a string
    """
    # Create the GPX structure with explicit namespace
    namespace_uri = 'http://www.topografix.com/GPX/1/1'
    gpx = ET.Element(f'{{{namespace_uri}}}gpx')
    gpx.set('version', '1.1')
    gpx.set('creator', 'GPX Track Splitter')
    gpx.set('xmlns', namespace_uri)
    
    # Create track with namespace
    trk = ET.SubElement(gpx, f'{{{namespace_uri}}}trk')
    name = ET.SubElement(trk, f'{{{namespace_uri}}}name')
    name.text = track_name
    
    # Create track segment with namespace
    trkseg = ET.SubElement(trk, f'{{{namespace_uri}}}trkseg')
    
    # Add track points with namespace
    for point in track_points:
        trkpt = ET.SubElement(trkseg, f'{{{namespace_uri}}}trkpt')
        trkpt.set('lat', str(point['lat']))
        trkpt.set('lon', str(point['lon']))
        
        # Add timestamp with namespace
        time_elem = ET.SubElement(trkpt, f'{{{namespace_uri}}}time')
        time_elem.text = point['timestamp'].isoformat()
    
    # Convert to string with proper formatting
    from xml.dom import minidom
    rough_string = ET.tostring(gpx, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    gpx_xml = reparsed.toprettyxml(indent="  ")
    # Remove the XML declaration line that minidom adds (callers can add their own if needed)
    lines = gpx_xml.split('\n')
    # Skip the first line (XML declaration) and rejoin
    gpx_xml = '\n'.join(lines[1:]) if lines[0].startswith('<?xml') else gpx_xml
    return gpx_xml

def split_gpx_file(gpx_content, max_distance_nm=1.0, max_time_hours=1.0, require_timestamps=False):
    """
    Split a GPX file into separate files based on time and distance criteria.
    
    Args:
        gpx_content (str): The GPX file content as a string
        max_distance_nm (float): Maximum distance in nautical miles before splitting
        max_time_hours (float): Maximum time in hours before splitting
        require_timestamps (bool): Whether to require timestamps or generate synthetic ones
        
    Returns:
        list: List of dictionaries with track info and GPX content
    """
    try:
        # Parse the GPX file
        tracks = parse_gpx_file(gpx_content)
        
        if not tracks:
            raise ValueError("No valid tracks found in GPX file")
        
        # Flatten all track points into a single list, sorted by timestamp
        all_points = []
        for track in tracks:
            for point in track['points']:
                all_points.append(point)
        
        # Sort all points by timestamp
        all_points.sort(key=lambda x: x['timestamp'])
        
        if not all_points:
            raise ValueError("No valid track points found in GPX file")
        
        # Split points based on time and distance criteria
        split_tracks = []
        current_track = []
        last_point = None
        
        for point in all_points:
            if not current_track:
                # Start a new track
                current_track = [point]
                last_point = point
            else:
                # Calculate time difference
                time_diff = point['timestamp'] - last_point['timestamp']
                time_diff_hours = time_diff.total_seconds() / 3600
                
                # Calculate distance
                distance = calculate_distance(
                    last_point['lat'], last_point['lon'],
                    point['lat'], point['lon']
                )
                
                # Check if we should split
                if time_diff_hours >= max_time_hours and distance <= max_distance_nm:
                    # Create a new track
                    if current_track:
                        split_tracks.append(current_track)
                    current_track = [point]
                else:
                    # Continue current track
                    current_track.append(point)
                
                last_point = point
        
        # Add the last track if it has points
        if current_track:
            split_tracks.append(current_track)
        
        # Create GPX content for each split track
        track_files = []
        for i, track_points in enumerate(split_tracks):
            if not track_points:
                continue
                
            # Calculate track statistics
            start_time = track_points[0]['timestamp']
            end_time = track_points[-1]['timestamp']
            duration = end_time - start_time
            
            # Calculate total distance
            total_distance = 0
            for j in range(1, len(track_points)):
                total_distance += calculate_distance(
                    track_points[j-1]['lat'], track_points[j-1]['lon'],
                    track_points[j]['lat'], track_points[j]['lon']
                )
            
            # Generate track name based on start and end locations
            start_lat, start_lon = track_points[0]['lat'], track_points[0]['lon']
            end_lat, end_lon = track_points[-1]['lat'], track_points[-1]['lon']
            track_name = generate_track_name(start_lat, start_lon, end_lat, end_lon)
            
            gpx_content = create_gpx_content(track_points, track_name)
            
            track_files.append({
                'name': track_name,
                'gpx_content': gpx_content,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'total_distance_nm': total_distance,
                'point_count': len(track_points),
                'points': track_points  # Include points for map display
            })
        
        logger.info(f"Created {len(track_files)} split track files")
        return track_files
        
    except Exception as e:
        logger.error(f"Error splitting GPX file: {str(e)}")
        raise

def split_gpx_by_tracks(gpx_content):
    """
    Split a GPX file into separate files based on individual track tags.
    
    Args:
        gpx_content (str): The GPX file content as a string
        
    Returns:
        list: List of dictionaries with track info and GPX content
    """
    try:
        # Parse the GPX file
        tracks = parse_gpx_file(gpx_content)
        
        if not tracks:
            raise ValueError("No valid tracks found in GPX file")
        
        # Create GPX content for each track
        track_files = []
        for track in tracks:
            gpx_content = create_gpx_content(track['points'], track['name'])
            
            track_files.append({
                'name': track['name'],
                'gpx_content': gpx_content,
                'start_time': track['start_time'],
                'end_time': track['end_time'],
                'duration': track['duration'],
                'total_distance_nm': track['total_distance_nm'],
                'point_count': track['point_count'],
                'points': track['points']  # Include points for map display
            })
        
        logger.info(f"Created {len(track_files)} track files")
        return track_files
        
    except Exception as e:
        logger.error(f"Error splitting GPX file: {str(e)}")
        raise

