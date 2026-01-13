"""Street lookup functionality using Montreal's Geobase data."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import logging
import math
from pathlib import Path
from typing import Any
import aiohttp
import re

_LOGGER = logging.getLogger(__name__)

# Montreal Geobase Double GeoJSON URL
GEOBASE_URL = "https://donnees.montreal.ca/dataset/88493b16-220f-4709-b57b-1ea57c5ba405/resource/16f7fa0a-9ce6-4b29-a7fc-00842c593927/download/gbdouble.json"

# Nominatim (OpenStreetMap) geocoding URL
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# User-Agent for Nominatim (must include contact info per their usage policy)
NOMINATIM_USER_AGENT = "HomeAssistant-SnowMontreal/1.0 (https://github.com/custom-components/snow_montreal)"

# Cache duration in seconds (24 hours)
CACHE_DURATION = 86400

# Montreal bounding box for geocoding bias
MONTREAL_BBOX = {
    "viewbox": "-73.9745,45.4100,-73.4745,45.7040",
    "bounded": "1",
}


@dataclass
class GeocodedAddress:
    """Represents a geocoded address result."""

    display_name: str
    lat: float
    lon: float
    house_number: str | None
    street: str | None
    city: str | None
    importance: float


@dataclass
class StreetSegment:
    """Represents a street segment from the Geobase."""

    cote_rue_id: int
    street_name: str
    address_start: int | None
    address_end: int | None
    side: str  # "Droit" (Right) or "Gauche" (Left)
    borough: str | None
    full_description: str
    # Geometry - centroid of the street segment
    lat: float | None = None
    lon: float | None = None

    @property
    def address_range(self) -> str:
        """Return a human-readable address range."""
        if self.address_start and self.address_end:
            return f"{self.address_start}-{self.address_end}"
        elif self.address_start:
            return f"{self.address_start}+"
        elif self.address_end:
            return f"up to {self.address_end}"
        return "N/A"

    @property
    def display_name(self) -> str:
        """Return a display name for UI selection."""
        side_str = "R" if self.side == "Droit" else "L"
        return f"{self.street_name} ({self.address_range}, {side_str})"


class StreetLookup:
    """Handles street lookup from Montreal's Geobase."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the street lookup.

        Args:
            cache_dir: Directory to cache the geobase data.
        """
        self._cache_dir = cache_dir
        self._streets: list[StreetSegment] = []
        self._loaded = False
        self._lock = asyncio.Lock()

    async def async_load(self, force_refresh: bool = False) -> bool:
        """Load the geobase data.

        Args:
            force_refresh: Force download even if cache exists.

        Returns:
            True if data was loaded successfully.
        """
        async with self._lock:
            if self._loaded and not force_refresh:
                return True

            try:
                data = await self._async_get_geobase_data(force_refresh)
                self._streets = self._parse_geobase(data)
                self._loaded = True
                _LOGGER.info("Loaded %d street segments from geobase", len(self._streets))
                return True
            except Exception as err:
                _LOGGER.error("Failed to load geobase data: %s", err)
                return False

    async def _async_get_geobase_data(self, force_refresh: bool) -> dict[str, Any]:
        """Get geobase data from cache or download."""
        cache_file = None
        if self._cache_dir:
            cache_file = self._cache_dir / "geobase_cache.json"

            # Try to load from cache (use thread to avoid blocking)
            if not force_refresh and cache_file.exists():
                try:
                    import time
                    cache_age = time.time() - cache_file.stat().st_mtime
                    if cache_age < CACHE_DURATION:
                        _LOGGER.debug("Loading geobase from cache")
                        data = await asyncio.to_thread(
                            self._read_cache_file, cache_file
                        )
                        if data:
                            return data
                except Exception as err:
                    _LOGGER.warning("Failed to read cache: %s", err)

        # Download fresh data
        _LOGGER.info("Downloading geobase data from Montreal Open Data...")
        async with aiohttp.ClientSession() as session:
            async with session.get(GEOBASE_URL, timeout=aiohttp.ClientTimeout(total=120)) as response:
                response.raise_for_status()
                # Disable content-type check in case server returns non-JSON mimetype
                data = await response.json(content_type=None)

        # Save to cache (use thread to avoid blocking)
        if cache_file:
            try:
                await asyncio.to_thread(
                    self._write_cache_file, cache_file, data
                )
                _LOGGER.debug("Saved geobase to cache")
            except Exception as err:
                _LOGGER.warning("Failed to write cache: %s", err)

        return data

    @staticmethod
    def _read_cache_file(cache_file: Path) -> dict[str, Any] | None:
        """Read cache file (blocking, run in thread)."""
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _write_cache_file(cache_file: Path, data: dict[str, Any]) -> None:
        """Write cache file (blocking, run in thread)."""
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data), encoding="utf-8")

    def _parse_geobase(self, data: dict[str, Any]) -> list[StreetSegment]:
        """Parse GeoJSON data into StreetSegment objects."""
        streets = []

        features = data.get("features", [])
        for feature in features:
            try:
                props = feature.get("properties", {})

                cote_rue_id = props.get("COTE_RUE_ID")
                if not cote_rue_id:
                    continue

                street_name = props.get("NOM_VOIE", "").strip()
                if not street_name:
                    continue

                address_start = props.get("DEBUT_ADRESSE")
                address_end = props.get("FIN_ADRESSE")
                side = props.get("COTE", "")
                borough = props.get("NOM_ARR", "") or props.get("ARR", "")

                # Extract centroid from geometry
                lat, lon = self._extract_centroid(feature.get("geometry"))

                # Build full description
                parts = [street_name]
                if address_start or address_end:
                    if address_start and address_end:
                        parts.append(f"({address_start}-{address_end})")
                    elif address_start:
                        parts.append(f"(from {address_start})")

                if side:
                    side_name = "Right side" if side == "Droit" else "Left side"
                    parts.append(f"- {side_name}")

                if borough:
                    parts.append(f"[{borough}]")

                segment = StreetSegment(
                    cote_rue_id=int(cote_rue_id),
                    street_name=street_name,
                    address_start=int(address_start) if address_start else None,
                    address_end=int(address_end) if address_end else None,
                    side=side,
                    borough=borough,
                    full_description=" ".join(parts),
                    lat=lat,
                    lon=lon,
                )
                streets.append(segment)

            except (ValueError, TypeError) as err:
                _LOGGER.debug("Error parsing feature: %s", err)
                continue

        return streets

    def _extract_centroid(self, geometry: dict[str, Any] | None) -> tuple[float | None, float | None]:
        """Extract centroid coordinates from GeoJSON geometry."""
        if not geometry:
            return None, None

        geom_type = geometry.get("type", "")
        coords = geometry.get("coordinates", [])

        try:
            if geom_type == "LineString" and coords:
                # Calculate centroid of LineString
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                return sum(lats) / len(lats), sum(lons) / len(lons)
            elif geom_type == "MultiLineString" and coords:
                # Flatten and calculate centroid
                all_coords = [c for line in coords for c in line]
                if all_coords:
                    lons = [c[0] for c in all_coords]
                    lats = [c[1] for c in all_coords]
                    return sum(lats) / len(lats), sum(lons) / len(lons)
            elif geom_type == "Point" and len(coords) >= 2:
                return coords[1], coords[0]
        except (IndexError, TypeError, ZeroDivisionError):
            pass

        return None, None

    async def async_geocode_address(
        self,
        address: str,
        limit: int = 5,
    ) -> list[GeocodedAddress]:
        """Geocode an address using Nominatim (OpenStreetMap).

        Args:
            address: The address string to geocode.
            limit: Maximum number of results.

        Returns:
            List of GeocodedAddress results.
        """
        # Add Montreal/Quebec context if not present
        address_lower = address.lower()
        if "montreal" not in address_lower and "montréal" not in address_lower:
            address = f"{address}, Montreal, Quebec, Canada"

        params = {
            "q": address,
            "format": "json",
            "addressdetails": "1",
            "limit": str(limit),
            **MONTREAL_BBOX,
        }

        headers = {
            "User-Agent": NOMINATIM_USER_AGENT,
            "Accept-Language": "en",
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Add small delay to respect Nominatim rate limits (1 req/sec)
                await asyncio.sleep(0.5)

                async with session.get(
                    NOMINATIM_URL,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 503:
                        _LOGGER.debug("Nominatim service temporarily unavailable, retrying...")
                        await asyncio.sleep(2)
                        async with session.get(
                            NOMINATIM_URL,
                            params=params,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as retry_response:
                            retry_response.raise_for_status()
                            data = await retry_response.json()
                    else:
                        response.raise_for_status()
                        data = await response.json()

            results = []
            for item in data:
                addr = item.get("address", {})
                results.append(GeocodedAddress(
                    display_name=item.get("display_name", ""),
                    lat=float(item.get("lat", 0)),
                    lon=float(item.get("lon", 0)),
                    house_number=addr.get("house_number"),
                    street=addr.get("road") or addr.get("street"),
                    city=addr.get("city") or addr.get("town") or addr.get("municipality"),
                    importance=float(item.get("importance", 0)),
                ))

            return results

        except aiohttp.ClientResponseError as err:
            _LOGGER.debug("Geocoding HTTP error: %s", err)
            return []
        except Exception as err:
            _LOGGER.debug("Geocoding failed: %s", err)
            return []

    def find_nearest_segments(
        self,
        lat: float,
        lon: float,
        street_name: str | None = None,
        civic_number: int | None = None,
        limit: int = 10,
    ) -> list[StreetSegment]:
        """Find street segments nearest to given coordinates.

        Args:
            lat: Latitude.
            lon: Longitude.
            street_name: Optional street name to filter by.
            civic_number: Optional civic number to filter by address range.
            limit: Maximum results to return.

        Returns:
            List of nearest StreetSegment objects, sorted by distance.
        """
        if not self._loaded:
            return []

        # Normalize street name if provided
        street_filter = None
        if street_name:
            street_filter = self._normalize_street_name(street_name.lower())

        results: list[tuple[float, StreetSegment]] = []

        for segment in self._streets:
            if segment.lat is None or segment.lon is None:
                continue

            # Filter by street name if provided
            if street_filter:
                segment_normalized = self._normalize_street_name(segment.street_name.lower())
                if street_filter not in segment_normalized and segment_normalized not in street_filter:
                    continue

            # Filter by civic number if provided
            if civic_number is not None:
                if segment.address_start and segment.address_end:
                    addr_min = min(segment.address_start, segment.address_end)
                    addr_max = max(segment.address_start, segment.address_end)
                    if not (addr_min <= civic_number <= addr_max):
                        continue
                elif segment.address_start:
                    if civic_number < segment.address_start:
                        continue

            # Calculate distance (simple Euclidean for small distances)
            distance = self._calculate_distance(lat, lon, segment.lat, segment.lon)
            results.append((distance, segment))

        # Sort by distance
        results.sort(key=lambda x: x[0])

        return [segment for _, segment in results[:limit]]

    @staticmethod
    def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate approximate distance between two coordinates in meters."""
        # Haversine formula simplified for small distances
        R = 6371000  # Earth radius in meters
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    async def async_search_by_postal_code(
        self,
        civic_number: int,
        postal_code: str,
        street_hint: str | None = None,
        limit: int = 10,
    ) -> list[StreetSegment]:
        """Search for street segments by civic number and postal code.

        Args:
            civic_number: The house/building number.
            postal_code: Canadian postal code (e.g., "H2X 1Y6").
            street_hint: Optional partial street name to filter results.
            limit: Maximum results to return.

        Returns:
            List of matching StreetSegment objects.
        """
        # Format postal code (ensure uppercase and proper spacing)
        postal_code = postal_code.upper().strip().replace(" ", "")
        postal_code_spaced = f"{postal_code[:3]} {postal_code[3:]}" if len(postal_code) == 6 else postal_code

        _LOGGER.debug("Searching by postal code: civic=%s, postal=%s", civic_number, postal_code_spaced)

        geocoded = []

        # Strategy 1: Search with civic number and postal code as address
        address = f"{civic_number} {postal_code_spaced}, Montreal, Quebec, Canada"
        geocoded = await self.async_geocode_address(address, limit=5)

        # Strategy 2: Try just postal code with Montreal
        if not geocoded:
            address = f"{postal_code_spaced}, Montreal, Quebec, Canada"
            geocoded = await self.async_geocode_address(address, limit=5)

        # Strategy 3: Try structured postal code search
        if not geocoded:
            geocoded = await self._geocode_postal_code(postal_code_spaced)

        # Strategy 4: Try FSA (first 3 characters) which is a larger area
        if not geocoded and len(postal_code) >= 3:
            fsa = postal_code[:3]
            address = f"{fsa}, Montreal, Quebec, Canada"
            geocoded = await self.async_geocode_address(address, limit=5)

        if not geocoded:
            _LOGGER.warning("No geocoding results for postal code: %s", postal_code_spaced)
            # Fallback: search by civic number range in geobase
            _LOGGER.debug("Falling back to civic number range search")
            return self._search_by_civic_number(civic_number, street_hint, limit)

        # Find nearest segments to geocoded location
        all_results = []
        for geo in geocoded:
            _LOGGER.debug(
                "Geocoded result: %s at (%s, %s), street=%s",
                geo.display_name, geo.lat, geo.lon, geo.street
            )

            # Search without strict filters - just find nearby segments
            segments = self.find_nearest_segments(
                lat=geo.lat,
                lon=geo.lon,
                street_name=None,
                civic_number=None,
                limit=limit * 2,  # Get more results to filter
            )
            for seg in segments:
                if seg not in all_results:
                    all_results.append(seg)

        # Sort by relevance - prefer segments where civic number is in range
        def sort_key(seg: StreetSegment) -> tuple:
            in_range = False
            distance_penalty = 0
            if seg.address_start and seg.address_end:
                addr_min = min(seg.address_start, seg.address_end)
                addr_max = max(seg.address_start, seg.address_end)
                in_range = addr_min <= civic_number <= addr_max
                # Also consider how close the civic number is to the range
                if not in_range:
                    distance_penalty = min(
                        abs(civic_number - addr_min),
                        abs(civic_number - addr_max)
                    )
            return (not in_range, distance_penalty, seg.street_name)

        all_results.sort(key=sort_key)

        return all_results[:limit]

    def _search_by_civic_number(
        self,
        civic_number: int,
        street_hint: str | None = None,
        limit: int = 15,
    ) -> list[StreetSegment]:
        """Search for street segments that contain the given civic number in their range.

        This is a fallback when geocoding fails.
        """
        if not self._loaded:
            return []

        # Normalize street hint for matching
        hint_normalized = None
        if street_hint:
            hint_normalized = self._normalize_street_name(street_hint.lower())

        results = []
        for segment in self._streets:
            # Filter by street name hint if provided
            if hint_normalized:
                segment_normalized = self._normalize_street_name(segment.street_name.lower())
                if hint_normalized not in segment_normalized:
                    continue

            # Check civic number range
            if segment.address_start and segment.address_end:
                addr_min = min(segment.address_start, segment.address_end)
                addr_max = max(segment.address_start, segment.address_end)
                if addr_min <= civic_number <= addr_max:
                    results.append(segment)

        # Sort by street name for easier browsing
        results.sort(key=lambda s: (s.street_name, s.address_start or 0))

        _LOGGER.debug(
            "Civic number search found %d segments for %d (hint: %s)",
            len(results), civic_number, street_hint
        )
        return results[:limit]

    async def _geocode_postal_code(self, postal_code: str) -> list[GeocodedAddress]:
        """Geocode using postal code with Nominatim."""
        params = {
            "postalcode": postal_code,
            "country": "Canada",
            "format": "json",
            "addressdetails": "1",
            "limit": "5",
            **MONTREAL_BBOX,
        }

        headers = {
            "User-Agent": NOMINATIM_USER_AGENT,
            "Accept-Language": "en",
        }

        try:
            async with aiohttp.ClientSession() as session:
                await asyncio.sleep(0.5)  # Rate limit

                async with session.get(
                    NOMINATIM_URL,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as response:
                    if response.status == 503:
                        await asyncio.sleep(2)
                        async with session.get(
                            NOMINATIM_URL,
                            params=params,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as retry_response:
                            retry_response.raise_for_status()
                            data = await retry_response.json()
                    else:
                        response.raise_for_status()
                        data = await response.json()

            results = []
            for item in data:
                addr = item.get("address", {})
                results.append(GeocodedAddress(
                    display_name=item.get("display_name", ""),
                    lat=float(item.get("lat", 0)),
                    lon=float(item.get("lon", 0)),
                    house_number=addr.get("house_number"),
                    street=addr.get("road") or addr.get("street"),
                    city=addr.get("city") or addr.get("town") or addr.get("municipality"),
                    importance=float(item.get("importance", 0)),
                ))

            _LOGGER.debug("Nominatim postal code search returned %d results", len(results))
            return results

        except Exception as err:
            _LOGGER.debug("Nominatim postal code geocoding failed: %s", err)
            return []

    async def async_search_by_full_address(
        self,
        address: str,
        limit: int = 10,
    ) -> list[StreetSegment]:
        """Search for street segments by full address using geocoding.

        Args:
            address: Full address string (e.g., "1234 Saint-Denis, Montreal").
            limit: Maximum results to return.

        Returns:
            List of matching StreetSegment objects.
        """
        # First, try to geocode the address
        geocoded = await self.async_geocode_address(address, limit=3)

        if not geocoded:
            # Fallback to text search
            # Try to parse civic number and street from address
            civic_number, street_name = self._parse_address(address)
            if street_name:
                return self.search(street_name, civic_number=civic_number, limit=limit)
            return []

        # Find nearest segments to geocoded location
        all_results = []
        for geo in geocoded:
            segments = self.find_nearest_segments(
                lat=geo.lat,
                lon=geo.lon,
                street_name=geo.street,
                civic_number=int(geo.house_number) if geo.house_number and geo.house_number.isdigit() else None,
                limit=limit,
            )
            for seg in segments:
                if seg not in all_results:
                    all_results.append(seg)

        return all_results[:limit]

    def _parse_address(self, address: str) -> tuple[int | None, str | None]:
        """Parse civic number and street name from address string."""
        # Try to match patterns like "1234 Street Name" or "1234, Street Name"
        match = re.match(r"^\s*(\d+)\s*[,\s]+(.+?)(?:,|$)", address)
        if match:
            return int(match.group(1)), match.group(2).strip()

        # No civic number found, return just the street
        # Remove common suffixes
        cleaned = re.sub(r",?\s*(montreal|montréal|qc|quebec|québec|canada).*$", "", address, flags=re.IGNORECASE)
        return None, cleaned.strip() if cleaned.strip() else None

    def search(
        self,
        query: str,
        civic_number: int | None = None,
        limit: int = 20,
    ) -> list[StreetSegment]:
        """Search for streets matching the query.

        Args:
            query: Street name to search for.
            civic_number: Optional civic number to filter by address range.
            limit: Maximum number of results to return.

        Returns:
            List of matching StreetSegment objects.
        """
        if not self._loaded:
            return []

        query_lower = query.lower().strip()
        if not query_lower:
            return []

        # Normalize common abbreviations
        query_normalized = self._normalize_street_name(query_lower)

        results: list[tuple[int, StreetSegment]] = []

        for segment in self._streets:
            street_lower = segment.street_name.lower()
            street_normalized = self._normalize_street_name(street_lower)

            # Calculate match score
            score = 0

            # Exact match
            if street_normalized == query_normalized:
                score = 100
            # Starts with query
            elif street_normalized.startswith(query_normalized):
                score = 80
            # Contains query as a word
            elif query_normalized in street_normalized.split():
                score = 60
            # Contains query
            elif query_normalized in street_normalized:
                score = 40
            else:
                continue

            # Filter by civic number if provided
            if civic_number is not None:
                if segment.address_start and segment.address_end:
                    addr_min = min(segment.address_start, segment.address_end)
                    addr_max = max(segment.address_start, segment.address_end)
                    if addr_min <= civic_number <= addr_max:
                        score += 20  # Bonus for matching address range
                    else:
                        continue  # Skip if not in range
                elif segment.address_start:
                    if civic_number < segment.address_start:
                        continue

            results.append((score, segment))

        # Sort by score (descending), then by street name
        results.sort(key=lambda x: (-x[0], x[1].street_name, x[1].address_start or 0))

        return [segment for _, segment in results[:limit]]

    def search_by_address(
        self,
        civic_number: int,
        street_name: str,
        limit: int = 10,
    ) -> list[StreetSegment]:
        """Search for a specific address.

        Args:
            civic_number: The civic/house number.
            street_name: The street name.
            limit: Maximum results to return.

        Returns:
            List of matching StreetSegment objects.
        """
        return self.search(street_name, civic_number=civic_number, limit=limit)

    def get_by_id(self, cote_rue_id: int) -> StreetSegment | None:
        """Get a street segment by its ID.

        Args:
            cote_rue_id: The street segment ID.

        Returns:
            The StreetSegment or None if not found.
        """
        for segment in self._streets:
            if segment.cote_rue_id == cote_rue_id:
                return segment
        return None

    @staticmethod
    def _normalize_street_name(name: str) -> str:
        """Normalize street name for better matching."""
        # Common French abbreviations
        replacements = {
            "st-": "saint-",
            "st ": "saint ",
            "ste-": "sainte-",
            "ste ": "sainte ",
            "av.": "avenue",
            "av ": "avenue ",
            "boul.": "boulevard",
            "boul ": "boulevard ",
            "blvd": "boulevard",
            "ch.": "chemin",
            "ch ": "chemin ",
            "pl.": "place",
            "pl ": "place ",
            "rue ": "",  # Remove "rue" prefix
        }

        result = name.lower()
        for abbr, full in replacements.items():
            result = result.replace(abbr, full)

        return result.strip()

    @property
    def is_loaded(self) -> bool:
        """Return True if data is loaded."""
        return self._loaded

    @property
    def street_count(self) -> int:
        """Return the number of loaded street segments."""
        return len(self._streets)


# Singleton instance for shared use
_street_lookup: StreetLookup | None = None


async def get_street_lookup(cache_dir: Path | None = None) -> StreetLookup:
    """Get the shared StreetLookup instance.

    Args:
        cache_dir: Cache directory (only used on first call).

    Returns:
        The shared StreetLookup instance.
    """
    global _street_lookup
    if _street_lookup is None:
        _street_lookup = StreetLookup(cache_dir)
    return _street_lookup
