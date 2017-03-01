"""
Testing the WSGI app
"""

import unittest
import wsgilinkapp
from webtest import TestApp
from unittest.mock import patch
from unittest.mock import MagicMock

class UtilitiesTest(unittest.TestCase):
    """
    Tests for helper functions for the WSGI apps.
    """
    def test_check_path_happy_path_start_false(self):
        
        environ = {'linkapp.path_prefix':'/linkapp/', 'PATH_INFO':'/linkapp/'}
        
        self.assertTrue(wsgilinkapp.check_path(environ, ""))
        self.assertFalse(wsgilinkapp.check_path(environ, "goober"))

        environ['PATH_INFO'] = "/linkapp/edit"
        self.assertTrue(wsgilinkapp.check_path(environ, "edit"))
        
        environ['PATH_INFO'] = "/linkapp/edit/"
        self.assertFalse(wsgilinkapp.check_path(environ, "edit"))
        
        
    def test_check_path_happy_path_start_true(self):
        
        environ = {'linkapp.path_prefix':'/linkapp/', 'PATH_INFO':'/linkapp/'}
        
        self.assertFalse(wsgilinkapp.check_path(environ, "goober"))

        environ['PATH_INFO'] = "/linkapp/edit/stuffhere"
        self.assertTrue(wsgilinkapp.check_path(environ, "edit", True))
        
        environ['PATH_INFO'] = "/linkapp/edit/"
        self.assertTrue(wsgilinkapp.check_path(environ, "edit", True))
        
        
class AuthenticationMiddlewareTest(unittest.TestCase):
    """
    Testing the Authentication Middleware.
    """
    
    def mocked_app(self):
        
        def application(environ, start_response):
            body = b"thisbody"
            headers = [('Content-Type', 'text/html; charset=utf8'),
                       ('Content-Length', str(len(body)))]
            start_response('200 OK', headers)
            return [body]
            
        mid_wrap = wsgilinkapp.AuthenticationMiddleware(application)
        mocked_um = MagicMock()
        return mocked_um, TestApp(mid_wrap, extra_environ={'linkapp.user_manager': mocked_um})
        
        
    def test_access_without_cred(self):
        
        um, app = self.mocked_app()
        resp = app.get("/path", status=401)
        self.assertEqual(resp.status_int, 401)
        
    
    def test_access_with_valid_cred(self):
        
        um, app = self.mocked_app()
        um.authenticate.return_value = True
        app.authorization = ('Basic', ('user', 'password'))
        resp = app.get("/path")
        self.assertEqual(resp.status_int, 200)
        
    
    def test_access_with_invalid_cred(self):
        
        um, app = self.mocked_app()
        um.authenticate.return_value = False
        app.authorization = ('Basic', ('user', 'password'))
        resp = app.get("/path", status=401)
        self.assertEqual(resp.status_int, 401)
        
        
class NewTest(unittest.TestCase):
    """
    Testing wsgilinkapp.new
    """
    
    def test_new_happy_path(self):
        
        app = TestApp(wsgilinkapp.new, extra_environ={'linkapp.path_prefix': '/linkapp/'})
        
        resp = app.get("/path")
        self.assertEqual(resp.status_int, 200)
        
        
    def test_new_wrong_method(self):
        
        app = TestApp(wsgilinkapp.new, extra_environ={'linkapp.path_prefix': '/linkapp/'})
        
        resp = app.post("/path", status='4**')
        self.assertEqual(resp.status_int, 400)
        
        
