import io
import re
import threading

from web import web

class FakeBytes(bytes):
	def set_len(self, len):
		self.len = len

	def __len__(self):
		return self.len

class FakeSocket(object):
	def __init__(self, initial=b''):
		self.bytes = initial
		self.timeout = None

	def setsockopt(self, level, optname, value):
		pass

	def settimeout(self, timeout):
		self.timeout = timeout

	def makefile(self, mode='r', buffering=None):
		return io.BytesIO(self.bytes)

class FakeHTTPHandler(object):
	def __init__(self, request, response, groups):
		self.request = request
		self.response = response
		self.groups = groups

	def respond(self):
		return 204, ''

class FakeHTTPResponse(object):
	def __init__(self, connection, client_address, server, request):
		self.connection = connection
		self.client_address = client_address
		self.server = server

		self.request = request

		self.wfile = io.BytesIO(b'')

		self.headers = web.HTTPHeaders()

		self.write_body = True

	def handle(self):
		pass

	def close(self):
		pass

class FakeHTTPRequest(object):
	def __init__(self, connection, client_address, server, timeout=None, body=None, headers=None, method='GET', resource='/', groups=(), handler=FakeHTTPHandler, handler_args={}, response=FakeHTTPResponse):
		self.connection = connection
		self.client_address = client_address
		self.server = server

		self.timeout = timeout

		self.rfile = io.BytesIO(body)

		self.response = response(connection, client_address, server, self)

		self.keepalive = True

		self.method = method

		self.resource = resource

		self.request_line = method + ' ' + resource + ' ' + web.http_version

		if headers:
			self.headers = headers
		else:
			self.headers = web.HTTPHeaders()

		if body:
			self.headers.set('Content-Length', str(len(body)))

		self.handler = handler(self, self.response, groups, **handler_args)

	def handle(self):
		pass

	def close(self):
		pass

class FakeHTTPLog(web.HTTPLog):
	def __init__(self, httpd_log, access_log):
		self.httpd_log = io.StringIO()
		self.httpd_log_lock = threading.Lock()

		self.access_log = io.StringIO()
		self.access_log_lock = threading.Lock()

class FakeHTTPServer(object):
	def __init__(self, routes={}, error_routes={}, log=FakeHTTPLog(None, None)):
		self.routes = {}
		for regex, handler in routes.items():
			self.routes[re.compile('^' + regex + '$')] = handler
		self.error_routes = {}
		for regex, handler in error_routes.items():
			self.error_routes[re.compile('^' + regex + '$')] = handler

		self.log = log

		self.res_lock = web.ResLock()
