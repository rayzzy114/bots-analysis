# BULBA Bot Tests

## Running Tests

```bash
# Install test dependencies
pip install -r tests/test_requirements.txt

# Run tests
python -m pytest tests/ -v

# Or use the main test runner
python ../../run_tests.py
```

## Test Structure

- `test_rates.py` - Tests for CoinGecko rate fetching
- `test_integration.py` - Integration tests for handlers
- `conftest.py` - Pytest configuration

## What is Tested

1. **CoinGecko Rate Fetching**
   - Rates are fetched from CoinGecko API
   - Fallback to env values when API fails
   - Rates are positive numbers

2. **Dynamic Commission**
   - Commission read from environment
   - Calculation uses dynamic value, not hardcoded

3. **Handler Integration**
   - Handlers use dynamic rate functions
   - No hardcoded values in critical paths
