import sqlite3

"""
database structure:

user_id: int
name: char
program: char

"""


class BotDatabase:
    def __init__(self, database_name: str):
        self.conn = sqlite3.connect(database_name)
        self.cur = self.conn.cursor()

    def check_user(self, user_id: int) -> bool:
        if user_id:
            return True
        return False

    def add_user(self, user_id: int, name: str):
        pass

    def insert(self, program: str):
        pass

    def edit(self, program: str):
        pass

    def close_conn(self):
        self.conn.close()
