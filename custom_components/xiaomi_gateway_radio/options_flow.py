import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Xiaomi Gateway Radio."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Salva le nuove opzioni
            return self.async_create_entry(title="", data=user_input)

        # Schema delle opzioni disponibili
        data_schema = vol.Schema({
            vol.Optional(
                "volume_step",
                default=self.config_entry.data.get("volume_step", 5)
            ): int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema
        )