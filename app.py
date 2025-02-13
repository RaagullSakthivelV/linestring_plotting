from flask import Flask, render_template, request
import folium
import pandas as pd
from shapely.geometry import LineString
import os
import logging
import subprocess
from flask import Flask
import jinja2
import requests  # To call a routing API
import psutil

# Initialize Flask app
app = Flask(__name__)

# Disable Jinja2 template caching
app.jinja_env.cache = None

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set logging level to DEBUG for detailed logs
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),  # Logs will be saved in app.log
        logging.StreamHandler()         # Logs will also print to the console
    ]
)

# Function to extract coordinates from LINESTRING input
def extract_coordinates(linestring):
    try:
        linestring = linestring.replace("LINESTRING(", "").replace(")", "")
        coordinates = [tuple(map(float, coord.split())) for coord in linestring.split(",")]
        # logging.debug(f"Extracted coordinates: {coordinates}")
        return coordinates
    except Exception as e:
        # logging.error(f"Error extracting coordinates from LINESTRING: {e}")
        raise ValueError("Invalid LINESTRING format. Please check the input.")
    
# OpenRouteService API Key (Replace with your API key)
ORS_API_KEY = "5b3ce3597851110001cf624874e5749e218d4224a8b27a6d1e35992c"
ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"

# Function to get encoded polyline from OpenRouteService
ORS_API_KEY = "5b3ce3597851110001cf624874e5749e218d4224a8b27a6d1e35992c"
ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car/json"

def get_encoded_polyline(start, end):
    print(f"Getting encoded polyline for start: {start}, end: {end}")
    
    # OpenRouteService requires coordinates in (longitude, latitude) order
    body = {
        "coordinates": [
            [float(start[1]), float(start[0])],  # (lon, lat)
            [float(end[1]), float(end[0])]
        ],
        "radiuses":-1
    }
    
    headers = {
        "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json; charset=utf-8"
    }
    
    response = requests.post(ORS_BASE_URL, json=body, headers=headers)
    
    print(f"Response status code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"Response data: {data}")
        polyline_str = data["routes"][0]["geometry"]  # Extract encoded polyline
        print(f"Encoded polyline: {polyline_str}")
        return polyline_str
    else:
        logging.error(f"Failed to get route: {response.text}")
        print(f"Error response: {response.text}")
        return None
    
def add_red_polyline(map_object, coordinates):
    """Adds a red polyline to the map based on given coordinates."""
    folium.PolyLine(
        [(coord[0], coord[1]) for coord in coordinates], 
        color="red", 
        weight=3.5
    ).add_to(map_object)
    
import subprocess

def get_buffered_wkt(encoded_polyline, buffer_radius=5):
    node_command = ["node", "polyline_buffer.js", encoded_polyline, str(buffer_radius)]

    def get_memory_usage():
        process = psutil.Process(os.getpid())
        return f"{process.memory_info().rss / 1024 / 1024:.2f} MB"

    print(f"Memory Before Subprocess: {get_memory_usage()}")

    try:
        process = subprocess.Popen(node_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()

        print(f"Memory After Subprocess: {get_memory_usage()}")

        if process.returncode == 0:
            return stdout.strip()
        else:
            print("Error:", stderr)
            return None

    except Exception as e:
        print("Subprocess error:", str(e))
        return None

    
def get_decoded_wkt(encoded_polyline):
    node_command = ["node", "decode_polyline.js", encoded_polyline]
    result = subprocess.run(node_command, capture_output=True, text=True)

    if result.returncode == 0:
        # print(result.stdout.strip())
        return result.stdout.strip()
    else:
        print("Error:", result.stderr)
        return None

# Route to upload the CSV file and LINESTRING data
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        logging.info("POST request received.")
        try:
            # Get the uploaded CSV file
            csv_file = request.files["csv_file"]
            linestringoriginal = request.form["linestring"]
            start_lat = request.form["start_lat"]
            start_lng = request.form["start_lng"]
            end_lat = request.form["end_lat"]
            end_lng = request.form["end_lng"]

            if linestringoriginal:
                linestring = linestringoriginal
            else:
                linestring = get_encoded_polyline([start_lat, start_lng], [end_lat, end_lng])

            logging.debug(f"Uploaded file: {csv_file.filename}")
            # logging.debug(f"Received LINESTRING: {linestring}")

            if csv_file:
                # Save the file to a temporary directory
                file_path = os.path.join("uploads", csv_file.filename)
                csv_file.save(file_path)
                logging.info(f"CSV file saved at {file_path}")

                # Load CSV data
                try:
                    data = pd.read_csv(file_path, sep='\t')
                    logging.info(f"CSV loaded successfully. First few rows:\n{data.head()}")
                except Exception as e:
                    logging.error(f"Error loading CSV: {e}")
                    return "Error loading CSV file. Please check the file format."

                # Check for required columns
                required_columns = ['latitude', 'longitude']
                missing_columns = [col for col in required_columns if col not in data.columns]

                if missing_columns:
                    error_message = f"CSV is missing required columns: {', '.join(missing_columns)}"
                    logging.error(error_message)
                    return error_message

                # Ensure numeric values for latitude and longitude
                data['latitude'] = pd.to_numeric(data['latitude'], errors='coerce')
                data['longitude'] = pd.to_numeric(data['longitude'], errors='coerce')
                data = data.dropna()  # Drop rows with invalid coordinates
                logging.info(f"Valid data after cleaning:\n{data}")

                # Extract coordinates from LINESTRING
                decodedlineString = get_buffered_wkt(linestring, 5)
                coordinates = extract_coordinates(decodedlineString)
                decoded_wkt = get_decoded_wkt(linestring)
                coordinatesdecoded_wkt = extract_coordinates(decoded_wkt)

                # Create a LineString from the coordinates
                line = LineString(coordinates)
                # logging.debug(f"Created LineString: {line}")

                # Create a map centered on the first point (latitude, longitude)
                m = folium.Map(location=[coordinates[0][0], coordinates[0][1]], zoom_start=10)
                
                # Add the line to the map
                folium.PolyLine([(coord[0], coord[1]) for coord in coordinates], color="blue", weight=2.5).add_to(m)

                # Add the red polyline for the encoded route
                add_red_polyline(m, coordinatesdecoded_wkt)

                # Add markers to the map
                for _, row in data.iterrows():
                    folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=f"Latitude: {row['latitude']}, Longitude: {row['longitude']}",
                        icon=folium.Icon(color="green", icon="info-sign")
                    ).add_to(m)

                # Save map to HTML
                map_path = 'templates/line_plot_map.html'
                
                # Delete old file if it exists
                if os.path.exists(map_path):
                    os.remove(map_path)

                m.save(map_path)
                logging.info(f"Map saved to {map_path}")

                return render_template("line_plot_map.html")

        except Exception as e:
            logging.error(f"Unexpected error during processing: {e}")
            return f"An error occurred: {e}"

    return render_template("index.html", map_path=None)

if __name__ == "__main__":
    # Create the uploads directory if not exists
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
        logging.info("Created uploads directory.")

    logging.info("Starting Flask app...")
    app.run(debug=True)
