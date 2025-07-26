from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime
import swisseph as swe
import math

# --- Initialize the FastAPI Application ---
app = FastAPI(
    title="Astro-Resonance Service (ARS-01)",
    description="A high-precision ephemeris and resonance calculation engine for the FRC ecosystem.",
    version="0.3.0"
)

# --- Data Models for API validation ---

class NatalData(BaseModel):
    """Birth data for natal chart calculations"""
    year: int = Field(..., example=1985)
    month: int = Field(..., example=12)
    day: int = Field(..., example=8)
    hour: int = Field(..., example=13)
    minute: int = Field(..., example=15)
    lat: float = Field(..., example=35.68)
    lon: float = Field(..., example=51.42)

class PlanetaryPositions(BaseModel):
    """Ecliptic longitudes of celestial bodies"""
    sun: float
    moon: float
    mercury: float
    venus: float
    mars: float
    jupiter: float
    saturn: float
    uranus: float
    neptune: float
    pluto: float
    north_node: float

class ARSResponse(BaseModel):
    """Basic response for current weather endpoint"""
    timestamp_utc: str
    transiting_positions: PlanetaryPositions

class CurrentLocation(BaseModel):
    """Current geographic location"""
    lat: float = Field(..., example=35.68, description="Current latitude")
    lon: float = Field(..., example=51.42, description="Current longitude")

class ResonantWeatherRequest(BaseModel):
    """Request body for resonant weather calculations"""
    natal_data: NatalData
    current_location: CurrentLocation

class HouseCusps(BaseModel):
    """Longitudes of the 12 astrological house cusps"""
    house_1: float = Field(..., description="1st House Cusp (Ascendant)")
    house_2: float
    house_3: float
    house_4: float = Field(..., description="4th House Cusp (IC)")
    house_5: float
    house_6: float
    house_7: float = Field(..., description="7th House Cusp (Descendant)")
    house_8: float
    house_9: float
    house_10: float = Field(..., description="10th House Cusp (Midheaven)")
    house_11: float
    house_12: float

class PlanetHouseMapping(BaseModel):
    """Mapping of planets to their house positions"""
    sun: int
    moon: int
    mercury: int
    venus: int
    mars: int
    jupiter: int
    saturn: int
    uranus: int
    neptune: int
    pluto: int
    north_node: int

class NatalChartData(BaseModel):
    """Complete natal chart data"""
    planetary_positions: PlanetaryPositions
    house_cusps: HouseCusps
    planet_house_mapping: PlanetHouseMapping
    ascendant: float = Field(..., description="Ascendant longitude")
    midheaven: float = Field(..., description="Midheaven longitude")

class ResonantWeatherResponse(BaseModel):
    """Complete response with FRC calculations and natal chart data"""
    timestamp_utc: str
    # FRC-specific calculations
    p_nat: float = Field(..., description="Natal pressure")
    p_tra: float = Field(..., description="Transit pressure with latitude gain applied")
    latitude_gain: float = Field(..., description="Latitude gain factor")
    rpi_mismatch: float = Field(..., description="Scalar RPI mismatch |P_tra - P_nat|")
    # Natal chart data
    natal_chart: NatalChartData
    # Current transiting positions
    transiting_positions: PlanetaryPositions

class NatalChartResponse(BaseModel):
    """Response for standalone natal chart endpoint"""
    timestamp_utc: str
    planetary_positions: PlanetaryPositions
    house_cusps: HouseCusps
    planet_house_mapping: PlanetHouseMapping
    ascendant: float = Field(..., description="Ascendant longitude")
    midheaven: float = Field(..., description="Midheaven longitude")

class Aspect(BaseModel):
    """Represents an astrological aspect between two celestial bodies"""
    planet1: str = Field(..., description="First celestial body")
    planet2: str = Field(..., description="Second celestial body")
    aspect_type: str = Field(..., description="Type of aspect (conjunction, opposition, etc.)")
    angle: float = Field(..., description="Exact angle between planets")
    orb: float = Field(..., description="Orb of influence (deviation from exact)")
    is_applying: bool = Field(..., description="Whether aspect is applying or separating")

class RPIVector(BaseModel):
    """2D RPI Vector with Pressure and Tension components"""
    pressure: float = Field(..., description="Pressure component (as before)")
    tension: float = Field(..., description="Tension component from live aspects")
    magnitude: float = Field(..., description="Vector magnitude sqrt(P² + T²)")

