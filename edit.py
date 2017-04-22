"""
Module for editing links to add, delete, modify and list data submitted.
"""
import redis
import hashlib
import uuid
from datetime import datetime

CREATED_TIME_FORMAT = "%m-%d-%Y @ %H:%M"
BEGINNING_OF_TIME = datetime(1975, 11, 16, 20, 12, 0)

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
        tags = list(set([x.strip() for x in tags]))
        tags.sort()
        
        
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
            
            # timedelta
            score = created - BEGINNING_OF_TIME
            
            for tag in tags:
                tag_id = 'tag:%s' % (tag,)
                pipe.zadd(tag_id, score.total_seconds(), raw_id)
                
            pipe.zadd("sorted:date", score.total_seconds(), raw_id)
            
            pipe.execute()
            
        return raw_id
        
        
    def delete(self, raw_id):
        """Deleting a link from the database."""
        
        tags = self.connection.hmget(self.prefix_key(raw_id), "tags")[0]
        tags = tags.split("|")
        
        # TODO: Consider adding a watch on the link key during deletion.
        with self.connection.pipeline() as pipe:
            for tag in tags:
                pipe.zrem('tag:%s' % (tag,), raw_id)
                
            pipe.delete(self.prefix_key(raw_id))
            pipe.zrem("sorted:date", raw_id)
            pipe.execute() 
            
        
    def rename(self, raw_id, new_url):
        """
        Delete and re-add a link when the url has changed.
        
        TODO: this is only temporary, we will switch to using a random key ASAP.
        """
        existing = self.list_one(raw_id)[0]
        
        self.delete(raw_id)
        
        created = datetime.strptime(existing['created'], CREATED_TIME_FORMAT)
        tags = existing['tags'].split("|")
        
        return self.add(page_title=existing['page_title'], 
                        desc_text=existing['desc_text'], 
                        url_address=new_url, 
                        author=existing['author'], 
                        tags=tags, 
                        created=created)
        
        
        
    def modify(self, raw_id, page_title=None, desc_text=None, url_address=None, author=None, created=None, tags=None):
        """Modify an existing link in the database."""
        # TODO: REFACTOR THIS LIKE WOAH
        
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
            # TODO: update sorted set if this changes
            fields['created'] = created.strftime(CREATED_TIME_FORMAT)
            
        if tags is not None:
            # TODO: change the set to a set comprehension
            tags = list(set([x.strip() for x in tags]))
            tags.sort()
            if not tags:
                raise Exception('At least one tag must be provided.')
            
            fields['tags'] = "|".join(tags)
            
        if fields:
            if fields.get("url_address", None):
                comp_id, junk = self.key(url_address)
                if comp_id != raw_id:
                    raw_id = self.rename(raw_id, url_address)
                
            # TODO: consider doing this in the pipeline and putting a watch on the
            #       link's key in case it changes during processing.
            if fields.get("tags", None):
                old_tags = self.connection.hmget(self.prefix_key(raw_id), 'tags')
                old_tags = old_tags[0].split("|")
                score = self.connection.zscore("sorted:date", raw_id)
            else:
                old_tags = []
                score = None
            
            with self.connection.pipeline() as pipe:
                pipe.hmset(self.prefix_key(raw_id), fields)
                
                if fields.get("tags", None):
                    for existing_tag in old_tags:
                        tag_key = 'tag:%s' % (existing_tag,)
                        pipe.zrem(tag_key, raw_id)
                        
                    for tag in tags:
                        tag_key = 'tag:%s' % (tag,)
                        pipe.zadd(tag_key, score, raw_id)
               
                return pipe.execute()
        else:
            return None
            
        
    def list_one(self, raw_id, tag_func=None):
        """Retrieves a single link from the database
        
           TODO: shouldn't return a list"""
        with self.connection.pipeline() as pipe:
            if tag_func:
                pipe.set_response_callback('HGETALL', tag_func)
            
            pipe.hgetall(self.prefix_key(raw_id))
            
            result = pipe.execute()
            
            return result
        
    def _tag_intersect(self, tags, command, start=0, stop=-1):
        """
        Helper function to work with the intersection of multiple tag ordered
        sets.
        
        tags is a list of tag names
        command is what to do, either:
           - count, to run zcard on the intersection
           - keys, to return a list of all the keys in the intersection (zrevrange)
           
        TODO: consider letting the intersection persist for a while so we aren't 
              creating it over and over
        """
        if not command in ['count', 'keys']:
            raise ValueError("command must be 'count' or 'keys'")
        
        with self.connection.pipeline() as pipe:
            tag_keys = ['tag:%s' % (x,) for x in tags]
            stored_at = "tag:%s:sorted" % ("|".join(tags))
            pipe.zinterstore(stored_at, tag_keys, "MAX")
            
            if command == 'count':
                pipe.zcard(stored_at)
            elif command == 'keys':
                pipe.zrevrange(stored_at, start, stop)
                
            pipe.delete(stored_at)
            result = pipe.execute()
            
            return result[1]
        
    def count(self, *tags):
        """
        Count the number of links in the database.
        """
        if len(tags) > 1:
            return self._tag_intersect(tags, 'count')
            
        elif len(tags) == 1:
            key = 'tag:%s' % (tags[0],)
            return self.connection.zcard(key)
        else:
            key = "sorted:date"
            return self.connection.zcard(key)
            
        
        
    def listing(self, *tags, tag_func=None, start=0, stop=-1):
        """Retrieving a list of links from database.
        
            TODO: Change the name listing to something that describes more than one.
            This sounds like a single listing like in the newspaper.
            
            TODO: don't bother doing the intersection if there's just one tag.
        """
        if tags:
            raw_ids = self._tag_intersect(tags, 'keys', start=start, stop=stop)
            
        else:
            # keys = self.connection.keys("link:*")
            raw_ids = self.connection.zrevrange("sorted:date", start, stop)
            
        keys = [self.prefix_key(x) for x in raw_ids]
        
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
        
