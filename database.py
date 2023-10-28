import sqlite3

"""
database structure:

user_id: int
name: char
program: char

"""


class BotDatabase:
    def __init__(self, database_name: str):
        self.conn = sqlite3.connect(database_name, check_same_thread=False)
        self.cur = self.conn.cursor()

    def check_user(self, user_id: int) -> bool:
        result = self.cur.execute("SELECT `id` FROM `users` WHERE `user_id` = ?", (user_id,))
        return bool(len(result.fetchall()))

    def add_user(self, user_id: int, name: str):
        self.cur.execute("INSERT INTO `users` (`user_id`, `name`) VALUES (?, ?)", (user_id, name,))
        return self.conn.commit()

    def get_user_id(self, user_id: int):
        res = self.cur.execute("SELECT `id` FROM `users` WHERE `user_id` = ?", (user_id,))
        return res.fetchone()[0]

    def insert(self, user_id: int, program: str):
        self.cur.execute("UPDATE users SET `program` = ? WHERE user_id = ?", (program, user_id))
        return self.conn.commit()

    def update(self, user_id: int, new_program: str):
        pass

    def close_conn(self):
        self.conn.close()

