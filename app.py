"""
GPX Track Splitter - A web application for splitting GPX track files

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

from flask import Flask, render_template, request, jsonify, make_response
from gpx_splitter import split_gpx_file, split_gpx_by_tracks
import logging
import requests
import time
import uuid
import re
from threading import Lock, Thread

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress Werkzeug development server warning
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask(__name__)

# Increase max content length to handle large GPX files (default is 16MB)
# Set to 100MB to handle very large GPX files
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

# Store progress and results for ongoing operations
progress_store = {}
results_store = {}
progress_lock = Lock()

def reverse_geocode(lat, lon):
    """
    Reverse geocode coordinates to get place name using Nominatim (OpenStreetMap).
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        
    Returns:
        str: Place name or None if lookup fails
    """
    try:
        # Use Nominatim API (free, no API key required)
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'GPX-Track-Splitter/1.0'  # Required by Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract a meaningful place name
        address = data.get('address', {})
        
        # Try to get a good place name in order of preference
        place_name = None
        if address.get('city'):
            place_name = address['city']
        elif address.get('town'):
            place_name = address['town']
        elif address.get('village'):
            place_name = address['village']
        elif address.get('municipality'):
            place_name = address['municipality']
        elif address.get('county'):
            place_name = address['county']
        elif address.get('state'):
            place_name = address['state']
        elif address.get('country'):
            place_name = address['country']
        
        # If we have a city/town, add state/country for context
        if place_name and (address.get('city') or address.get('town') or address.get('village')):
            if address.get('state'):
                place_name = f"{place_name}, {address['state']}"
            elif address.get('country'):
                place_name = f"{place_name}, {address['country']}"
        
        # Fallback to display_name if nothing else works
        if not place_name:
            display_name = data.get('display_name', '')
            if display_name:
                # Take first part of display name (usually the most specific)
                place_name = display_name.split(',')[0].strip()
        
        # Rate limiting: Nominatim requires max 1 request per second
        time.sleep(1.1)
        
        return place_name if place_name else None
        
    except Exception as e:
        logger.warning(f"Reverse geocoding failed for {lat},{lon}: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('gpx_splitter.html')

@app.route('/split-gpx', methods=['POST'])
def split_gpx():
    try:
        # Check if file was uploaded
        if 'gpx_file' not in request.files:
            logger.error("No file uploaded")
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['gpx_file']
        if file.filename == '':
            logger.error("No file selected")
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Get splitting method and parameters
        split_method = request.form.get('split_method', 'tracks')  # Default to track-based splitting
        max_distance_nm = float(request.form.get('max_distance_nm', 1.0))
        max_time_hours = float(request.form.get('max_time_hours', 1.0))
        require_timestamps = request.form.get('require_timestamps', 'false').lower() == 'true'
        # Checkbox: if present and value is 'true', then lookup is enabled
        # If checkbox is unchecked, the key won't be in form data, so default to False
        lookup_place_names = request.form.get('lookup_place_names', 'false').lower() == 'true'
        
        logger.info(f"Processing GPX file: {file.filename} with method: {split_method}")
        logger.info(f"Parameters: max_distance_nm={max_distance_nm}, max_time_hours={max_time_hours}, require_timestamps={require_timestamps}")
        
        # Read file content
        gpx_content = file.read().decode('utf-8')
        logger.debug(f"File content length: {len(gpx_content)} characters")
        
        # Generate a unique ID for this operation (before processing)
        operation_id = str(uuid.uuid4())
        
        # Split the GPX file based on method
        if split_method == 'time':
            # Time-based splitting
            track_files = split_gpx_file(gpx_content, max_distance_nm, max_time_hours, require_timestamps)
        else:
            # Track-based splitting (default)
            track_files = split_gpx_by_tracks(gpx_content)
        
        # Initialize progress after we know how many tracks we have
        total_lookups = len(track_files) * 2 if lookup_place_names else 0  # 2 lookups per track (start and end)
        with progress_lock:
            progress_store[operation_id] = {
                'total': total_lookups,
                'completed': 0,
                'current_track': 0,
                'total_tracks': len(track_files),
                'status': 'processing',
                'lookup_place_names': lookup_place_names
            }
            results_store[operation_id] = {
                'tracks': None,
                'split_method': split_method,
                'error': None
            }
        
        # Start geocoding in background thread (or skip if disabled)
        def geocode_tracks():
            try:
                tracks_data = []
                
                # If place name lookup is disabled, process immediately without geocoding
                if not lookup_place_names:
                    # Process all tracks quickly without geocoding
                    for idx, track in enumerate(track_files):
                        # Convert points to format suitable for JSON
                        points_data = []
                        for point in track['points']:
                            points_data.append({
                                'lat': point['lat'],
                                'lon': point['lon'],
                                'timestamp': point['timestamp'].isoformat()
                            })
                        
                        # Get start and end coordinates
                        start_lat = track['points'][0]['lat']
                        start_lon = track['points'][0]['lon']
                        end_lat = track['points'][-1]['lat']
                        end_lon = track['points'][-1]['lon']
                        
                        # Format coordinates
                        start_coords = f"{start_lat:.4f},{start_lon:.4f}"
                        end_coords = f"{end_lat:.4f},{end_lon:.4f}"
                        
                        tracks_data.append({
                            'name': track['name'],
                            'start_time': track['start_time'].isoformat(),
                            'end_time': track['end_time'].isoformat(),
                            'duration_hours': round(track['duration'].total_seconds() / 3600, 2),
                            'total_distance_nm': round(track['total_distance_nm'], 2),
                            'point_count': track['point_count'],
                            'gpx_content': track['gpx_content'],
                            'points': points_data,
                            'start_lat': start_lat,
                            'start_lon': start_lon,
                            'end_lat': end_lat,
                            'end_lon': end_lon,
                            'start_coords': start_coords,
                            'end_coords': end_coords,
                            'start_place_name': '',
                            'end_place_name': ''
                        })
                    
                    # Sort tracks by start_time in descending order (newest first)
                    tracks_data.sort(key=lambda x: x['start_time'], reverse=True)
                    
                    # Store results and mark as complete immediately
                    with progress_lock:
                        if operation_id in results_store:
                            results_store[operation_id]['tracks'] = tracks_data
                        if operation_id in progress_store:
                            progress_store[operation_id]['status'] = 'complete'
                            progress_store[operation_id]['completed'] = 0
                            progress_store[operation_id]['current_track'] = len(track_files)
                    
                    logger.info(f"Successfully processed GPX file into {len(tracks_data)} tracks using {split_method} method (place names disabled)")
                    return
                
                # Place name lookup is enabled - process with geocoding
                for idx, track in enumerate(track_files):
                    # Convert points to format suitable for JSON
                    points_data = []
                    for point in track['points']:
                        points_data.append({
                            'lat': point['lat'],
                            'lon': point['lon'],
                            'timestamp': point['timestamp'].isoformat()
                        })
                    
                    # Get start and end coordinates
                    start_lat = track['points'][0]['lat']
                    start_lon = track['points'][0]['lon']
                    end_lat = track['points'][-1]['lat']
                    end_lon = track['points'][-1]['lon']
                    
                    # Update progress - starting track
                    with progress_lock:
                        if operation_id in progress_store:
                            progress_store[operation_id]['current_track'] = idx + 1
                    
                    # Look up place names if enabled
                    start_place_name = ''
                    end_place_name = ''
                    
                    if lookup_place_names:
                        # Look up place names for start and end coordinates
                        logger.info(f"Looking up place names for track {idx + 1}/{len(track_files)}: {track['name']}")
                        start_place_name = reverse_geocode(start_lat, start_lon) or ''
                        
                        # Update progress - completed start lookup
                        with progress_lock:
                            if operation_id in progress_store:
                                progress_store[operation_id]['completed'] += 1
                        
                        end_place_name = reverse_geocode(end_lat, end_lon) or ''
                        
                        # Update progress - completed end lookup
                        with progress_lock:
                            if operation_id in progress_store:
                                progress_store[operation_id]['completed'] += 1
                    else:
                        # Skip geocoding, mark as complete immediately
                        with progress_lock:
                            if operation_id in progress_store:
                                progress_store[operation_id]['completed'] = progress_store[operation_id]['total']
                    
                    # Format coordinates
                    start_coords = f"{start_lat:.4f},{start_lon:.4f}"
                    end_coords = f"{end_lat:.4f},{end_lon:.4f}"
                    
                    tracks_data.append({
                        'name': track['name'],
                        'start_time': track['start_time'].isoformat(),
                        'end_time': track['end_time'].isoformat(),
                        'duration_hours': round(track['duration'].total_seconds() / 3600, 2),
                        'total_distance_nm': round(track['total_distance_nm'], 2),
                        'point_count': track['point_count'],
                        'gpx_content': track['gpx_content'],
                        'points': points_data,
                        'start_lat': start_lat,
                        'start_lon': start_lon,
                        'end_lat': end_lat,
                        'end_lon': end_lon,
                        'start_coords': start_coords,
                        'end_coords': end_coords,
                        'start_place_name': start_place_name,
                        'end_place_name': end_place_name
                    })
                
                # Sort tracks by start_time in descending order (newest first)
                tracks_data.sort(key=lambda x: x['start_time'], reverse=True)
                
                # Store results and mark as complete
                with progress_lock:
                    if operation_id in results_store:
                        results_store[operation_id]['tracks'] = tracks_data
                    if operation_id in progress_store:
                        progress_store[operation_id]['status'] = 'complete'
                        # If place name lookup was disabled, total is 0, so set completed to 0
                        if progress_store[operation_id]['total'] == 0:
                            progress_store[operation_id]['completed'] = 0
                        else:
                            progress_store[operation_id]['completed'] = progress_store[operation_id]['total']
                
                logger.info(f"Successfully processed GPX file into {len(tracks_data)} tracks using {split_method} method (place names: {lookup_place_names})")
            except Exception as e:
                logger.error(f"Error in geocoding thread: {str(e)}")
                with progress_lock:
                    if operation_id in results_store:
                        results_store[operation_id]['error'] = str(e)
                    if operation_id in progress_store:
                        progress_store[operation_id]['status'] = 'error'
        
        # Start background thread
        thread = Thread(target=geocode_tracks, daemon=True)
        thread.start()
        
        # Small delay to ensure operation is initialized before returning
        # This helps prevent race conditions when lookup is disabled
        time.sleep(0.1)
        
        # Return immediately with operation_id
        return jsonify({
            'success': True,
            'operation_id': operation_id,
            'total_tracks': len(track_files),
            'message': 'Processing started. Poll /progress/<operation_id> for updates.'
        })
        
    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error processing GPX file: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error processing GPX file: {str(e)}'
        }), 500

@app.route('/download-gpx/<operation_id>/<int:track_index>', methods=['GET'])
def download_gpx(operation_id, track_index):
    try:
        # Get GPX content from stored results
        with progress_lock:
            results = results_store.get(operation_id, None)
        
        if not results or not results.get('tracks'):
            return jsonify({
                'success': False,
                'error': 'Track data not found. Please process the GPX file again.'
            }), 404
        
        tracks = results['tracks']
        if track_index < 0 or track_index >= len(tracks):
            return jsonify({
                'success': False,
                'error': 'Invalid track index'
            }), 400
        
        track = tracks[track_index]
        gpx_content = track.get('gpx_content')
        if not gpx_content:
            return jsonify({
                'success': False,
                'error': 'No GPX content available for this track'
            }), 400
        
        # Get the track name to use (may have been edited)
        actual_track_name = request.args.get('track_name', track.get('name', 'Track'))
        
        # Sanitize filename - remove/replace invalid characters for filenames
        # Replace invalid filename characters with underscores
        # Invalid chars: / \ : * ? " < > |
        sanitized_filename = re.sub(r'[<>:"/\\|?*]', '_', actual_track_name)
        # Replace commas and multiple spaces with single underscores
        sanitized_filename = re.sub(r'[, ]+', '_', sanitized_filename)
        # Remove leading/trailing underscores and dots
        sanitized_filename = sanitized_filename.strip('_.')
        # Limit length to avoid filesystem issues (255 chars is common limit, leave room for .gpx)
        if len(sanitized_filename) > 240:
            sanitized_filename = sanitized_filename[:240]
        
        # Update the GPX content with the new track name
        import xml.etree.ElementTree as ET
        root = ET.fromstring(gpx_content)
        namespace = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        namespace_uri = 'http://www.topografix.com/GPX/1/1'
        
        # Find and update the track name
        # Try to find trk with namespace first, then without
        trk = root.find(f'.//{{{namespace_uri}}}trk')
        if trk is None:
            trk = root.find('.//gpx:trk', namespace)
        if trk is None:
            trk = root.find('.//trk')
            
        if trk is not None:
            # Remove ALL existing name elements by iterating through children
            # This is the most reliable method
            children_list = list(trk)
            for child in children_list:
                tag = child.tag
                # Check if this is a name element (with or without namespace)
                if tag == 'name' or tag.endswith('}name'):
                    trk.remove(child)
            
            # Find the namespace used by trk element
            trk_tag = trk.tag
            if '}' in trk_tag:
                # Element uses namespace, extract it
                ns_uri = trk_tag.split('}')[0][1:]  # Remove the {
                name_tag = f'{{{ns_uri}}}name'
            else:
                # No namespace, use simple name
                name_tag = 'name'
            
            # Create new name element with proper namespace
            name_elem = ET.Element(name_tag)
            name_elem.text = actual_track_name
            
            # Find trkseg to insert name before it, or insert at beginning
            trkseg = trk.find(f'{{{namespace_uri}}}trkseg')
            if trkseg is None:
                trkseg = trk.find('gpx:trkseg', namespace)
            if trkseg is None:
                trkseg = trk.find('trkseg')
                
            if trkseg is not None:
                # Insert name before trkseg
                trk.insert(list(trk).index(trkseg), name_elem)
            else:
                # No trkseg found, insert at beginning
                trk.insert(0, name_elem)
            
            # Update GPX content with proper XML formatting
            # Register namespaces to avoid prefixes in output
            ET.register_namespace('', 'http://www.topografix.com/GPX/1/1')
            # Use a simple formatting approach that preserves default namespace
            rough_string = ET.tostring(root, encoding='unicode')
            # Parse and reformat to ensure proper structure
            from xml.dom import minidom
            reparsed = minidom.parseString(rough_string)
            gpx_content = reparsed.toprettyxml(indent="  ")
            # Remove extra blank lines that minidom adds
            lines = [line for line in gpx_content.split('\n') if line.strip()]
            gpx_content = '\n'.join(lines)
            
            # Replace namespace prefixes with default namespace
            # Some GPX readers don't handle ns0: prefixes well
            gpx_content = gpx_content.replace('ns0:', '').replace(' xmlns:ns0="http://www.topografix.com/GPX/1/1"', '')
            # Ensure xmlns attribute is present
            if 'xmlns=' not in gpx_content.split('\n')[0]:
                # Add xmlns to the gpx element
                lines = gpx_content.split('\n')
                for i, line in enumerate(lines):
                    if '<gpx' in line and 'xmlns=' not in line:
                        lines[i] = line.replace('<gpx', '<gpx xmlns="http://www.topografix.com/GPX/1/1"')
                        break
                gpx_content = '\n'.join(lines)
            
            # Replace the XML declaration to ensure proper encoding
            if gpx_content.strip().startswith('<?xml'):
                # Remove the old declaration and add a proper one with encoding
                lines = gpx_content.split('\n')
                if lines[0].strip().startswith('<?xml'):
                    gpx_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines[1:])
        
        # Ensure proper XML declaration at the beginning
        if not gpx_content.strip().startswith('<?xml'):
            gpx_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + gpx_content
        
        # Create response with proper headers for download
        response = make_response(gpx_content)
        response.headers['Content-Type'] = 'application/gpx+xml; charset=utf-8'
        # Use sanitized filename for download, but keep original name in GPX content
        response.headers['Content-Disposition'] = f'attachment; filename="{sanitized_filename}.gpx"'
        
        logger.info(f"Downloading GPX file: {sanitized_filename}.gpx (original: {actual_track_name})")
        return response
        
    except Exception as e:
        logger.error(f"Error serving GPX download: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error serving GPX download: {str(e)}'
        }), 500

@app.route('/download-gpx-post/<track_name>', methods=['POST'])
def download_gpx_post(track_name):
    """
    Fallback POST endpoint for downloading GPX files.
    Used when GET endpoint is not available (e.g., operation_id expired).
    Note: This may hit size limits for very large GPX files.
    """
    try:
        # Get the GPX content from the form data
        gpx_content = request.form.get('gpx_content')
        if not gpx_content:
            return jsonify({
                'success': False,
                'error': 'No GPX content provided'
            }), 400
        
        # Get the track name to use (may have been edited)
        actual_track_name = request.form.get('track_name', track_name)
        
        # Sanitize filename
        sanitized_filename = re.sub(r'[<>:"/\\|?*]', '_', actual_track_name)
        sanitized_filename = re.sub(r'[, ]+', '_', sanitized_filename)
        sanitized_filename = sanitized_filename.strip('_.')
        if len(sanitized_filename) > 240:
            sanitized_filename = sanitized_filename[:240]
        
        # Update the GPX content with the new track name
        root = ET.fromstring(gpx_content)
        namespace_uri = 'http://www.topografix.com/GPX/1/1'
        
        trk = root.find(f'.//{{{namespace_uri}}}trk')
        if trk is None:
            trk = root.find('.//trk')
            
        if trk is not None:
            # Remove all name elements
            for child in list(trk):
                if child.tag == 'name' or child.tag.endswith('}name'):
                    trk.remove(child)
            
            # Create new name element
            trk_tag = trk.tag
            if '}' in trk_tag:
                ns_uri = trk_tag.split('}')[0][1:]
                name_tag = f'{{{ns_uri}}}name'
            else:
                name_tag = 'name'
            
            name_elem = ET.Element(name_tag)
            name_elem.text = actual_track_name
            
            trkseg = trk.find(f'{{{namespace_uri}}}trkseg') or trk.find('trkseg')
            if trkseg is not None:
                trk.insert(list(trk).index(trkseg), name_elem)
            else:
                trk.insert(0, name_elem)
            
            # Format XML
            # Register namespaces to avoid prefixes in output
            ET.register_namespace('', 'http://www.topografix.com/GPX/1/1')
            rough_string = ET.tostring(root, encoding='unicode')
            from xml.dom import minidom
            reparsed = minidom.parseString(rough_string)
            gpx_content = reparsed.toprettyxml(indent="  ")
            lines = [line for line in gpx_content.split('\n') if line.strip()]
            gpx_content = '\n'.join(lines)
            
            # Replace namespace prefixes with default namespace
            # Some GPX readers don't handle ns0: prefixes well
            gpx_content = gpx_content.replace('ns0:', '').replace(' xmlns:ns0="http://www.topografix.com/GPX/1/1"', '')
            # Ensure xmlns attribute is present
            if 'xmlns=' not in gpx_content.split('\n')[0]:
                # Add xmlns to the gpx element
                lines = gpx_content.split('\n')
                for i, line in enumerate(lines):
                    if '<gpx' in line and 'xmlns=' not in line:
                        lines[i] = line.replace('<gpx', '<gpx xmlns="http://www.topografix.com/GPX/1/1"')
                        break
                gpx_content = '\n'.join(lines)
            
            # Replace the XML declaration to ensure proper encoding
            if gpx_content.strip().startswith('<?xml'):
                # Remove the old declaration and add a proper one with encoding
                lines = gpx_content.split('\n')
                if lines[0].strip().startswith('<?xml'):
                    gpx_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines[1:])
        
        if not gpx_content.strip().startswith('<?xml'):
            gpx_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + gpx_content
        
        response = make_response(gpx_content)
        response.headers['Content-Type'] = 'application/gpx+xml; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="{sanitized_filename}.gpx"'
        
        logger.info(f"Downloading GPX file via POST: {sanitized_filename}.gpx")
        return response
        
    except Exception as e:
        logger.error(f"Error serving GPX download via POST: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error serving GPX download: {str(e)}'
        }), 500

@app.route('/progress/<operation_id>', methods=['GET'])
def get_progress(operation_id):
    """
    Get progress for a GPX processing operation.
    Returns progress info and results if complete.
    """
    with progress_lock:
        progress = progress_store.get(operation_id, None)
        results = results_store.get(operation_id, None)
    
    if progress is None:
        # Check if results exist even if progress was cleaned up
        if results and results.get('tracks'):
            # Return results even if progress entry is gone
            return jsonify({
                'success': True,
                'status': 'complete',
                'tracks': results['tracks'],
                'split_method': results['split_method'],
                'total_tracks': len(results['tracks']),
                'completed': 0,
                'total': 0
            })
        
        return jsonify({
            'success': False,
            'error': 'Operation not found',
            'status': 'not_found'
        }), 404
    
    remaining = progress['total'] - progress['completed']
    percentage = round((progress['completed'] / progress['total']) * 100, 1) if progress['total'] > 0 else 0
    
    response_data = {
        'success': True,
        'total': progress['total'],
        'completed': progress['completed'],
        'remaining': remaining,
        'current_track': progress['current_track'],
        'total_tracks': progress['total_tracks'],
        'percentage': percentage,
        'status': progress.get('status', 'processing')
    }
    
    # If complete, include results
    if progress.get('status') == 'complete':
        if results and results.get('tracks'):
            response_data['tracks'] = results['tracks']
            response_data['split_method'] = results['split_method']
            response_data['operation_id'] = operation_id  # Include operation_id for downloads
        # Always set status to complete
        response_data['status'] = 'complete'
    elif progress.get('status') == 'error':
        if results and results.get('error'):
            response_data['error'] = results['error']
        response_data['status'] = 'error'
    
    return jsonify(response_data)

@app.route('/update-track-name', methods=['POST'])
def update_track_name():
    try:
        data = request.get_json()
        track_index = data.get('track_index')
        new_name = data.get('new_name')
        start_place_name = data.get('start_place_name')
        end_place_name = data.get('end_place_name')
        
        if track_index is None or new_name is None:
            return jsonify({
                'success': False,
                'error': 'Missing track_index or new_name'
            }), 400
        
        # Validate track index
        if not isinstance(track_index, int) or track_index < 0:
            return jsonify({
                'success': False,
                'error': 'Invalid track_index'
            }), 400
        
        # Validate new name
        if not new_name.strip():
            return jsonify({
                'success': False,
                'error': 'Track name cannot be empty'
            }), 400
        
        # In a real application, you would store this in a database
        # For now, we'll just return success
        logger.info(f"Track {track_index} renamed to: {new_name}")
        if start_place_name:
            logger.info(f"Start place name updated to: {start_place_name}")
        if end_place_name:
            logger.info(f"End place name updated to: {end_place_name}")
        
        return jsonify({
            'success': True,
            'message': f'Track renamed to "{new_name}"'
        })
        
    except Exception as e:
        logger.error(f"Error updating track name: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error updating track name: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)

