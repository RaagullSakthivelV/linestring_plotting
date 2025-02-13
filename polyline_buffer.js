const polyline = require('@mapbox/polyline');
const turf = require('@turf/turf');

function getBufferedLineStringWKT(encodedPolyline, bufferRadius = 5) {
    var decodedCoordinates = polyline.decode(encodedPolyline).map(coord => [coord[1], coord[0]]);
    
    if (decodedCoordinates.length === 0) {
        console.error("Decoded polyline is empty");
        return null;
    }

    var geojsonLine = turf.lineString(decodedCoordinates);
    var buffered = turf.buffer(geojsonLine, bufferRadius, { units: 'kilometers' });

    if (buffered.geometry.type === "Polygon") {
        var coordinates = buffered.geometry.coordinates[0]
            .map(coord => `${coord[1]} ${coord[0]}`);

        return `LINESTRING(${coordinates.join(", ")})`;
    }

    console.error("Buffer did not generate a valid polygon");
    return null;
}

// Read from command line arguments
const encodedPolyline = process.argv[2];
const bufferRadius = process.argv[3] ? parseFloat(process.argv[3]) : 5;

console.log(getBufferedLineStringWKT(encodedPolyline, bufferRadius));