class FullReadingRequest(BaseModel):
    """Request body for full reading calculations"""
    natal_data: NatalData
    current_location: CurrentLocation

class FullReadingResponse(BaseModel):
    """Comprehensive response with all FRC calculations, aspects, and transits"""
    timestamp_utc: str
    # RPI calculations
    rpi_vector: RPIVector
    rpi_mismatch: float = Field(..., description="Scalar RPI mismatch (magnitude difference)")
    latitude_gain: float = Field(..., description="Latitude gain factor")
    # Aspect data
    active_transits: list[Aspect] = Field(..., description="Transiting to natal aspects")
    live_aspects: list[Aspect] = Field(..., description="Transiting to transiting aspects")
    # Chart data
    natal_chart: NatalChartData
    transiting_positions: PlanetaryPositions

# --- Set the Ephemeris Path ---
swe.set_ephe_path('./swiss_ephem_data')

# --- FRC Core Calculation Functions ---

def gaussian(x: float, mu: float, sigma: float, amplitude: float) -> float:
    """
    Calculate a Gaussian function value.
    
    Args:
        x: Input value (longitude in degrees)
        mu: Mean (center) of the Gaussian
        sigma: Standard deviation
        amplitude: Peak amplitude
    
    Returns:
        Gaussian function value
    """
    return amplitude * math.exp(-0.5 * ((x - mu) / sigma) ** 2)

def cosmic_flux_map(longitude: float) -> float:
    """
    Calculate the Cosmic Flux Map F(λ) using 5-lobed Gaussian mixture.
    
    The flux map represents cosmic energy variations across ecliptic longitude.
    F(λ) = 1 + G(250, 20, 0.25) + G(310, 15, 0.18) + G(270, 18, 0.15) 
           - G(80, 25, 0.20) - G(35, 25, 0.10)
    
    Args:
        longitude: Ecliptic longitude in degrees
    
    Returns:
        Flux value at the given longitude
    """
    # Normalize longitude to [0, 360) range
    longitude = longitude % 360
    
    # Base flux level
    flux = 1.0
    
    # Positive lobes (energy peaks)
    flux += gaussian(longitude, 250, 20, 0.25)
    flux += gaussian(longitude, 310, 15, 0.18)
    flux += gaussian(longitude, 270, 18, 0.15)
    
    # Negative lobes (energy troughs)
    flux -= gaussian(longitude, 80, 25, 0.20)
    flux -= gaussian(longitude, 35, 25, 0.10)
    
    return flux

def latitude_gain(latitude: float) -> float:
    """
    Calculate the Latitude Gain g(φ) using cos^4(φ) formula.
    
    This represents how cosmic influences vary with geographic latitude.
    g(φ) = 1 + 0.15 * (1 - cos(φ)^4)
    
    Args:
        latitude: Geographic latitude in degrees
    
    Returns:
        Latitude gain factor
    """
    # Convert latitude from degrees to radians
    lat_rad = math.radians(latitude)
    
    return 1 + 0.15 * (1 - math.cos(lat_rad) ** 4)

# --- Planetary Weights for FRC Calculations ---
PLANETARY_WEIGHTS = {
    "sun": 1.0,      # Primary luminary
    "moon": 1.0,     # Secondary luminary
    "mercury": 0.8,  # Personal planets
    "venus": 0.8,
    "mars": 0.7,
    "jupiter": 0.7,  # Social planets
    "saturn": 0.7,
    "uranus": 0.5,   # Transpersonal planets
    "neptune": 0.4,
    "pluto": 0.3,
    "north_node": 0.6  # Lunar node
}

# --- Aspect Definitions ---
ASPECT_DEFINITIONS = {
    "conjunction": {"angle": 0, "orb": 8, "weight": 1.0},
    "opposition": {"angle": 180, "orb": 8, "weight": 0.8},
    "square": {"angle": 90, "orb": 6, "weight": 0.7},
    "trine": {"angle": 120, "orb": 6, "weight": 0.6},
    "sextile": {"angle": 60, "orb": 4, "weight": 0.5}
}

