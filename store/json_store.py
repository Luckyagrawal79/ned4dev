import json
from collections import defaultdict

class JSONMetricStore:
    def __init__(self, path="data/data_store.json"):
        self.path = path

    def load(self):
        with open(self.path, "r") as f:
            return json.load(f)

    def group_by_week(self):
        data = self.load()
        grouped = defaultdict(list)
        for row in data:
            grouped[row["week"]].append(row)
        return dict(grouped)

    def get_week(self, week):
        return self.group_by_week().get(week, [])
