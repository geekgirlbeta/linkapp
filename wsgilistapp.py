import cgi
import io
import pprint
import pystache
from edit import LinkManager
import os.path
import mimetypes
import base64
import user
import re

renderer = pystache.Renderer(search_dirs='./templates', file_extension='html')

def check_path(environ, path, start=False):
    """
    Return true if path is requested in the given environ dictionary.
    
    If start is True, match if path provided is the BEGINNING of the path info.
       useful if you are doing something with the parts of the path AFTER the 
       initial path (e.g. /edit/[id of thing to edit])
    """
    check = "%s%s" % (environ['listapp.path_prefix'], path)
    
    if start:
        if environ['PATH_INFO'].startswith(check+"/"):
            return True
        else:
            return False
    else:
        if environ['PATH_INFO'] == check:
            return True
        else:
            return False

class LinkWrapper:
    """
    Convenience class for wrapping raw redis data for Mustache use
    """
    def __init__(self, tags='', **kwargs):
        self._tags = tags
        
        for key, value in kwargs.items():
            setattr(self, key, value)
            
    @property
    def tags(self):
        """
        Making it easy to get a list out of the tags property.
        """
        return [{"name": x} for x in self._tags.split("|")]
        
        
def hash_to_linkwrapper(response, **options):
    """
    Takes a redis response list (result from HGETALL) and returns a LinkWrapper
    object that can be used in Mustache templates in place of the typical 
    dictionary that redis-py returns.
    """
    
    # if the response is false, an empty string or empty list, etc, 
    # return a dictionary - this is OK for mustache
    if not response:
        return {}
        
    # cleverness level up! CHEEKY
    # if you pass the same iter object to zip(), it will take the even items in
    # the iterator and use them for keys, and the odd ones for values.
    # 
    # NOTE: if that seems weird, remember that list indices start with 0 :)
    #
    it = iter(response)
    
    # SUPER CHEEKY
    attributes = dict(zip(it, it))
    
    # make each member of the dictionary into a keyword argument to pass
    # to the LinkWrapper constructor.
    return LinkWrapper(**attributes)

class AuthenticationMiddleware:
    """
    This will wrap a wsgi app to require a username and password.
    """
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        if 'HTTP_AUTHORIZATION' in environ:
            auth_type, hashed_pass = environ['HTTP_AUTHORIZATION'].split(' ')
            decoded = base64.b64decode(hashed_pass)
            username, password = decoded.decode('utf-8').split(':')
            if environ['listapp.user_manager'].authenticate(username, password):
                environ['listapp.loggedin'] = username
                return self.application(environ, start_response)
            else:
                start_response('401 Unauthorized', [('Content-Type', 'text/plain'), ('WWW-Authenticate', 'Basic realm="Test Thing"')])
                return [b'Unauthorized']
        else:
            start_response('401 Unauthorized', [('Content-Type', 'text/plain'), ('WWW-Authenticate', 'Basic realm="Test Thing"')])
            return [b'Unauthorized']

def new(environ, start_response):
    """This wsgi app gives the form to be filled out."""
    if environ['REQUEST_METHOD'] != 'GET':
        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
        return [b'Bad Request, Method Not Supported']
        
    context = {
       'prefix': environ['listapp.path_prefix'], 
       'link':True
    }
    
    html = renderer.render_name('form', context)
    
    start_response('200 OK', [('Content-Type', 'text/html')])
    return [html.encode('utf-8')]

def edit(environ, start_response):
    """This wsgi app gives the form to be filled out."""
    if environ['REQUEST_METHOD'] != 'GET':
        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
        return [b'Bad Request, Method Not Supported']

    match = re.search("/([^/]{32})$", environ['PATH_INFO'])
    
    if not match:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Not Found']
    
    # the first grouping in the regex is the id of the link post.
    context = {
        'link': environ['listapp.link_manager'].list_one(match.group(1)),
        'prefix': environ['listapp.path_prefix'],
        'key': match.group(1)
    }
    
    html = renderer.render_name('form', context)
    
    start_response('200 OK', [('Content-Type', 'text/html')])
    return [html.encode('utf-8')]