class ReadingListManager:
    """
    Class to handle lists of links that are assigned or suggested for a user.
    """
    
    def __init__(self, host="localhost", port=6379, db=0):
        self.host = host
        self.port = port
        self.db = db
        
        self.connection = redis.StrictRedis(
            decode_responses=True,
            host=self.host, 
            port=self.port, 
            db=self.db)
        
        
    def key(self, user):
        """
        Generating the redis key for a user reading list.
        """
        return "list:{}".format(user)
        
        
    def key_read(self, user):
        """
        Generating the redis key for the list of links that the user has read.
        """
        return "list-read:{}".format(user)
        
    def add(self, user, link_id):
        """
        Add link to existing reading list.
        """
        
        created = datetime.now()
        score = created - BEGINNING_OF_TIME
        
        with self.connection.pipeline() as pipe:
            pipe.zadd(self.key(user), score.total_seconds(), link_id)
            pipe.srem(self.key_read(user), link_id)
            
            pipe.execute()
            
            
    def read(self, user, link_id):
        """
        Mark a link as read.
        """
        
        self.connection.sadd(self.key_read(user), link_id)
        
        
    def unread(self, user, link_id):
        """
        Mark a link as unread.
        """
        
        self.connection.srem(self.key_read(user), link_id)
        
        
    def remove(self, user, link_id):
        """
        Remove a link from a list.
        """
        
        with self.connection.pipeline() as pipe:
            pipe.srem(self.key_read(user), link_id)
            pipe.zrem(self.key(user), link_id)
        
            pipe.execute()
        
        
    def to_read(self, user, tag_func=None):   
        
        key = self.key(user)
        key_read = self.key_read(user)
        
        with self.connection.pipeline() as pipe:
            temp_key = "to-read:{}:temp".format(user)
            pipe.zunionstore(temp_key, {key:1, key_read:0}, "MIN")
            pipe.zrangebyscore(temp_key, 1, "+inf")
            
            pipe.delete(temp_key)
            
            result = pipe.execute()
            
            print(result)
            
            keys = ["link:{}".format(x) for x in result[1]] 
            
        with self.connection.pipeline() as pipe:
            if tag_func:
                pipe.set_response_callback('HGETALL', tag_func)
            
            for key in keys:
                pipe.hgetall(key)
                
            result = pipe.execute()
            
            return result
            
            
    def been_read(self, user, tag_func=None):   
        
        key = self.key(user)
        key_read = self.key_read(user)
        
        with self.connection.pipeline() as pipe: 
            temp_key = "been-read:{}:temp".format(user)
            pipe.zunionstore(temp_key, {key:0, key_read:1}, "MIN")
            pipe.zrangebyscore(temp_key, 1, "+inf")
            
            pipe.delete(temp_key)
            
            result = pipe.execute()
            
            keys = ["link:{}".format(x) for x in result[1]] 
            
        with self.connection.pipeline() as pipe:
            if tag_func:
                pipe.set_response_callback('HGETALL', tag_func)
            
            for key in keys:
                pipe.hgetall(key)
                
            result = pipe.execute()
            
            return result