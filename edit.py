"""
Module for editing links to add, delete, modify and list data submitted.
"""
import redis
import hashlib

class LinkManager:
    
    def __init__(self, host="localhost", port=6379, db=0):
        self.host = host
        self.port = port
        self.db = db
        
        self.connection = redis.StrictRedis(
            decode_responses=True,
            host=self.host, 
            port=self.port, 
            db=self.db)
        
    def prefix_key(self, raw_id):
        """Put the prefix on the key"""
        return "link:%s" % (raw_id,)
        
    def key(self, url_address):
        """Generate a database key and hashed id based on the URL"""
        hashed = hashlib.md5(url_address.encode('utf-8')).hexdigest()
        
        raw_id = hashed
        redis_key = self.prefix_key(hashed)
        
        return raw_id, redis_key
        
    def add(self, page_title, desc_text, url_address):
        """Add link to the database."""
        raw_id, redis_key = self.key(url_address)
        
        self.connection.hmset(redis_key, {
            'page_title': page_title, 
            'desc_text': desc_text, 
            'url_address': url_address,
            'key': raw_id
        })
        
        return raw_id
        
    def delete(self, raw_id):
        """Deleting a link from the database."""
        self.connection.delete(self.prefix_key(raw_id))
        
    def modify(self, raw_id, page_title=None, desc_text=None, url_address=None):
        """Modify an existing link in the database."""
        fields = {}
        
        if page_title is not None:
            fields['page_title'] = page_title
            
        if desc_text is not None:
            fields['desc_text'] = desc_text
            
        if url_address is not None:
            fields['url_address'] = url_address
            
        if fields:
            return self.connection.hmset(self.prefix_key(raw_id), fields)
        else:
            return None
        
    def list_one(self, raw_id):
        """Retrieves a single link from the database"""
        return self.connection.hgetall(self.prefix_key(raw_id))
        
    def listing(self):
        """Retrieving a list of links from database."""
        keys = self.connection.keys("link:*")
        
        with self.connection.pipeline() as pipe:
            for key in keys:
                pipe.hgetall(key)
                
            result = pipe.execute()
            
            return result