def save(environ, start_response):
    """This wsgi app sends the collected data back to the client."""
    if environ['REQUEST_METHOD'] != 'POST':
        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
        return [b'Bad Request, Method Not Supported']
    
    # if there's a key presented after /save, we need to use modify(), since
    # we're changing a link. Otherwise, we need to use add()
    theres_a_key = re.search("/([^/]{32})$", environ['PATH_INFO'])
    
    post = cgi.FieldStorage(
            fp=environ['wsgi.input'],
            environ=environ,
            keep_blank_values=True
        )

    errors = []
    
    page_title = post.getvalue('page_title', None)
    if page_title is None or page_title == '':
        errors.append({'message':b'Page Title Required'})
    
    desc_text = post.getvalue('desc_text', None)
    if desc_text is None or desc_text == '':
        errors.append({'message':b'Description Required'})
    
    url_address = post.getvalue('url_address', None)
    if url_address is None or url_address == '':
        errors.append({'message':b'URL is a required field'})
        
    tags = post.getvalue('tags', None)
    process_tags = set([x.strip() for x in tags.split('|')])
    if tags is None or tags == '' or not process_tags:
        errors.append({'message':b'Please enter at least one tag.'})
        
    
    if url_address and environ['listapp.link_manager'].url_exists(url_address):
        errors.append({'message':b'URL has already been posted'})
        
    
    if errors:
        context = {
            'errors': errors,
            'link': {
                'page_title': page_title,
                'desc_text': desc_text,
                'url_address': url_address,
                'tags': tags
            },
            'prefix': environ['listapp.path_prefix'],
            'key': None
        }
        
        if theres_a_key:
            key = theres_a_key.group(1)
            context['key'] = key
        
        html = renderer.render_name('form', context)
        
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [html.encode('utf-8')]
    else:
        if theres_a_key:
            key = theres_a_key.group(1)
            
            environ['listapp.link_manager'].modify(
                key, 
                page_title=page_title, 
                desc_text=desc_text, 
                url_address=url_address, 
                tags=process_tags, 
                author=environ['listapp.loggedin'])
        else:
            
            environ['listapp.link_manager'].add(
                page_title=page_title, 
                desc_text=desc_text, 
                url_address=url_address, 
                tags=process_tags, 
                author=environ['listapp.loggedin'])
        
        redirect_to = 'http://%s%s' % (environ['HTTP_HOST'], environ['listapp.path_prefix']) 
        start_response('302 Found', [('Location', redirect_to)])
        return [redirect_to.encode('utf-8')]
    
def listing(environ, start_response): 
    context = { 
        'links': environ['listapp.link_manager'].listing(tag_func=hash_to_linkwrapper),
        'prefix': environ['listapp.path_prefix']
    }
    
    html = renderer.render_name('list', context)

    start_response('200 OK', [('Content-Type', 'text/html')])
    return [html.encode('utf-8')]
    
def listing_by_tag(environ, start_response):
    tag = environ['PATH_INFO'].split("/")[-1]
    context = { 
        'links': environ['listapp.link_manager'].listing(tag, tag_func=hash_to_linkwrapper),
        'prefix': environ['listapp.path_prefix'],
        'tag': tag
    }
    
    html = renderer.render_name('list', context)

    start_response('200 OK', [('Content-Type', 'text/html')])
    return [html.encode('utf-8')]
    
def static(environ, start_response):
    
    # TODO: decide how we want the browser to cache the static content
    #       see: cache-control headers.
    
    path = environ['PATH_INFO'].replace(environ['listapp.path_prefix'], "", 1)
    parts = path.split("/")
    parts = parts[1:]
    
    # TODO: let the static directory be specified in configuration
    # TODO: make sure you can't load arbitrary files!
    to_get = os.path.join("./static", *parts)
    
    if os.path.isfile(to_get):
        content_type, encoding = mimetypes.guess_type(to_get)
        
        start_response('200 OK', [('Content-Type', content_type)])
        
        block_size = 4096
        
        asset = open(to_get, 'rb')
        
        # lifted from pep 333: https://www.python.org/dev/peps/pep-0333/#optional-platform-specific-file-handling
        if 'wsgi.file_wrapper' in environ:
            return environ['wsgi.file_wrapper'](asset, block_size)
        else:
            
            # lambda == anonymous function
            # equivalent to:
            # def some_name():
            #     asset.read(block_size)
            #
            # Except that it doesn't get a name and gets garbage collected
            # when it's no longer used.
            
            return iter(lambda: asset.read(block_size), '')
    else:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Not Found']

auth_new = AuthenticationMiddleware(new)
auth_save = AuthenticationMiddleware(save)
auth_edit = AuthenticationMiddleware(edit)
    
def main(environ, start_response):
    if check_path(environ, ""):
        return listing(environ, start_response)
    elif check_path(environ, "tag", True):
        return listing_by_tag(environ, start_response)
    elif environ['PATH_INFO'].startswith("%sstatic" % (environ['listapp.path_prefix'],)):
        return static(environ, start_response)
    elif check_path(environ, "new"):
        return auth_new(environ, start_response)
    elif check_path(environ, "save", True):
        return auth_save(environ, start_response)
    elif check_path(environ, "edit", True):
        return auth_edit(environ, start_response)
    else:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Not Found']
    
class AppFactory:
    """
    Configure and return the main WSGI app for this application.
    """
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, path_prefix="/listapp/"):
        self.link_manager = LinkManager(redis_host, redis_port, redis_db)
        self.um = user.UserManager(redis_host, redis_port, redis_db)
        self.path_prefix = path_prefix
        
    def __call__(self, environ, start_response):
        environ['listapp.link_manager'] = self.link_manager
        environ['listapp.path_prefix'] = self.path_prefix
        environ['listapp.user_manager'] = self.um
        return main(environ, start_response)
        
        

app = AppFactory(path_prefix="/")

