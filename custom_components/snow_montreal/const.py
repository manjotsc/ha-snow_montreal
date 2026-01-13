"""Constants for the Montreal Snow Removal integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "snow_montreal"

# Public API Configuration (no token required)
PUBLIC_API_DATA_URL: Final = "https://raw.githubusercontent.com/ludodefgh/planif-neige-public-api/main/data/planif-neige.json"
PUBLIC_API_METADATA_URL: Final = "https://raw.githubusercontent.com/ludodefgh/planif-neige-public-api/main/data/planif-neige-metadata.json"
PUBLIC_API_GEOBASE_URL: Final = "https://raw.githubusercontent.com/ludodefgh/planif-neige-public-api/main/data/geobase-map.json"

# Config keys
CONF_STREET_ID: Final = "street_id"
CONF_STREET_NAME: Final = "street_name"

# Update interval in seconds (10 minutes - matches public API update frequency)
UPDATE_INTERVAL: Final = 600

# Snow removal states (Public API status codes)
STATE_SNOWED: Final = 0  # Not yet cleared
STATE_CLEARED: Final = 1  # Loading complete
STATE_SCHEDULED: Final = 2  # Clearance planned
STATE_RESCHEDULED: Final = 3  # Rescheduled to new date
STATE_DEFERRED: Final = 4  # Deferred, date TBD
STATE_IN_PROGRESS: Final = 5  # Currently clearing
STATE_CLEAR: Final = 10  # Between operations

# State mappings (Public API status codes)
SNOW_STATE_MAP: Final = {
    0: "snowed",
    1: "cleared",
    2: "scheduled",
    3: "rescheduled",
    4: "deferred",
    5: "in_progress",
    10: "clear",
}

# French/English status labels (Public API status codes)
STATE_LABELS: Final = {
    "en": {
        0: "Snowed",
        1: "Cleared",
        2: "Scheduled",
        3: "Rescheduled",
        4: "Deferred",
        5: "In Progress",
        10: "Clear",
    },
    "fr": {
        0: "Enneigé",
        1: "Déneigé",
        2: "Planifié",
        3: "Replanifié",
        4: "Sera replanifié",
        5: "En cours",
        10: "Dégagé",
    },
}

# Montreal boroughs
BOROUGHS: Final = {
    "AHU": "Ahuntsic-Cartierville",
    "ANJ": "Anjou",
    "CDN": "Côte-des-Neiges–Notre-Dame-de-Grâce",
    "LAC": "Lachine",
    "LAS": "LaSalle",
    "PLA": "Le Plateau-Mont-Royal",
    "LSO": "Le Sud-Ouest",
    "MHM": "Mercier–Hochelaga-Maisonneuve",
    "MTN": "Montréal-Nord",
    "OUT": "Outremont",
    "PRF": "Pierrefonds-Roxboro",
    "RDP": "Rivière-des-Prairies–Pointe-aux-Trembles",
    "RPP": "Rosemont–La Petite-Patrie",
    "VSL": "Saint-Laurent",
    "STL": "Saint-Léonard",
    "VER": "Verdun",
    "VIM": "Ville-Marie",
    "VSE": "Villeray–Saint-Michel–Parc-Extension",
}

ATTRIBUTION: Final = "Data provided by City of Montreal - Planif-Neige"
