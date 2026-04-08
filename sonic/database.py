import sqlite3 as sq


class DataBase:
    def __init__(self, db_file):
        self.connection = sq.connect(db_file, check_same_thread=False)
        self.cur = self.connection.cursor()

    def db_settings(self):
        with self.connection:
            self.cur.execute("CREATE TABLE IF NOT EXISTS setting("
                             "KARTA TEXT,"
                             "SBP TEXT)")
            # Check if settings already exist
            self.cur.execute("SELECT COUNT(*) FROM setting")
            if self.cur.fetchone()[0] == 0:
                self.cur.execute('INSERT INTO setting (KARTA, SBP) VALUES ("0000 0000 0000 0000", "790050076543 (Тинькофф)")')




    def get_karta(self):
        with self.connection:
            return self.cur.execute('SELECT KARTA from setting').fetchone()[0]

    def update_karta(self, card):
        with self.connection:
            return self.cur.execute('UPDATE setting SET KARTA = ?', (card,))


    def get_sbp(self):
        with self.connection:
            return self.cur.execute('SELECT SBP from setting').fetchone()[0]

    def update_sbp(self, number):
        with self.connection:
            return self.cur.execute('UPDATE setting SET SBP = ?', (number,))
