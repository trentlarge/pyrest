from web import web

import fake

from nose.tools import nottest

test_request = 'GET / HTTP/1.1\r\n' + '\r\n'

@nottest
def test(request, handler=None, timeout=None, keepalive=True, initial_timeout=None, read_exception=False, close=True):
	if not isinstance(request, bytes):
		request = request.encode(web.http_encoding)

	if not handler:
		handler = fake.FakeHTTPHandler

	server = fake.FakeHTTPServer(routes={ '/': handler })

	socket = fake.FakeSocket(request)

	request_obj = web.HTTPRequest(socket, ('127.0.0.1', 1337), server, timeout)
	request_obj.response = fake.FakeHTTPResponse(socket, ('127.0.0.1', 1337), server, request_obj)

	if read_exception:
		def bad_read(self):
			raise Exception()
		request_obj.rfile.read = bad_read
		request_obj.rfile.readline = bad_read

	request_obj.handle(keepalive, initial_timeout)

	if close:
		request_obj.close()

	return request_obj

def test_initial_timeout():
	request = test('', initial_timeout=5)

	assert request.connection.timeout == 5

def test_timeout():
	request = test(test_request, timeout=8, initial_timeout=5)

	assert request.connection.timeout == 8

def test_read_exception():
	request = test(test_request, timeout=8, initial_timeout=5, read_exception=True)

	assert request.connection.timeout == 5
	assert request.keepalive == False

def test_no_request():
	request = test('')

	#If no request, do not keepalive
	assert request.keepalive == False

def test_request_too_large():
	#Request for 'GET aaaaaaa... HTTP/1.1\r\n' where it's length is one over the maximum line size
	long_request = 'GET ' + 'a' * (web.max_line_size - 4 - 9 - 2 + 1) + ' HTTP/1.1\r\n\r\n'

	request = test(long_request)

	assert request.handler.error.code == 414
	assert request.keepalive == False

def test_no_newline():
	request = test(test_request[:-4])

	assert request.handler.error.code == 400
	assert request.keepalive == False

def test_bad_request_line():
	request = test('GET /\r\n' + '\r\n')

	assert request.handler.error.code == 400
	assert request.keepalive == False

def test_wrong_http_version():
	request = test('GET / HTTP/9000\r\n' + '\r\n')

	assert request.handler.error.code == 505
	assert request.keepalive == False

def test_header_too_large():
	#Create a header for 'TooLong: aaaaaaa...\r\n' where it's length is one over the maximum line size
	test_header_too_long = 'TooLong: ' + 'a' * (web.max_line_size - 9 - 2 + 1) + '\r\n'
	request = test('GET / HTTP/1.1\r\n' + test_header_too_long + '\r\n')

	assert request.handler.error.code == 431
	assert request.handler.error.status_message == 'TooLong Header Too Large'
	assert request.keepalive == False

def test_too_many_headers():
	#Create a list of headers '1: test\r\n2: test\r\n...' where the number of them is one over the maximum number of headers
	headers = ''.join(str(i) + ': test\r\n' for i in range(web.max_headers + 1))

	request = test('GET / HTTP/1.1\r\n' + headers + '\r\n')

	assert request.handler.error.code == 431
	assert request.keepalive == False

def test_header_no_newline():
	request = test('GET / HTTP/1.1\r\n' + 'Test: header')

	assert request.handler.error.code == 400
	assert request.keepalive == False

def test_header_no_colon():
	request = test('GET / HTTP/1.1\r\n' + 'Test header\r\n' + '\r\n')

	assert request.handler.error.code == 400
	assert request.keepalive == False

def test_connection_close():
	request = test('GET / HTTP/1.1\r\n' + 'Connection: close\r\n' + '\r\n')

	assert request.keepalive == False

def test_handler_not_found():
	request = test('GET /nonexistent HTTP/1.1\r\n' + '\r\n')

	assert request.handler.error.code == 404
	assert request.keepalive == True

def test_keepalive():
	request = test(test_request)

	assert request.keepalive == True

def test_no_keepalive():
	request = test(test_request, keepalive=False)

	assert request.keepalive == False

def test_handler():
	request = test(test_request, handler=web.HTTPHandler)

	assert isinstance(request.handler, web.HTTPHandler)

def test_read_pipelining():
	request = test('GET / HTTP/1.1\r\n' + '\r\n' + 'GET /nonexistent HTTP/1.1\r\n' + '\r\n', close=False)

	assert request.rfile.read() == b'GET /nonexistent HTTP/1.1\r\n\r\n'

	request.close()

def test_close():
	request = test('GET / HTTP/1.1\r\n' + '\r\n')

	assert request.rfile.closed
	assert request.response.closed
