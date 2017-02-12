#!/usr/bin/env python
"""
Script to backup the database as a JSON file.

File contains single list of links stored as a dictionary.
"""

import edit
import json
import user

lm = edit.LinkManager()
um = user.UserManager()

with open("data_backup.json", "w") as backup:
    export = {"users":um.listing(), "links":lm.listing()}
    json.dump(export, backup)
    
