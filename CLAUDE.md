# ARS (Astro-Resonance Service) Project Memory

## Project Overview
The Astro-Resonance Service (ARS-01) is a high-precision ephemeris and resonance calculation engine for the FRC ecosystem. It provides astronomical calculations, astrological house systems, aspect analysis, and FRC-specific resonance calculations.

## Current Version: 0.3.0

## Key Components

### Swiss Ephemeris Data
- Location: `./swiss_ephem_data/`
- Files: seas_18.se1, semo_18.se1, sepl_18.se1
- Source: Downloaded from https://github.com/aloistr/swisseph/tree/master/ephe

### Python Environment
- Virtual environment: `./venv/`
- Activation: `source venv/bin/activate`
- Dependencies: fastapi, uvicorn[standard], pyswisseph

### Server Management
- Start command: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- Server logs: `./server.log`
- Default port: 8000

## API Endpoints

### 1. GET / 
- Health check endpoint
- Returns: Service status message

### 2. POST /v1/current_weather
- Basic transiting planetary positions
- Input: NatalData (not actually used, just for compatibility)
- Output: Current planetary longitudes

### 3. POST /v1/resonant_weather
- FRC calculations with natal chart
- Input: NatalData + CurrentLocation
- Output: P_nat, P_tra, latitude_gain, rpi_mismatch, natal chart

### 4. POST /v1/natal_chart
- Standalone natal chart calculation
- Input: NatalData
- Output: Planetary positions, house cusps (Placidus), planet-house mappings

### 5. POST /v1/full_reading (PRIMARY)
- Complete FRC analysis with aspects
- Input: NatalData + CurrentLocation
- Output: 2D RPI Vector, active transits, live aspects, natal chart

## FRC Mathematical Components

### Cosmic Flux Map F(»)
- 5-lobed Gaussian mixture
- Formula: 1 + G(250,20,0.25) + G(310,15,0.18) + G(270,18,0.15) - G(80,25,0.20) - G(35,25,0.10)

### Latitude Gain g(Æ)
- Formula: 1 + 0.15 * (1 - cos(Æ)^4)

### Planetary Weights
- Sun/Moon: 1.0
- Mercury/Venus: 0.8
- Mars/Jupiter/Saturn: 0.7
- Uranus: 0.5
- Neptune: 0.4
- Pluto: 0.3
- North Node: 0.6

### Aspect Orbs
- Conjunction: 0° ±8°
- Opposition: 180° ±8°
- Square: 90° ±6°
- Trine: 120° ±6°
- Sextile: 60° ±4°

### RPI Vector
- Pressure: Weighted sum of planetary flux values
- Tension: Calculated from live aspects (hard aspects weighted 1.5x)
- Magnitude: sqrt(Pressure² + Tension²)

## Development History

### v0.1.0 - Initial Release
- Basic planetary position calculations
- Current weather endpoint
- FRC pressure calculations

### v0.2.0 - House System Integration
- Added Placidus house calculations
- Natal chart endpoint
- Planet-to-house mappings
- Combined resonant_weather endpoint

### v0.3.0 - Aspect Engine
- Dynamic aspect calculations
- 2D RPI Vector (Pressure + Tension)
- Active transits and live aspects
- Full reading endpoint as primary data source

## Testing Examples

### Test Full Reading
```bash
curl -X POST "http://localhost:8000/v1/full_reading" \
  -H "Content-Type: application/json" \
  -d '{
    "natal_data": {
      "year": 1985, "month": 12, "day": 8,
      "hour": 13, "minute": 15,
      "lat": 35.68, "lon": 51.42
    },
    "current_location": {
      "lat": 40.7128, "lon": -74.0060
    }
  }'
```

## Common Operations

### Restart Server
```bash
pkill -f "uvicorn main:app"
source venv/bin/activate
nohup uvicorn main:app --reload --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

### Check Server Status
```bash
curl http://localhost:8000/
```

### View API Documentation
Browse to: http://localhost:8000/docs

## Architecture Notes
- FastAPI for web framework
- Pydantic for data validation
- Swiss Ephemeris (pyswisseph) for astronomical calculations
- Placidus house system as default
- All calculations in tropical zodiac
- Timestamps in UTC

## Future Enhancement Ideas
- Additional house systems (Koch, Equal, Whole Sign)
- Minor aspects (quintile, septile, etc.)
- Asteroid positions
- Progressed chart calculations
- Chart comparison (synastry)
- Pre-calculated natal chart storage with IDs