class EditTest(unittest.TestCase):
    """
    Testing wsgilinkapp.edit
    """
    
    def mocked_app(self):
        mocked_lm = MagicMock()
        
        app = TestApp(wsgilinkapp.edit, 
            extra_environ={
                'linkapp.path_prefix': '/linkapp/', 
                'linkapp.link_manager': mocked_lm})
        
        return mocked_lm, app
    
    
    def test_edit_happy_path(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.get("/path/" + ("x"*32))
        self.assertEqual(resp.status_int, 200)
        
        
    def test_edit_wrong_method(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.post("/path", status='4**')
        self.assertEqual(resp.status_int, 400)
        
        
    def test_edit_wrong_key(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.get("/path", status='4**')
        self.assertEqual(resp.status_int, 404)
        
        
class SaveTest(unittest.TestCase):
    """
    Testing wsgilinkapp.save
    """
    
    def mocked_app(self):
        mocked_lm = MagicMock()
        
        app = TestApp(wsgilinkapp.save, 
            extra_environ={
                'linkapp.path_prefix': '/linkapp/',
                'linkapp.loggedin': 'test_name',
                'linkapp.link_manager': mocked_lm})
        
        return mocked_lm, app
        
        
    def test_save_bad_request(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.get("/path", status='4**')
        self.assertEqual(resp.status_int, 400)
        
        
    def test_happy_path_save_add(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = False
        
        resp = app.post("/path", 
            {'page_title': "Something as a Title",
                'desc_text': "Whole bunch of things. Talking about stuff.",
                'url_address': "http://www.sillygooses.com",
                'tags': "one|two|tags|blue"
            })
        self.assertEqual(resp.status_int, 302)
        mocked_lm.add.assert_called_once()
        
    def test_happy_path_save_edit(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = False
        mocked_lm.url_url_changed.return_value = False
        
        resp = app.post("/path/" + ("x"*32), 
            {'page_title': "Something as a Title",
                'desc_text': "Whole bunch of things. Talking about stuff.",
                'url_address': "http://www.sillygooses.com",
                'tags': "one|two|tags|blue"
            })
        self.assertEqual(resp.status_int, 302)
        mocked_lm.modify.assert_called_once()
        
        
    def test_save_no_data_edit(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = False
        mocked_lm.url_url_changed.return_value = False
        
        resp = app.post("/path/" + ("x"*32), {})
        resp.mustcontain("errors")
        self.assertEqual(resp.status_int, 200)
        mocked_lm.modify.assert_not_called()
        
        
    def test_save_empty_data_edit(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = False
        mocked_lm.url_url_changed.return_value = False
        
        resp = app.post(
            "/path/" + ("x"*32),
            {'page_title': "",
             'desc_text': "",
             'url_address': "",
             'tags': ""
            })
        
        resp.mustcontain("errors")
        self.assertEqual(resp.status_int, 200)
        mocked_lm.modify.assert_not_called()
        
        
    def test_save_duplicate_url_edit(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = True
        mocked_lm.url_url_changed.return_value = False
        
        resp = app.post(
            "/path/" + ("x"*32),
            {'page_title': "Lions Eat Apples",
             'desc_text': "Are they hungry for apples Jerry?",
             'url_address': "http://www.thesame.com",
             'tags': "tag1"
            })
        
        resp.mustcontain("errors")
        self.assertEqual(resp.status_int, 200)
        mocked_lm.modify.assert_not_called()
        
        
    def test_save_no_data_add(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = False
        mocked_lm.url_url_changed.return_value = False
        
        resp = app.post("/path", {})
        resp.mustcontain("errors")
        self.assertEqual(resp.status_int, 200)
        mocked_lm.add.assert_not_called()
        
        
    def test_save_empty_data_add(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = False
        mocked_lm.url_url_changed.return_value = False
        
        resp = app.post(
            "/path",
            {'page_title': "",
             'desc_text': "",
             'url_address': "",
             'tags': ""
            })
        
        resp.mustcontain("errors")
        self.assertEqual(resp.status_int, 200)
        mocked_lm.add.assert_not_called()
        
        
    def test_save_duplicate_url_add(self):
        
        mocked_lm, app = self.mocked_app()
        mocked_lm.url_exists.return_value = True
        mocked_lm.url_url_changed.return_value = False
        
        resp = app.post(
            "/path",
            {'page_title': "Lions Eat Apples",
             'desc_text': "Are they hungry for apples Jerry?",
             'url_address': "http://www.thesame.com",
             'tags': "tag1"
            })
        
        resp.mustcontain("errors")
        self.assertEqual(resp.status_int, 200)
        mocked_lm.add.assert_not_called()
        
        
class ListingTest(unittest.TestCase):
    """
    Testing wsgilinkapp.listing
    """
    
    def mocked_app(self):
        mocked_lm = MagicMock()
        
        app = TestApp(wsgilinkapp.listing, 
            extra_environ={
                'linkapp.path_prefix': '/linkapp/',
                'linkapp.link_manager': mocked_lm})
        
        return mocked_lm, app
        
    def test_listing_happy_path(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.get("/path")
        self.assertEqual(resp.status_int, 200)
        
        
    def test_listing_wrong_method(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.post("/path", status='4**')
        self.assertEqual(resp.status_int, 400)
        
        
class ListingByTagTest(unittest.TestCase):
    """
    Testing wsgilinkapp.listing_by_tag
    """
    
    def mocked_app(self):
        mocked_lm = MagicMock()
        
        app = TestApp(wsgilinkapp.listing_by_tag, 
            extra_environ={
                'linkapp.path_prefix': '/linkapp/',
                'linkapp.link_manager': mocked_lm})
        
        return mocked_lm, app
        
    def test_listing_by_tag_happy_path(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.get("/path/tagged")
        self.assertEqual(resp.status_int, 200)
        
        
    def test_listing_by_tag_wrong_method(self):
        
        mocked_lm, app = self.mocked_app()
        
        resp = app.post("/path/tagged", status='4**')
        self.assertEqual(resp.status_int, 400)