import logging
import warnings
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, CONF_HOST, CONF_TOKEN, DATA_DEVICE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["media_player"]

# ---------------------------------------------------------------------------
# 1) Warning filtering (solo ciò che serve)
# ---------------------------------------------------------------------------
warnings.filterwarnings("ignore", category=FutureWarning, module="miio")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="miio")

# ---------------------------------------------------------------------------
# 2) Lazy import python-miio
# ---------------------------------------------------------------------------
try:
    from miio import Device, DeviceException  # type: ignore
    import miio.protocol
except ImportError:
    Device = None
    DeviceException = None
    miio = None

# ---------------------------------------------------------------------------
# 3) Patch per Python 3.13 (DeprecationWarning su utcfromtimestamp)
# ---------------------------------------------------------------------------
if miio:
    import datetime

    def _fixed_utcfromtimestamp(ts):
        return datetime.datetime.fromtimestamp(ts, datetime.UTC)

    # Sostituisce la funzione interna usata da python-miio
    miio.protocol.utcfromtimestamp = _fixed_utcfromtimestamp
    _LOGGER.debug("Applied python-miio timestamp patch for Python 3.13")

# ---------------------------------------------------------------------------
# 4) Setup YAML (non usato, ma richiesto da HA)
# ---------------------------------------------------------------------------
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True

# ---------------------------------------------------------------------------
# 5) Setup Config Entry
# ---------------------------------------------------------------------------
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xiaomi Gateway Radio from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if Device is None:
        _LOGGER.error("python-miio not available")
        return False

    host: str = entry.data[CONF_HOST]
    token: str = entry.data[CONF_TOKEN]

    async def _create_device():
        def _sync_create():
            dev = Device(host, token)
            info = dev.info()
            return dev, info

        return await hass.async_add_executor_job(_sync_create)

    try:
        device, info = await _create_device()
    except DeviceException as err:  # type: ignore
        _LOGGER.error(
            "Unable to connect to Xiaomi Gateway Radio at %s: %s", host, err
        )
        raise UpdateFailed from err

    _LOGGER.info(
        "Connected to Xiaomi Gateway Radio %s (fw: %s, hw: %s)",
        info.model,
        info.firmware_version,
        info.hardware_version,
    )

    async def _async_update_data():
        """Coordinator fetch (entity gestisce il polling)."""
        return True

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{host}",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=60),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_DEVICE: device,
        "info": info,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

# ---------------------------------------------------------------------------
# 6) Unload
# ---------------------------------------------------------------------------
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok

# ---------------------------------------------------------------------------
# 7) Options Flow
# ---------------------------------------------------------------------------
async def async_get_options_flow(config_entry):
    from .options_flow import OptionsFlowHandler
    return OptionsFlowHandler(config_entry)