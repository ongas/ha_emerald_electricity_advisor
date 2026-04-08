"""Constants for Emerald Electricity Advisor integration."""

DOMAIN = "emerald_electricity_advisor"
ATTR_DEVICE_ID = "device_id"
ATTR_DEVICE_MAC = "device_mac"
ATTR_DEVICE_MODEL = "device_model"
ATTR_IMPULSE_RATE = "impulse_rate"

# Emerald API
EMERALD_API_BASE = "https://api.emerald-ems.com.au/api/v1"
EMERALD_SIGN_IN = f"{EMERALD_API_BASE}/customer/sign-in"
EMERALD_TOKEN_REFRESH = f"{EMERALD_API_BASE}/customer/token-refresh"
EMERALD_PROPERTY_LIST = f"{EMERALD_API_BASE}/customer/property/list"
EMERALD_DEVICE_DATA = f"{EMERALD_API_BASE}/customer/device/get-by-date/flashes-data"

# Default update interval (seconds)
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes for API polling

# Sensor suffixes
SENSOR_DAILY_ENERGY = "daily_energy"
SENSOR_CURRENT_HOUR = "current_hour_energy"
SENSOR_LAST_10MIN = "last_10min_energy"
SENSOR_DAILY_COST = "daily_cost"
SENSOR_POWER = "current_power"
SENSOR_LAST_UPDATE = "last_update"

# Device info
ATTR_SERIAL = "serial_number"
ATTR_FIRMWARE = "firmware_version"
ATTR_NMI = "nmi"
