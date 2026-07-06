from homeassistant.core import HomeAssistant

from custom_components.transperth.api import async_shared_client


async def test_shared_client_is_reused(hass: HomeAssistant) -> None:
    assert async_shared_client(hass) is async_shared_client(hass)
