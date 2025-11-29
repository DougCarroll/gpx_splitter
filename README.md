# GPX Track Splitter

A standalone Python web application for splitting GPX track files. Split tracks by track tags or by time/distance criteria, visualize tracks on an interactive map, and download individual track files.

## Features

- **Split by Track Tags**: Split a GPX file into separate files based on individual `<trk>` tags
- **Split by Time/Distance**: Split tracks based on maximum time gaps and distance thresholds
- **Interactive Map**: Visualize tracks on a map using Leaflet.js with start/end markers
- **Track Statistics**: View distance, duration, point count, and timestamps for each track
- **Download Individual Tracks**: Download each split track as a separate GPX file
- **Edit Track Names**: Click on track names to edit them inline
- **Place Name Lookup**: Automatically looks up geographic place names for start and end coordinates using OpenStreetMap Nominatim
- **Editable Place Names**: Edit place names for each track's start and end locations
- **Flexible Naming**: Choose to use place names or coordinates in track names via checkboxes
- **Coordinate Display**: View both place names and coordinates (lat/long) for each track

## Dependencies

### Python Dependencies (via pip)
- `Flask==2.3.3` - Web framework
- `Werkzeug>=2.3.7` - WSGI utilities (dependency of Flask)
- `requests==2.31.0` - HTTP library for reverse geocoding API calls

### External Dependencies (CDN, no installation needed)
- Leaflet.js 1.9.4 - Map visualization (loaded from CDN)
- OpenStreetMap tiles - Map tiles (loaded from CDN)

### Python Standard Library (no installation needed)
- `xml.etree.ElementTree` - GPX XML parsing
- `datetime` - Timestamp handling
- `logging` - Logging functionality
- `math` - Distance calculations

## Installation

### Prerequisites

- Python 3.6 or higher
- pip (Python package installer)
- Internet connection (for map tiles and geocoding)

### macOS Installation

