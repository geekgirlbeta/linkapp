#!/usr/bin/env python
"""
Script to reset database.
Deletes all existing data and creates a new user with username = admin and password = password.
"""

import edit
import user

lm = edit.LinkManager()
lm.connection.flushdb()

um = user.UserManager()
um.add('admin', 'password')


