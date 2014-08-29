import threading
import time

from web import web

import fake

def test_manager_create_threads():
	server = fake.FakeHTTPServer()

	server.manager_thread = threading.Thread(target=web.HTTPServer.manager, args=(server,))
	server.manager_thread.start()

	#Wait a bit
	time.sleep(0.1)

	assert len(server.worker_threads) == server.num_threads
	for thread in server.worker_threads:
		assert thread.is_alive()

	server.manager_shutdown = True
	server.manager_thread.join(timeout=1)
	server.manager_shutdown = False

	assert server.worker_threads == None

def test_manager_thread_death():
	server = fake.FakeHTTPServer()

	server.manager_thread = threading.Thread(target=web.HTTPServer.manager, args=(server,))
	server.manager_thread.start()

	#Wait a bit
	time.sleep(0.1)

	server.worker_shutdown = 0
	server.worker_threads[0].join(timeout=1)
	server.worker_shutdown = None

	#Wait a bit for thread restart
	time.sleep(server.poll_interval + 0.1)

	#Test that it is alive again
	assert server.worker_threads[0].is_alive()

	server.manager_shutdown = True
	server.manager_thread.join(timeout=1)
	server.manager_shutdown = False

def test_manager_scaling():
	server = fake.FakeHTTPServer()

	server.manager_thread = threading.Thread(target=web.HTTPServer.manager, args=(server,))
	server.manager_thread.start()

	#Wait a bit
	time.sleep(0.1)

	for i in range(server.max_queue):
		server.request_queue.put(None)

	#Wait a bit for thread start
	time.sleep(server.poll_interval + 0.1)

	#Just make sure it is spawning some but not too many threads
	num_threads = len(server.worker_threads)
	assert num_threads > server.num_threads
	assert num_threads <= server.max_threads

	#Mark a task as done
	server.request_queue.get_nowait()
	server.request_queue.task_done()

	#Wait a bit for another poll
	time.sleep(server.poll_interval + 0.1)

	#Make sure the number didn't go down (and isn't over the max)
	last_threads = num_threads
	num_threads = len(server.worker_threads)
	assert num_threads >= last_threads
	assert num_threads <= server.max_threads

	#Mark all tasks as done
	try:
		while True:
			server.request_queue.get_nowait()
			server.request_queue.task_done()
	except:
		pass

	#Wait a bit for another poll
	time.sleep(server.poll_interval + 0.1)

	#Make sure the number at least went down
	last_threads = num_threads
	num_threads = len(server.worker_threads)
	assert num_threads < last_threads
	assert num_threads >= server.num_threads

	server.manager_shutdown = True
	server.manager_thread.join(timeout=1)
	server.manager_shutdown = False

def test_worker_shutdown():
	server = fake.FakeHTTPServer()

	thread = threading.Thread(target=web.HTTPServer.worker, args=(server, 0))
	thread.start()

	#Wait a bit
	time.sleep(0.1)

	server.worker_shutdown = 0
	thread.join(timeout=1)
	server.worker_shutdown = None

	#Do it again but this time setting worker_shutdown to -1
	thread = threading.Thread(target=web.HTTPServer.worker, args=(server, 0))
	thread.start()

	#Wait a bit
	time.sleep(0.1)

	server.worker_shutdown = -1
	thread.join(timeout=1)
	server.worker_shutdown = None

def test_worker_handle():
	server = fake.FakeHTTPServer()

	thread = threading.Thread(target=web.HTTPServer.worker, args=(server, 0))
	thread.start()

	#Wait a bit
	time.sleep(0.1)

	request = fake.FakeHTTPRequest(None, None, None)

	server.request_queue.put((request, False, None))

	#Wait another bit
	time.sleep(server.poll_interval + 0.1)

	assert server.request_queue.qsize() == 0
	assert thread.is_alive()

	assert request.handled == 1

	server.worker_shutdown = -1
	thread.join(timeout=1)
	server.worker_shutdown = None

def test_worker_handle_exception():
	server = fake.FakeHTTPServer()

	thread = threading.Thread(target=web.HTTPServer.worker, args=(server, 0))
	thread.start()

	#Wait a bit
	time.sleep(0.1)

	request = fake.FakeHTTPRequest(None, None, None)
	def bad_handle(self):
		raise Exception()
	request.handle = bad_handle

	server.request_queue.put((request, False, None))

	#Wait another bit
	time.sleep(server.poll_interval + 0.1)

	assert server.request_queue.qsize() == 0
	assert thread.is_alive()

	server.worker_shutdown = -1
	thread.join(timeout=1)
	server.worker_shutdown = None

def test_worker_keepalive():
	server = fake.FakeHTTPServer()

	thread = threading.Thread(target=web.HTTPServer.worker, args=(server, 0))
	thread.start()

	#Wait a bit
	time.sleep(0.1)

	request = fake.FakeHTTPRequest(None, None, None, keepalive_number=2)

	server.request_queue.put((request, True, None))

	#Wait for two polls
	time.sleep(server.poll_interval + server.poll_interval + 0.1)

	assert server.request_queue.qsize() == 0
	assert thread.is_alive()

	assert request.handled == 2
	assert request.initial_timeout == server.keepalive_timeout

	server.worker_shutdown = -1
	thread.join(timeout=1)
	server.worker_shutdown = None
