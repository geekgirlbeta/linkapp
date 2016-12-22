import cgi
import io
import pprint
import pystache
import edit
import os.path
import mimetypes
import base64
import user

renderer = pystache.Renderer(search_dirs='./templates', file_extension='html')

def check_path(environ, path):
    """
    Return true if path is requested in the given environ dictionary.
    """
    check = "%s%s" % (environ['listapp.path_prefix'], path)
    
    if environ['PATH_INFO'] == check:
        return True
    else:
        return False
        
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
        
    html = renderer.render_name('form')
    
    start_response('200 OK', [('Content-Type', 'text/html')])
    return [html.encode('utf-8')]

def save(environ, start_response):
    """This wsgi app sends the collected data back to the client."""
    if environ['REQUEST_METHOD'] != 'POST':
        start_response('400 Bad Request', [('Content-Type', 'text/plain')])
        return [b'Bad Request, Method Not Supported']
    
    post = cgi.FieldStorage(
            fp=environ['wsgi.input'],
            environ=environ,
            keep_blank_values=True
        )
    
    # context = {}
    # 
    # context['errors'] = []
    # 
    # context['page_title'] = post.getvalue('page_title', None)
    # if context['page_title'] is None or context['page_title'] == '':
        # errors.append(b'Page Title Required')
        
    # -------     
    
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
    
    if errors:
        context = {
            'errors': errors,
            'page_title': page_title,
            'desc_text': desc_text,
            'url_address': url_address
        }
        
        print(context)
        
        html = renderer.render_name('form', context)
        
        start_response('200 OK', [('Content-Type', 'text/html')])
        return [html.encode('utf-8')]
    else:
        environ['listapp.link_manager'].add(page_title, desc_text, url_address, environ['listapp.loggedin'])
        redirect_to = 'http://%s%s' % (environ['HTTP_HOST'], environ['listapp.path_prefix']) 
        start_response('302 Found', [('Location', redirect_to)])
        return [redirect_to.encode('utf-8')]
    
def listing(environ, start_response): 
    context = { 
        'links': environ['listapp.link_manager'].listing(),
    }
    
    html = renderer.render_name('list', context)

    start_response('200 OK', [('Content-Type', 'text/html')])
    return [html.encode('utf-8')]
    
def static(environ, start_response):
    
    # TODO: decide how we want the browser to cache the static content
    #       see: cache-control headers.
    
    path = environ['PATH_INFO'].replace(environ['listapp.path_prefix'], "", 1)
    print(path)
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
    
def main(environ, start_response):
    if check_path(environ, ""):
        return listing(environ, start_response)
    elif environ['PATH_INFO'].startswith("%sstatic" % (environ['listapp.path_prefix'],)):
        return static(environ, start_response)
    elif check_path(environ, "new"):
        return auth_new(environ, start_response)
    elif check_path(environ, "save"):
        return auth_save(environ, start_response)
    else:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Not Found']
    
class AppFactory:
    """
    Configure and return the main WSGI app for this application.
    """
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, path_prefix="/listapp/"):
        self.link_manager = edit.LinkManager(redis_host, redis_port, redis_db)
        self.um = user.UserManager(redis_host, redis_port, redis_db)
        self.path_prefix = path_prefix
        
    def __call__(self, environ, start_response):
        environ['listapp.link_manager'] = self.link_manager
        environ['listapp.path_prefix'] = self.path_prefix
        environ['listapp.user_manager'] = self.um
        return main(environ, start_response)
        
        

app = AppFactory(path_prefix="/")

