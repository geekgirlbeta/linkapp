"""
Module for editing links to add, delete, modify and list data submitted.
"""
import redis
import hashlib
from datetime import datetime

CREATED_TIME_FORMAT = "%m-%d-%Y @ %H:%M"

def pipeline_monkeypatch(self, transaction=True, shard_hint=None):
        """
        MONKEYPATCH: callbacks really should be a copy!
        """
        return redis.client.StrictPipeline(
            self.connection_pool,
            self.response_callbacks.copy(),
            transaction,
            shard_hint)

redis.StrictRedis.pipeline = pipeline_monkeypatch

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
        
        
    def add(self, page_title, desc_text, url_address, author, tags, created=None):
        """Add link to the database."""
        raw_id, redis_key = self.key(url_address)
        
        if created is None:
            created = datetime.now()
        
        if isinstance(tags, str):
            raise Exception('Tags must be a list, set, tuple, etc.')
            
        #taking out excess white space and removing any duplicates.
        tags = set([x.strip() for x in tags])
        
        
        if not tags:
            raise Exception('At least one tag must be provided.')
            
        with self.connection.pipeline() as pipe:
        
            pipe.hmset(redis_key, {
                'page_title': page_title, 
                'desc_text': desc_text, 
                'url_address': url_address,
                'key': raw_id,
                'author': author,
                'created': created.strftime(CREATED_TIME_FORMAT), 
                'tags': "|".join(tags)
            })
            
            for tag in tags:
                tag_id = 'tag:%s' % (tag,)
                pipe.sadd(tag_id, raw_id)
                
            pipe.execute()
            
        return raw_id
        
    def delete(self, raw_id):
        """Deleting a link from the database."""
        
        tags = self.connection.hmget(self.prefix_key(raw_id), "tags")[0]
        tags = tags.split("|")
        
        # TODO: Consider adding a watch on the link key during deletion.
        with self.connection.pipeline() as pipe:
            for tag in tags:
                pipe.srem('tag:%s' % (tag,), raw_id)
                
            pipe.delete(self.prefix_key(raw_id))
            pipe.execute() 
            
        
    def modify(self, raw_id, page_title=None, desc_text=None, url_address=None, author=None, created=None, tags=None):
        """Modify an existing link in the database."""
        fields = {}
        
        if page_title is not None:
            fields['page_title'] = page_title
            
        if desc_text is not None:
            fields['desc_text'] = desc_text
            
        if url_address is not None:
            fields['url_address'] = url_address
            
        if author is not None:
            fields['author'] = author
            
        if created is not None:
            fields['created'] = created.strftime(CREATED_TIME_FORMAT)
            
        if tags is not None:
            tags = set([x.strip() for x in tags])
            if not tags:
                raise Exception('At least one tag must be provided.')
            
            fields['tags'] = "|".join(tags)
            
        if fields:
            if fields.get("url_address", None):
                comp_id, junk = self.key(url_address)
                if comp_id == raw_id:
                    rename = False
                else:
                    rename = True
            else:
                comp_id = None
                rename = False
                
            # TODO: consider doing this in the pipeline and putting a watch on the
            #       link's key in case it changes during processing.
            if fields.get("tags", None) or rename:
                old_tags = self.connection.hmget(self.prefix_key(raw_id), 'tags')
                old_tags = old_tags[0].split("|")
            else:
                old_tags = []
            
            # TODO: REFACTOR THIS LIKE WOAH
            with self.connection.pipeline() as pipe:
                if rename:
                    pipe.rename(self.prefix_key(raw_id), self.prefix_key(comp_id))
                    
                    for existing_tag in old_tags:
                        tag_key = 'tag:%s' % (existing_tag,)
                        pipe.srem(tag_key, raw_id)
                        pipe.sadd(tag_key, comp_id)
                    
                    fields["key"] = comp_id
                    
                    raw_id = comp_id
                    
                pipe.hmset(self.prefix_key(raw_id), fields)
                
                if fields.get("tags", None):
                    for existing_tag in old_tags:
                        tag_key = 'tag:%s' % (existing_tag,)
                        pipe.srem(tag_key, raw_id)
                        
                    for tag in tags:
                        tag_key = 'tag:%s' % (tag,)
                        pipe.sadd(tag_key, raw_id)
               
                return pipe.execute()
        else:
            return None
            
        
    def list_one(self, raw_id, tag_func=None):
        """Retrieves a single link from the database"""
        with self.connection.pipeline() as pipe:
            if tag_func:
                pipe.set_response_callback('HGETALL', tag_func)
            
            pipe.hgetall(self.prefix_key(raw_id))
            
            result = pipe.execute()
            
            return result
        
    def listing(self, *tags, tag_func=None):
        """Retrieving a list of links from database."""
        if tags:
            tag_keys = ['tag:%s' % (x,) for x in tags]
            
            raw_ids = self.connection.sinter(*tag_keys)
            
            keys = [self.prefix_key(x) for x in raw_ids]
        else:
            keys = self.connection.keys("link:*")
        
        # TODO: Should we turn off transactions for this pipeline?
        with self.connection.pipeline() as pipe:
            # should restrict using this special function that returns a LinkWrapper
            # to just this pipeline - when it's gone (when we exit the 'with' block
            # below), subsequent calls to hgetall should work as expected.
            if tag_func:
                pipe.set_response_callback('HGETALL', tag_func)
            
            
            for key in keys:
                pipe.hgetall(key)
                
            result = pipe.execute()
            
            return result
            
    def exists(self, raw_id):
        """
        Return True if there is a link in the database with the given id.
        """
        return self.connection.exists(self.prefix_key(raw_id))
        
    def url_exists(self, url_address):
        """
        Return True if there is a link in the database with the given url
        """
        raw_id, key = self.key(url_address)
        
        return self.exists(raw_id)
        
    def url_changed(self, raw_id, url_address):
        """
        Returns True if the provided url is different than the one used to generate the raw_id
        """
        comp_id, junk = self.key(url_address)
        if comp_id == raw_id:
            return False
        else:
            return True
        
        