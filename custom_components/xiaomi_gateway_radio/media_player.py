import logging
from functools import partial

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, DATA_DEVICE, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

SUPPORT_XIAOMI_GATEWAY_FM = (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.NEXT_TRACK
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up media player from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    device = data[DATA_DEVICE]
    info = data["info"]

    name = entry.data.get("name", DEFAULT_NAME)

    entity = XiaomiGatewayRadioMediaPlayer(
        hass=hass,
        device=device,
        name=name,
        model=info.model,
        firmware=info.firmware_version,
        hardware=info.hardware_version,
        unique_id=f"{info.model}-{info.mac_address}-fm",
    )

    async_add_entities([entity])


class XiaomiGatewayRadioMediaPlayer(MediaPlayerEntity):
    """Representation of the Xiaomi Gateway Radio."""

    _attr_supported_features = SUPPORT_XIAOMI_GATEWAY_FM

    def __init__(
        self,
        hass: HomeAssistant,
        device,
        name: str,
        model: str,
        firmware: str,
        hardware: str,
        unique_id: str,
    ) -> None:
        self.hass = hass
        self._device = device
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._model = model
        self._firmware = firmware
        self._hardware = hardware

        self._attr_icon = "mdi:radio"
        self._attr_available = True
        self._attr_state = None
        self._muted = False
        self._volume = 0.0

    @property
    def extra_state_attributes(self):
        return {
            "model": self._model,
            "firmware_version": self._firmware,
            "hardware_version": self._hardware,
            "muted": self._muted,
        }

    async def _async_try_command(self, mask_error: str, func, *args, **kwargs) -> bool:
        from miio import DeviceException  # type: ignore

        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )
            _LOGGER.debug("Response from Xiaomi Gateway Radio: %s", result)
            return True
        except DeviceException as exc:  # type: ignore
            _LOGGER.error("%s: %s", mask_error, exc)
            self._attr_available = False
            return False

    async def async_turn_off(self) -> None:
        await self._async_try_command(
            "Turning the Gateway off failed", self._device.send, "play_fm", ["off"]
        )
        self._attr_state = STATE_OFF
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        await self._async_try_command(
            "Turning the Gateway on failed", self._device.send, "play_fm", ["on"]
        )
        self._attr_state = STATE_ON
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        volume = round(self._volume * 100) + 1
        await self._async_try_command(
            "Increasing volume failed", self._device.send, "set_fm_volume", [volume]
        )

    async def async_volume_down(self) -> None:
        volume = max(0, round(self._volume * 100) - 1)
        await self._async_try_command(
            "Decreasing volume failed", self._device.send, "set_fm_volume", [volume]
        )

    async def async_set_volume_level(self, volume: float) -> None:
        volset = max(0, min(100, round(volume * 100)))
        await self._async_try_command(
            "Setting volume failed", self._device.send, "set_fm_volume", [volset]
        )

    async def async_mute_volume(self, mute: bool) -> None:
        volume = 0 if mute else 10
        ok = await self._async_try_command(
            "Muting volume failed", self._device.send, "set_fm_volume", [volume]
        )
        if ok:
            self._muted = mute
            self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        await self._async_try_command(
            "Next track failed", self._device.send, "play_fm", ["next"]
        )

    async def async_update(self) -> None:
        """Fetch state from the gateway."""
        from miio import DeviceException  # type: ignore

        try:
            def _sync_state():
                return self._device.send("get_prop_fm", "")

            state = await self.hass.async_add_executor_job(_sync_state)

            _LOGGER.debug("Got new state from Xiaomi Gateway Radio: %s", state)

            volume = state.pop("current_volume", None)
            status = state.pop("current_status", None)

            if volume is not None:
                self._volume = volume / 100
                self._muted = volume == 0

            if status == "pause":
                self._attr_state = STATE_OFF
            elif status == "run":
                self._attr_state = STATE_ON
            else:
                _LOGGER.warning("Unexpected state from gateway: %s", status)
                self._attr_state = None

            self._attr_available = True

        except DeviceException as ex:  # type: ignore
            self._attr_available = False
            _LOGGER.error("Error while fetching state from Xiaomi Gateway Radio: %s", ex)
