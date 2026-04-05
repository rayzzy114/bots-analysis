import os
import sqlite3
import tempfile
import unittest

from db.init_db import init_db
from db.settings import get_commission, update_commission


class TestDbCommissionIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self._temp_dir.name)

    async def asyncTearDown(self) -> None:
        os.chdir(self._original_cwd)
        self._temp_dir.cleanup()

    async def test_init_db_adds_commission_column_and_default(self) -> None:
        await init_db()

        conn = sqlite3.connect("users.db")
        try:
            columns = conn.execute("PRAGMA table_info(settings)").fetchall()
            names = {row[1] for row in columns}
            self.assertIn("commission", names)

            commission = conn.execute("SELECT commission FROM settings WHERE id = 1").fetchone()[0]
            self.assertIsInstance(commission, float)
            self.assertGreaterEqual(commission, 0)
        finally:
            conn.close()

    async def test_update_and_get_commission_roundtrip(self) -> None:
        await init_db()

        await update_commission(3.5)
        commission = await get_commission()

        self.assertEqual(commission, 3.5)
