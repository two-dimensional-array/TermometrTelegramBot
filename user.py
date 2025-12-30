import csv
from os.path import realpath

class UserStorage:
    __RECORDS_FIELDNAMES = ("user_id", "last_msg_id", "chat_id")

    def __init__(self, user_storage_file_path: str):
        self.user_storage_file_path = realpath(user_storage_file_path)
        self.user_data = []

    def load_users(self):
        try:
            with open(self.user_storage_file_path, "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=self.__RECORDS_FIELDNAMES)
                self.user_data = [row for row in reader]
        except FileNotFoundError:
            self.records = []

    def find_user_by_id(self, id: str):
        for user in self.user_data:
            if user["user_id"] == id:
                return user
        return None

    def add_user(self, id: str):
        if self.find_user_by_id(id) is None:
            user_record = {
                "user_id" : id,
                "last_msg_id" : None,
                "chat_id" : None
            }
            self.user_data.append(user_record)

    def set_last_msg_id(self, id: str, msg_id: str, chat_id: str):
        user = self.find_user_by_id(id)
        if user is not None:
            user["last_msg_id"] = msg_id
            user["chat_id"] = chat_id

    def save_user_data(self):
        with open(self.user_storage_file_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.__RECORDS_FIELDNAMES)
            writer.writeheader()
            writer.writerows(self.user_data)
