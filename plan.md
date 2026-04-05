# Plan

1. Remove synchronous `requests.get` from async functions in `VortexExchange/utils/valute.py`, `sonic/func.py`, and other similar locations. Replace them with `aiohttp` to fix async/await broken patterns.
2. Search and fix deadlocks/race conditions by migrating raw `sqlite3` to `aiosqlite` or wrapping db calls in threads where `await` is expected (or fix `sqlite3` accesses inside `async` def).
3. Check and fix missing API response status checks (incorrect handling of API responses) where `requests.get` or `aiohttp` session returns a response that's not `200 OK` or missing keys in JSON (like `['price']`).
4. Find and remove silent failures in `try: ... except: pass` blocks. Replace with proper logging or error handling, particularly in payment flow / API handlers.
5. Identify and remove backdoors / suspicious logic in `dev.py` and `dev_run.py` (e.g. `subprocess.Popen` logic that executes unknown commands or payload from `sys.executable`).

