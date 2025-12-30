from time import strftime
from os.path import realpath
from os import listdir
import csv

class Termometr:
    __MAX_RECORDS_COUNT = 1440
    __RECORDS_FIELDNAMES = ("name", "temperature", "humidity", "timestamp")

    def __init__(self, id, name="", humidity=0.0, temperature=0.0):
        self.id = id
        self.name = name
        self.temperature = temperature
        self.humidity = humidity
        self.records = []

    def add_record(self):
        record = {
            "name": self.name,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "timestamp": strftime("%d-%m-%y %H:%M:%S")
        }

        self.records.append(record)
        if len(self.records) > self.__MAX_RECORDS_COUNT:
            self.records.pop(0)  # Remove oldest record to maintain size limit

    def update(self, temperature, humidity, name):
        self.temperature = temperature
        self.humidity = humidity
        self.name = name

        self.add_record()

    def __get_records_file_name(self, records_directory_path):
        return f"{realpath(records_directory_path)}/{str(self.id)}.csv"

    def save_records(self, records_directory_path):
        with open(self.__get_records_file_name(records_directory_path), "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.__RECORDS_FIELDNAMES)
            writer.writeheader()
            for record in self.records:
                writer.writerow(record)

    def load(self, records_directory_path):
        try:
            with open(self.__get_records_file_name(records_directory_path), "r", newline="") as csvfile:
                reader = csv.DictReader(csvfile, fieldnames=self.__RECORDS_FIELDNAMES)
                self.records = [row for row in reader]

                for item in reader:
                    record = {
                        "name"        : str(item["name"]),
                        "temperature" : float(item["temperature"]),
                        "humidity"    : float(item["humidity"]),
                        "timestamp"   : str(item["timestamp"])
                    }
                    self.records.append(record)

                last_record = self.records[-1]
                self.name = last_record["name"]
                self.temperature = last_record["temperature"]
                self.humidity = last_record["humidity"]
        except FileNotFoundError:
            self.records = []

class TermometerHandler():

    def __init__(self, records_directory_path):
        self.__termometr_list = []
        self.__records_directory_path = realpath(records_directory_path)

    def load_all_termometrs(self):
        self.__termometr_list = [Termometr(file[:-4]) for file in listdir(self.__records_directory_path) if file.endswith('.csv')]

        for termometr in self.__termometr_list:
            termometr.load(self.__records_directory_path)

    def find_termometr_by_id(self, termometr_id):
        for termometr in self.__termometr_list:
            if termometr.id == termometr_id:
                return termometr
        return None

    def add_termometr(self, termometr):
        self.__termometr_list.append(termometr)
        self.__termometr_list[-1].add_record()
        self.__termometr_list[-1].save_records()

    def update_termometr(self, termometr_id, temperature, humidity, name):
        termometr = self.find_termometr_by_id(termometr_id)
        if termometr:
            termometr.update(temperature, humidity, name)
            termometr.save_records(self.__records_directory_path)

    def get_all_termometrs(self):
        return self.__termometr_list.copy()