def calculate_pressure(positions: dict, location_lat: float, location_lon: float) -> float:
    """
    Calculate pressure as a weighted sum of planetary influences.
    
    Each planet's contribution is its weight multiplied by the cosmic flux
    at its ecliptic longitude position.
    
    Args:
        positions: Dictionary of planet names to ecliptic longitudes
        location_lat: Geographic latitude (currently unused but reserved)
        location_lon: Geographic longitude (currently unused but reserved)
    
    Returns:
        Total pressure value
    """
    pressure = 0.0
    
    for planet, longitude in positions.items():
        if planet in PLANETARY_WEIGHTS:
            weight = PLANETARY_WEIGHTS[planet]
            flux = cosmic_flux_map(longitude)
            pressure += weight * flux
    
    return pressure

# --- Astronomical Calculation Functions ---

def get_planetary_positions(year: int, month: int, day: int, hour: int, minute: int) -> dict:
    """
    Calculate planetary positions for a specific date and time.
    
    Args:
        year: Year (4 digits)
        month: Month (1-12)
        day: Day (1-31)
        hour: Hour (0-23)
        minute: Minute (0-59)
    
    Returns:
        Dictionary mapping planet names to ecliptic longitudes
    """
    # Convert to Julian Day Number
    julian_day = swe.julday(year, month, day, hour + minute/60.0)
    
    # Define Swiss Ephemeris planet IDs
    planet_ids = {
        "sun": swe.SUN,
        "moon": swe.MOON,
        "mercury": swe.MERCURY,
        "venus": swe.VENUS,
        "mars": swe.MARS,
        "jupiter": swe.JUPITER,
        "saturn": swe.SATURN,
        "uranus": swe.URANUS,
        "neptune": swe.NEPTUNE,
        "pluto": swe.PLUTO,
        "north_node": swe.TRUE_NODE
    }
    
    positions = {}
    # Use Swiss Ephemeris with speed flag
    iflag = swe.FLG_SWIEPH | swe.FLG_SPEED
    
    for name, planet_id in planet_ids.items():
        # Calculate planet position
        pos_data, _ = swe.calc_ut(julian_day, planet_id, iflag)
        positions[name] = pos_data[0]  # Extract ecliptic longitude
    
    return positions

def calculate_houses(year: int, month: int, day: int, hour: int, minute: int, 
                   lat: float, lon: float) -> tuple:
    """
    Calculate house cusps using Placidus system.
    
    Args:
        year, month, day, hour, minute: Birth date and time
        lat: Geographic latitude
        lon: Geographic longitude
    
    Returns:
        Tuple of (cusps, ascmc) where:
        - cusps: List of 12 house cusp longitudes
        - ascmc: Array containing special points (ASC, MC, ARMC, Vertex, etc.)
    """
    # Convert to Julian Day Number
    julian_day = swe.julday(year, month, day, hour + minute/60.0)
    
    # Calculate houses using Placidus system (b'P')
    cusps, ascmc = swe.houses_ex(julian_day, lat, lon, b'P')
    
    return cusps, ascmc

def determine_planet_houses(planet_positions: dict, house_cusps: list) -> dict:
    """
    Determine which house each planet occupies.
    
    Uses the principle that a planet is in a house if its longitude
    falls between that house's cusp and the next house's cusp.
    
    Args:
        planet_positions: Dictionary of planet names to longitudes
        house_cusps: List of 12 house cusp longitudes
    
    Returns:
        Dictionary mapping planet names to house numbers (1-12)
    """
    planet_houses = {}
    
    for planet, longitude in planet_positions.items():
        # Normalize longitude to 0-360 range
        longitude = longitude % 360
        
        # Find which house contains this longitude
        house = 1
        for i in range(12):
            cusp1 = house_cusps[i]
            cusp2 = house_cusps[(i + 1) % 12]
            
            # Handle the case where house crosses 0° Aries
            if cusp1 > cusp2:
                if longitude >= cusp1 or longitude < cusp2:
                    house = i + 1
                    break
            else:
                if cusp1 <= longitude < cusp2:
                    house = i + 1
                    break
        
        planet_houses[planet] = house
    
    return planet_houses

# --- Aspect Calculation Functions ---

def normalize_angle(angle: float) -> float:
    """
    Normalize an angle to the range [0, 360).
    
    Args:
        angle: Angle in degrees
    
    Returns:
        Normalized angle between 0 and 360 degrees
    """
    return angle % 360

def calculate_angular_separation(lon1: float, lon2: float) -> float:
    """
    Calculate the shortest angular separation between two longitudes.
    
    Args:
        lon1: First longitude in degrees
        lon2: Second longitude in degrees
    
    Returns:
        Angular separation in degrees (0-180)
    """
    diff = abs(normalize_angle(lon1) - normalize_angle(lon2))
    if diff > 180:
        diff = 360 - diff
    return diff

