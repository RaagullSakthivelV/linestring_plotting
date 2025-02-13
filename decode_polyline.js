const polyline = require('@mapbox/polyline');

function getLineStringWKT(encodedPolyline) {
    var decodedCoordinates = polyline.decode(encodedPolyline).map(coord => `${coord[0]} ${coord[1]}`);
    
    if (decodedCoordinates.length === 0) {
        console.error("Decoded polyline is empty");
        return null;
    }

    return `LINESTRING(${decodedCoordinates.join(", ")})`;
}

// Read from command line arguments
const encodedPolyline = process.argv[2];

console.log(getLineStringWKT(encodedPolyline));
