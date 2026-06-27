"""Constants for the O Spa Heat Pump integration."""
from __future__ import annotations

DOMAIN = "ospa_heatpump"
CONF_URL = "url"
DEFAULT_URL = "http://localhost:8883"
DEFAULT_SCAN_INTERVAL = 15  # seconds

# Tuya DP IDs (as strings, matching the bridge dp_map keys)
DP_POWER = "1"
DP_MODE = "2"
DP_TARGET_TEMP = "4"
DP_ELEC_HEAT = "32"

# Scale factor for temperature DPs (device sends °C × 10)
TEMP_SCALE = 10

# Mode strings used by this device — adjust here if yours differ.
# Common alternatives: "warm"/"cold", "0"/"1", or integer 0/1.
TUYA_MODE_HEATING = "heating"
TUYA_MODE_COOLING = "cooling"