def check_aspect(lon1: float, lon2: float, aspect_def: dict) -> tuple[bool, float]:
    """
    Check if two planets form a specific aspect.
    
    Args:
        lon1: Longitude of first planet
        lon2: Longitude of second planet
        aspect_def: Aspect definition with angle and orb
    
    Returns:
        Tuple of (is_aspect, orb_value)
    """
    separation = calculate_angular_separation(lon1, lon2)
    exact_angle = aspect_def["angle"]
    max_orb = aspect_def["orb"]
    
    orb = abs(separation - exact_angle)
    is_aspect = orb <= max_orb
    
    return is_aspect, orb

def calculate_aspects(positions1: dict, positions2: dict, 
                     check_same: bool = False) -> list[Aspect]:
    """
    Calculate all major aspects between two sets of planetary positions.
    
    Args:
        positions1: First set of planetary positions
        positions2: Second set of planetary positions
        check_same: If True, avoid duplicate aspects when comparing same set
    
    Returns:
        List of Aspect objects
    """
    aspects = []
    
    for planet1, lon1 in positions1.items():
        for planet2, lon2 in positions2.items():
            # Skip if checking same set and already processed
            if check_same and planet1 >= planet2:
                continue
                
            # Check each aspect type
            for aspect_type, aspect_def in ASPECT_DEFINITIONS.items():
                is_aspect, orb = check_aspect(lon1, lon2, aspect_def)
                
                if is_aspect:
                    # Determine if applying (planets moving closer)
                    # This is simplified; real calculation would need planet speeds
                    is_applying = orb < aspect_def["orb"] / 2
                    
                    aspects.append(Aspect(
                        planet1=planet1,
                        planet2=planet2,
                        aspect_type=aspect_type,
                        angle=calculate_angular_separation(lon1, lon2),
                        orb=round(orb, 2),
                        is_applying=is_applying
                    ))
                    break  # Only one aspect type per planet pair
    
    return aspects

def calculate_tension_from_aspects(live_aspects: list[Aspect]) -> float:
    """
    Calculate the tension component from live aspects.
    
    Tension increases with the number and strength of aspects,
    particularly hard aspects (squares and oppositions).
    
    Args:
        live_aspects: List of aspects between transiting planets
    
    Returns:
        Tension value
    """
    tension = 0.0
    
    for aspect in live_aspects:
        aspect_def = ASPECT_DEFINITIONS[aspect.aspect_type]
        weight = aspect_def["weight"]
        
        # Hard aspects contribute more to tension
        if aspect.aspect_type in ["square", "opposition"]:
            weight *= 1.5
        
        # Closer orbs have stronger influence
        orb_factor = 1 - (aspect.orb / aspect_def["orb"])
        
        # Add weighted contribution
        tension += weight * orb_factor
    
    return tension

# --- API Endpoints ---

