import pytest
import httpx
from unittest.mock import AsyncMock, patch
from bot.handlers.exchange import fetch_coingecko_rate
from core.config import Config

@pytest.mark.asyncio
async def test_fetch_coingecko_rate_success():
    mock_data = {"bitcoin": {"rub": 5000000.0}}
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_data
        
        rate = await fetch_coingecko_rate("btc")
        assert rate == 5000000.0
        mock_get.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_coingecko_rate_failure():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPError("API Down")
        
        rate = await fetch_coingecko_rate("btc")
        assert rate is None
