#!/usr/bin/env python

import edit
import json
import user
from datetime import datetime

lm = edit.LinkManager()
um = user.UserManager()

with open("data_backup.json", "r") as backup:
    data = json.load(backup)
    
for link in data["links"]:
    created = datetime.strptime(link['created'], edit.CREATED_TIME_FORMAT)
    tags = link['tags'].split("|")
        
    lm.add(page_title=link['page_title'], 
                    desc_text=link['desc_text'], 
                    url_address=link['url_address'], 
                    author=link['author'], 
                    tags=tags, 
                    created=created)

for user_obj in data["users"]:
    um.add(user_obj['username'], user_obj['password'], True)