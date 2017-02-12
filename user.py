"""
Module to handle users. 
"""

import redis
from passlib.hash import pbkdf2_sha256

class UserManager:
    
    def __init__(self, host="localhost", port=6379, db=0):
        self.host = host
        self.port = port
        self.db = db
        
        self.connection = redis.StrictRedis(
            decode_responses=True,
            host=self.host, 
            port=self.port, 
            db=self.db)
        
    def prefix_key(self, username):
        """Put the prefix on the key"""
        return "user:%s" % (username,)
        
    def encrypt(self, password):
        """Encrypts the password for saving in database."""
        return pbkdf2_sha256.hash(password)
        
    def authenticate(self, username, password):
        """Verifying that the user entered the correct password"""
        user = self.list_one(username)
        if user:
            return pbkdf2_sha256.verify(password, user['password'])
        else:
            return False
        
    def add(self, username, password, encrypted=False):
        """Add user to the database."""
        redis_key = self.prefix_key(username)
        
        if not encrypted:
            password = self.encrypt(password)
            
        self.connection.hmset(redis_key, {
            'username':username,
            'password':password
        })
        
        return username
        
    def delete(self, username):
        """Deleting a user from the database."""
        self.connection.delete(self.prefix_key(username))
        
    def modify(self, username, password, encrypted=False):
        """Modify an existing user in the database."""
        if not encrypted:
            password = self.encrypt(password)

        self.connection.hmset(
            self.prefix_key(username), 
            {'password':password})
        
    def list_one(self, username):
        """Retrieves a single user from the database"""
        return self.connection.hgetall(self.prefix_key(username))
        
    def listing(self):
        """Retrieving a list of users from database."""
        keys = self.connection.keys("user:*")
        
        with self.connection.pipeline() as pipe:
            for key in keys:
                pipe.hgetall(key)
                
            result = pipe.execute()
            
            return result