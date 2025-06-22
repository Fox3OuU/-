# Contents of /image-matcher-app/image-matcher-app/src/utils/config.py

import json
import os

class Config:
    def __init__(self, config_file='config/settings.json'):
        self.config_file = config_file
        self.settings = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        with open(self.config_file, 'r') as file:
            return json.load(file)

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.save_config()

    def save_config(self):
        with open(self.config_file, 'w') as file:
            json.dump(self.settings, file, indent=4)