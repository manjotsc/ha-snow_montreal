"""Constants for the Montreal Snow Removal integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "snow_montreal"

# API Configuration
WSDL_URL: Final = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/InfoneigeWebService?WSDL"
WSDL_URL_SIM: Final = "https://servicesenligne2.ville.montreal.qc.ca/api/infoneige/sim/InfoneigeWebService?wsdl"

# Config keys
CONF_API_TOKEN: Final = "api_token"
CONF_STREETS: Final = "streets"
CONF_STREET_ID: Final = "street_id"
CONF_STREET_NAME: Final = "street_name"
CONF_USE_SIMULATION: Final = "use_simulation"

# Update interval in seconds (5 minutes)
UPDATE_INTERVAL: Final = 300

# Snow removal states
STATE_UNKNOWN: Final = 0
STATE_SCHEDULED: Final = 1
STATE_IN_PROGRESS: Final = 2
STATE_COMPLETED: Final = 3
STATE_CANCELLED: Final = 4

# State mappings (etatDeneig values from API)
SNOW_STATE_MAP: Final = {
    0: "unknown",
    1: "scheduled",
    2: "in_progress",
    3: "completed",
    4: "cancelled",
    5: "pending",
    6: "replanned",
}

# French/English status labels from API
STATE_LABELS: Final = {
    "en": {
        0: "Unknown",
        1: "Scheduled",
        2: "In Progress",
        3: "Completed",
        4: "Cancelled",
        5: "Pending",
        6: "Replanned",
    },
    "fr": {
        0: "Inconnu",
        1: "Planifié",
        2: "En cours",
        3: "Terminé",
        4: "Annulé",
        5: "En attente",
        6: "Replanifié",
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
