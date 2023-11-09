import sqlite3


class BotDatabase:
    def __init__(self, database_name: str):
        self.conn = sqlite3.connect(database_name, check_same_thread=False)
        self.cur = self.conn.cursor()

    def check_user(self, user_id: int) -> bool:
        result = self.cur.execute("SELECT `id` FROM `users` WHERE `user_id` = ?", (user_id,))
        return bool(len(result.fetchall()))

    def add_user(self, user_id: int):
        self.cur.execute("INSERT INTO `users` (`user_id`) VALUES (?)", (user_id,))
        return self.conn.commit()

    def get_user_id(self, user_id: int):
        res = self.cur.execute("SELECT `id` FROM `users` WHERE `user_id` = ?", (user_id,))
        return res.fetchone()[0]

    def insert(self, user_id: int, program: list):
        pass
        # i = 1
        # for idx, ex in enumerate(program):
        #     self.cur.execute(f"UPDATE users SET `ex{i}` = ? WHERE user_id = ?", (ex, user_id))
        #     i += 1
        # return self.conn.commit()


    def update(self, user_id: int, new_program: str):
        pass

    def get_exercises(self, user_id: int):
        exs = []
        result = self.cur.execute(f"SELECT * FROM `users` WHERE `user_id` = ?", (user_id,))

        for obj in result.fetchall():
            for j in range(3, len(obj) - 1):
                if not obj[j] is None:
                    exs.append(obj[j])
        return exs

    def insert_feedback(self, user_id: int, feedback: str):
        self.cur.execute("UPDATE users SET feedback = ? WHERE user_id = ?", (feedback, user_id,))
        return self.conn.commit()

    def get_actual_columns(self):
        self.cur.execute("PRAGMA table_info(users)")
        columns = self.cur.fetchall()
        column_names = [column[1] for column in columns]
        return column_names

    def insert_schedule(self, user_id: int, schedule: dict):
        column_names = self.get_actual_columns()

        for weekday in schedule["schedule"]:
            if weekday['dayOfWeek'] not in column_names:
                self.cur.execute("ALTER TABLE users ADD COLUMN '%s' 'string'" % weekday['dayOfWeek'])
            self.cur.execute(f"UPDATE users SET `{weekday['dayOfWeek']}` = ? WHERE user_id = ?", (weekday['time'], user_id))

        return self.conn.commit()

    def insert_user_form(self, user_id: int, form: dict):
        column_names = self.get_actual_columns()

        for key, val in form['profile'].items():
            if key not in column_names:
                self.cur.execute("ALTER TABLE users ADD COLUMN '%s' 'string'" % key)
            self.cur.execute(f"UPDATE users SET `{key}` = ? WHERE user_id = ?", (val, user_id))
        return self.conn.commit()


    def close_conn(self):
        self.conn.close()

