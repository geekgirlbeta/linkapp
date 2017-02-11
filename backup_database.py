#!/usr/bin/env python
"""
Script to backup the database as a JSON file.

File contains single list of links stored as a dictionary.
"""

import edit
import json

lm = edit.LinkManager()
lm.listing()

with open("data_backup.json", "w") as backup:
    json.dump(lm.listing(), backup)