1. **Check if Python is installed**:
   ```bash
   python3 --version
   ```
   If Python is not installed, download it from [python.org](https://www.python.org/downloads/) or install via Homebrew:
   ```bash
   brew install python3
   ```

2. **Navigate to the project directory**:
   ```bash
   cd /path/to/gpx_splitter
   ```

3. **Install Python dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```
   
   If you encounter permission errors, use:
   ```bash
   pip3 install --user -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python3 app.py
   ```

### Windows Installation

1. **Check if Python is installed**:
   - Open Command Prompt (Win + R, type `cmd`, press Enter)
   - Type: `python --version` or `py --version`
   - If Python is not installed, download it from [python.org](https://www.python.org/downloads/)
     - **Important**: During installation, check "Add Python to PATH"

2. **Navigate to the project directory**:
   ```cmd
   cd C:\path\to\gpx_splitter
   ```
   Or use File Explorer to navigate to the folder, then right-click and select "Open in Terminal" or "Open PowerShell window here"

3. **Install Python dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```
   
   If you get an error about pip not being found, try:
   ```cmd
   python -m pip install -r requirements.txt
   ```
   Or:
   ```cmd
   py -m pip install -r requirements.txt
   ```

4. **Run the application**:
   ```cmd
   python app.py
   ```
   Or:
   ```cmd
   py app.py
   ```

### Linux Installation

1. **Check if Python 3 is installed**:
   ```bash
   python3 --version
   ```
   If Python 3 is not installed, install it using your package manager:
   
   **Ubuntu/Debian**:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip
   ```
   
   **Fedora/RHEL/CentOS**:
   ```bash
   sudo dnf install python3 python3-pip
   ```
   
   **Arch Linux**:
   ```bash
   sudo pacman -S python python-pip
   ```

2. **Navigate to the project directory**:
   ```bash
   cd /path/to/gpx_splitter
   ```

3. **Install Python dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```
   
   If you encounter permission errors, use:
   ```bash
   pip3 install --user -r requirements.txt
   ```
   
   Or install system-wide (requires sudo):
   ```bash
   sudo pip3 install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python3 app.py
   ```

### Verifying Installation

After installation, verify that all dependencies are installed correctly:

```bash
# macOS/Linux
python3 -c "import flask, werkzeug, requests; print('All dependencies installed successfully!')"

# Windows
python -c "import flask, werkzeug, requests; print('All dependencies installed successfully!')"
```

If you see "All dependencies installed successfully!", you're ready to run the application.

## Usage

### Starting the Application

**macOS/Linux**:
```bash
python3 app.py
```

**Windows**:
```cmd
python app.py
```
or
```cmd
py app.py
```

### Accessing the Application

Once the server starts, you should see output like:
```
 * Running on http://0.0.0.0:5003
 * Debug mode: on
```

Open your web browser and navigate to:
```
http://localhost:5003
```

**Note**: If you're accessing from another device on the same network, use your computer's IP address instead of `localhost`:
```
http://YOUR_IP_ADDRESS:5003
```

3. **Upload a GPX file**:
   - Click the file upload area or drag and drop a GPX file
   - Choose your splitting method:
     - **Split by Track Tags**: Splits based on `<trk>` elements in the GPX file
     - **Split by Time/Distance**: Splits when time gaps exceed the maximum time threshold and distance is within the maximum distance threshold
   - Click "Split GPX File"

4. **View and download tracks**:
   - View track statistics (distance, duration, points, timestamps)
   - Place names are automatically looked up for start and end coordinates
   - Edit place names by clicking in the place name input fields
   - Use checkboxes to toggle between displaying place names or coordinates in track names
   - Click "View on Map" to visualize individual tracks
   - Click "Show All Tracks" to see all tracks on one map
   - Click "Download GPX" to download individual track files (uses selected name format)
   - Click on track names to edit the full display name

## Project Structure

```
gpx_splitter/
├── app.py                 # Flask web application
├── gpx_splitter.py        # Core GPX splitting logic
├── distance_calculator.py # Distance calculation utilities
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── templates/
    └── gpx_splitter.html # Web interface template
```

## How It Works

### Core Functionality
- **GPX Parsing**: Uses Python's built-in `xml.etree.ElementTree` to parse GPX XML files
- **Distance Calculation**: Uses the Haversine formula to calculate distances between GPS coordinates
- **Track Splitting**: 
  - By tags: Extracts each `<trk>` element as a separate track
  - By time/distance: Splits tracks when time gaps exceed thresholds and distance is within limits

### Web Interface
- **Backend**: Flask web server handles file uploads, GPX processing, and file downloads
- **Frontend**: HTML/CSS/JavaScript with Leaflet.js for map visualization
- **Map Display**: Uses OpenStreetMap tiles (no API key required)

## Limitations

- Maximum file size is limited by Flask's default request size (can be configured)
- Map tiles require internet connection (uses OpenStreetMap CDN)
- Place name lookup requires internet connection (uses Nominatim API)
- Place name lookup is rate-limited to 1 request per second (as per Nominatim usage policy)
- Track name editing is client-side only (not persisted to server between sessions)

## Troubleshooting

### Common Issues

**Python not found**:
- **macOS/Linux**: Use `python3` instead of `python`
- **Windows**: Ensure Python is added to PATH during installation, or use `py` command

**pip not found**:
- **macOS/Linux**: Use `pip3` instead of `pip`, or install pip: `python3 -m ensurepip --upgrade`
- **Windows**: Use `python -m pip` or `py -m pip` instead of `pip`

**Permission denied errors**:
- **macOS/Linux**: Use `pip3 install --user -r requirements.txt` to install for your user only
- **Windows**: Run Command Prompt as Administrator, or use `--user` flag

**Port already in use**: 
Change the port in `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5004)  # Use a different port
```

**File upload fails**: 
- Check that your GPX file is valid XML and contains track points
- Ensure the file is not corrupted
- Try a different GPX file to verify

**Map doesn't load**: 
- Ensure you have an internet connection (required for Leaflet.js and OpenStreetMap tiles)
- Check browser console for errors (F12 in most browsers)
- Try a different browser

**Place names not loading**:
- Ensure you have an internet connection (required for Nominatim API)
- Place name lookup is rate-limited (1 request per second), so it may take time for many tracks
- Check browser console for API errors

**Module not found errors**:
- Ensure you've installed all dependencies: `pip install -r requirements.txt`
- Verify installation: `python -c "import flask, werkzeug, requests"`
- Try reinstalling: `pip install --upgrade -r requirements.txt`

## License

This project is extracted from the burnt_toast project. Use as needed.

## Notes

- No database required - all processing is done in memory
- No containerization needed - runs as a standard Python application
- Minimal dependencies - only Flask, Werkzeug, and requests required (3 packages total)
- Cross-platform - works on macOS, Windows, and Linux without modification

