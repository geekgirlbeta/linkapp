# linkapp
Application for gathering links shared into a database.

# Prerequisites

* Redis 3.2.6
* Python 3.4

# Installation

    $ pip install -r requirements.txt
    
# Running

    $ gunicorn wsgilinkapp:app
    
# How To Configure

This will assume you are running Redis on your local host.

To change this, use the AppFactory class. 

    app = AppFactory(
        path_prefix="/", 
        redis_host='some other host', 
        redis_port=some other port, 
        redis_db=some other db)
        
# Add Admin User

    >>> from user import UserManager
    >>> um = UserManager()
    >>> um.add('username', 'password')
    'username'