@app.post("/v1/current_weather", response_model=ARSResponse)
async def get_current_astronomical_data(natal_data: NatalData):
    """
    Provides the current transiting planetary positions.
    
    This is a lightweight endpoint for basic astronomical data retrieval.
    """
    try:
        # Get current UTC time
        now = datetime.utcnow()
        
        # Calculate current planetary positions
        positions = get_planetary_positions(
            now.year, now.month, now.day, 
            now.hour, now.minute
        )
        
        # Round positions for response
        planetary_positions = {
            planet: round(longitude, 4) 
            for planet, longitude in positions.items()
        }
        
        return {
            "timestamp_utc": now.isoformat(),
            "transiting_positions": planetary_positions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/resonant_weather", response_model=ResonantWeatherResponse)
async def get_resonant_weather(request: ResonantWeatherRequest):
    """
    Calculate comprehensive FRC resonant weather data.
    
    This endpoint combines:
    - FRC pressure calculations (P_nat, P_tra)
    - Latitude gain adjustments
    - RPI mismatch calculation
    - Complete natal chart with houses
    - Current transiting positions
    
    This is the primary endpoint for FRC applications.
    """
    try:
        # Extract birth data for clarity
        birth_data = request.natal_data
        current_loc = request.current_location
        
        # Calculate natal planetary positions
        natal_positions = get_planetary_positions(
            birth_data.year, birth_data.month, birth_data.day,
            birth_data.hour, birth_data.minute
        )
        
        # Calculate natal house cusps
        cusps, ascmc = calculate_houses(
            birth_data.year, birth_data.month, birth_data.day,
            birth_data.hour, birth_data.minute,
            birth_data.lat, birth_data.lon
        )
        
        # Extract special points
        ascendant = ascmc[0]
        midheaven = ascmc[1]
        
        # Determine planet-to-house mappings
        planet_houses = determine_planet_houses(natal_positions, cusps)
        
        # Get current transiting planetary positions
        now = datetime.utcnow()
        transit_positions = get_planetary_positions(
            now.year, now.month, now.day,
            now.hour, now.minute
        )
        
        # Calculate natal pressure (P_nat)
        p_nat = calculate_pressure(
            natal_positions,
            birth_data.lat,
            birth_data.lon
        )
        
        # Calculate base transit pressure
        p_tra_base = calculate_pressure(
            transit_positions,
            current_loc.lat,
            current_loc.lon
        )
        
        # Calculate and apply latitude gain
        lat_gain = latitude_gain(current_loc.lat)
        p_tra = p_tra_base * lat_gain
        
        # Calculate RPI mismatch
        rpi_mismatch = abs(p_tra - p_nat)
        
        # Prepare natal chart data
        natal_chart = {
            "planetary_positions": {
                planet: round(longitude, 4) 
                for planet, longitude in natal_positions.items()
            },
            "house_cusps": {
                "house_1": round(cusps[0], 4),
                "house_2": round(cusps[1], 4),
                "house_3": round(cusps[2], 4),
                "house_4": round(cusps[3], 4),
                "house_5": round(cusps[4], 4),
                "house_6": round(cusps[5], 4),
                "house_7": round(cusps[6], 4),
                "house_8": round(cusps[7], 4),
                "house_9": round(cusps[8], 4),
                "house_10": round(cusps[9], 4),
                "house_11": round(cusps[10], 4),
                "house_12": round(cusps[11], 4)
            },
            "planet_house_mapping": planet_houses,
            "ascendant": round(ascendant, 4),
            "midheaven": round(midheaven, 4)
        }
        
        # Prepare transiting positions
        transiting_positions = {
            planet: round(longitude, 4) 
            for planet, longitude in transit_positions.items()
        }
        
        return {
            "timestamp_utc": now.isoformat(),
            "p_nat": round(p_nat, 6),
            "p_tra": round(p_tra, 6),
            "latitude_gain": round(lat_gain, 6),
            "rpi_mismatch": round(rpi_mismatch, 6),
            "natal_chart": natal_chart,
            "transiting_positions": transiting_positions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/natal_chart", response_model=NatalChartResponse)
async def get_natal_chart(natal_data: NatalData):
    """
    Calculate a complete natal chart.
    
    This endpoint provides:
    - Planetary positions at birth
    - House cusps (Placidus system)
    - Planet-to-house mappings
    - Ascendant and Midheaven
    
    This is a standalone endpoint for pure astrological calculations.
    """
    try:
        # Calculate planetary positions
        positions = get_planetary_positions(
            natal_data.year, natal_data.month, natal_data.day,
            natal_data.hour, natal_data.minute
        )
        
        # Calculate house cusps
        cusps, ascmc = calculate_houses(
            natal_data.year, natal_data.month, natal_data.day,
            natal_data.hour, natal_data.minute,
            natal_data.lat, natal_data.lon
        )
        
        # Extract special points
        ascendant = ascmc[0]
        midheaven = ascmc[1]
        
        # Determine planet-to-house mappings
        planet_houses = determine_planet_houses(positions, cusps)
        
        # Prepare response data
        house_cusps = {
            "house_1": round(cusps[0], 4),
            "house_2": round(cusps[1], 4),
            "house_3": round(cusps[2], 4),
            "house_4": round(cusps[3], 4),
            "house_5": round(cusps[4], 4),
            "house_6": round(cusps[5], 4),
            "house_7": round(cusps[6], 4),
            "house_8": round(cusps[7], 4),
            "house_9": round(cusps[8], 4),
            "house_10": round(cusps[9], 4),
            "house_11": round(cusps[10], 4),
            "house_12": round(cusps[11], 4)
        }
        
        planetary_positions = {
            planet: round(longitude, 4) 
            for planet, longitude in positions.items()
        }
        
        return {
            "timestamp_utc": datetime.utcnow().isoformat(),
            "planetary_positions": planetary_positions,
            "house_cusps": house_cusps,
            "planet_house_mapping": planet_houses,
            "ascendant": round(ascendant, 4),
            "midheaven": round(midheaven, 4)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/full_reading", response_model=FullReadingResponse)
async def get_full_reading(request: FullReadingRequest):
    """
    Calculate comprehensive FRC full reading with aspects and 2D RPI vector.
    
    This is the primary endpoint for the FRC ecosystem, providing:
    - 2D RPI Vector (Pressure, Tension)
    - Active transits (transiting to natal aspects)
    - Live aspects (current sky aspects)
    - Complete natal chart data
    - Current transiting positions
    """
    try:
        # Extract request data
        birth_data = request.natal_data
        current_loc = request.current_location
        
        # Calculate natal planetary positions
        natal_positions = get_planetary_positions(
            birth_data.year, birth_data.month, birth_data.day,
            birth_data.hour, birth_data.minute
        )
        
        # Calculate natal house cusps
        cusps, ascmc = calculate_houses(
            birth_data.year, birth_data.month, birth_data.day,
            birth_data.hour, birth_data.minute,
            birth_data.lat, birth_data.lon
        )
        
        # Extract special points
        ascendant = ascmc[0]
        midheaven = ascmc[1]
        
        # Determine planet-to-house mappings
        planet_houses = determine_planet_houses(natal_positions, cusps)
        
        # Get current transiting planetary positions
        now = datetime.utcnow()
        transit_positions = get_planetary_positions(
            now.year, now.month, now.day,
            now.hour, now.minute
        )
        
        # Calculate aspects
        active_transits = calculate_aspects(transit_positions, natal_positions)
        live_aspects = calculate_aspects(transit_positions, transit_positions, check_same=True)
        
        # Calculate natal pressure (P_nat)
        p_nat = calculate_pressure(
            natal_positions,
            birth_data.lat,
            birth_data.lon
        )
        
        # Calculate base transit pressure
        p_tra_base = calculate_pressure(
            transit_positions,
            current_loc.lat,
            current_loc.lon
        )
        
        # Calculate and apply latitude gain
        lat_gain = latitude_gain(current_loc.lat)
        p_tra = p_tra_base * lat_gain
        
        # Calculate tension from live aspects
        tension = calculate_tension_from_aspects(live_aspects)
        
        # Create RPI vectors
        rpi_natal = RPIVector(
            pressure=p_nat,
            tension=0.0,  # Natal has no tension component
            magnitude=p_nat
        )
        
        rpi_current = RPIVector(
            pressure=p_tra,
            tension=tension,
            magnitude=math.sqrt(p_tra**2 + tension**2)
        )
        
        # Calculate RPI mismatch (magnitude difference)
        rpi_mismatch = abs(rpi_current.magnitude - rpi_natal.magnitude)
        
        # Prepare natal chart data
        natal_chart = {
            "planetary_positions": {
                planet: round(longitude, 4) 
                for planet, longitude in natal_positions.items()
            },
            "house_cusps": {
                "house_1": round(cusps[0], 4),
                "house_2": round(cusps[1], 4),
                "house_3": round(cusps[2], 4),
                "house_4": round(cusps[3], 4),
                "house_5": round(cusps[4], 4),
                "house_6": round(cusps[5], 4),
                "house_7": round(cusps[6], 4),
                "house_8": round(cusps[7], 4),
                "house_9": round(cusps[8], 4),
                "house_10": round(cusps[9], 4),
                "house_11": round(cusps[10], 4),
                "house_12": round(cusps[11], 4)
            },
            "planet_house_mapping": planet_houses,
            "ascendant": round(ascendant, 4),
            "midheaven": round(midheaven, 4)
        }
        
        # Prepare transiting positions
        transiting_positions = {
            planet: round(longitude, 4) 
            for planet, longitude in transit_positions.items()
        }
        
        return {
            "timestamp_utc": now.isoformat(),
            "rpi_vector": {
                "pressure": round(p_tra, 6),
                "tension": round(tension, 6),
                "magnitude": round(rpi_current.magnitude, 6)
            },
            "rpi_mismatch": round(rpi_mismatch, 6),
            "latitude_gain": round(lat_gain, 6),
            "active_transits": active_transits,
            "live_aspects": live_aspects,
            "natal_chart": natal_chart,
            "transiting_positions": transiting_positions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Root endpoint for service health check"""
    return {"message": "Astro-Resonance Service is online. Awaiting coherent queries."}