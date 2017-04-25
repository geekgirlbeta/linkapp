"""
Testing the edit module.

add, modify, delete, rename etc.

LinkManager class.
"""

import unittest
from datetime import datetime
from edit import LinkManager
from unittest.mock import patch
from unittest.mock import MagicMock


@patch('edit.redis.StrictRedis')
class LinkManagerTest(unittest.TestCase):
    """
    Test suite for LinkManager.
    """
    
    def test_add_happy_path(self, mocked_class):
        """
        LinkManager.add test that the correct data is being passed.
        """
        
        mocked_inst = mocked_class()
        mocked_pipe = mocked_inst.pipeline().__enter__()
        
        date = datetime(2017, 1, 15)
        
        expected = {
            'page_title': "Words In The Title", 
            'desc_text': "The little brown fox jumps over the fence.", 
            'url_address': "http://www.thisisnotaurl.com",
            'key': "raw_id",
            'author': "Hubert",
            'created': "01-15-2017 @ 00:00", 
            'tags': "fooa|foob|fooc"
        }
        
        lm = LinkManager()
        
        lm.key = MagicMock(return_value=("raw_id", "redis_key"))
        
        lm.add("Words In The Title", 
               "The little brown fox jumps over the fence.", 
               "http://www.thisisnotaurl.com", 
               "Hubert", 
               ["fooa", "fooc", "foob"],
               date)
        
        mocked_pipe.hmset.assert_called_with("redis_key", expected)
        
        mocked_pipe.hmset.assert_called_once()
        self.assertEqual(mocked_pipe.zadd.call_count, 4)
        
    def test_delete_happy_path(self, mocked_class):
        """
        LinkManager.delete happy path.
        """
        
        mocked_inst = mocked_class()
        mocked_pipe = mocked_inst.pipeline().__enter__()
        
        mocked_inst.hmget.return_value = ["fooa|foob|fooc"]
        
        lm = LinkManager()
        lm.delete("fake_key")
        
        self.assertEqual(mocked_pipe.zrem.call_count, 4)
        self.assertEqual(mocked_pipe.delete.call_count, 1)
        
        
    def test_modify_happy_path(self, mocked_class):
        """
        LinkManager.modify happy path.
        """
        
        mocked_inst = mocked_class()
        mocked_pipe = mocked_inst.pipeline().__enter__()
        
        mocked_inst.hmget.return_value = ["fooa|foo1|foo4"]
        mocked_inst.zscore.return_value = 10.0
        
        date = datetime(2017, 1, 15)
        
        lm = LinkManager()
        
        lm.key = MagicMock(return_value=("mocked_id", "redis_key"))
        
        lm.modify("mocked_id", 
            page_title="Words In The Title Modify", 
            desc_text="The little brown fox jumps over the fence. Modify", 
            url_address="http://www.mthisisnotaurl.com", 
            author="Hubert", 
            created=date, 
            tags=["fooa", "fooc", "foob", "extra"])
        
        expected = {
            'page_title': "Words In The Title Modify", 
            'desc_text': "The little brown fox jumps over the fence. Modify", 
            'url_address': "http://www.mthisisnotaurl.com",
            'author': "Hubert",
            'created': "01-15-2017 @ 00:00", 
            'tags': "extra|fooa|foob|fooc"
        }
        
        mocked_pipe.hmset.assert_called_with("link:mocked_id", expected)
        
        self.assertEqual(mocked_pipe.zrem.call_count, 3)
        self.assertEqual(mocked_pipe.zadd.call_count, 4)
        
    
@patch('edit.redis.StrictRedis')
class ReadingListManagerTest(unittest.TestCase):
    """
    Test suite for ReadingListManager.
    """
    
    
    
    
    
    