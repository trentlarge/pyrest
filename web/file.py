import collections
import mimetypes
import os
import re
import shutil
import urllib.parse

import web

def normpath(path):
	old_path = path.split('/')
	new_path = collections.deque()

	for entry in old_path:
		#Ignore empty paths - A//B -> A/B
		if not entry:
			continue
		#Ignore dots - A/./B -> A/B
		elif entry == '.':
			continue
		#Go back a level by popping the last directory off (if there is one) - A/foo/../B -> A/B
		elif entry == '..':
			if len(new_path) > 0:
				new_path.pop()
		else:
			new_path.append(entry)

	#Special case for leading slashes
	if old_path[0] == '':
		new_path.appendleft('')

	#Special case for trailing slashes
	if old_path[-1] == '':
		new_path.append('')

	return '/'.join(new_path)

class FileHandler(web.HTTPHandler):
	filename = None
	dir_index = False

	def index(self):
		#Magic for stringing together everything in the directory with a newline and adding a / at the end for directories
		return ''.join(filename + '/\n' if os.path.isdir(os.path.join(self.filename, filename)) else filename + '\n' for filename in os.listdir(self.filename))

	def get_body(self):
		return False

	def do_get(self):
		try:
			if os.path.isdir(self.filename):
				#If necessary, redirect to add trailing slash
				if not self.filename.endswith('/'):
					self.response.headers.set('Location', self.request.resource + '/')

					return 307, ''

				#Check for index file
				index = self.filename + 'index.html'
				if os.path.exists(index) and os.path.isfile(index):
					indexfile = open(index, 'rb')
					self.response.headers.set('Content-Type', 'text/html')
					self.response.headers.set('Content-Length', str(os.path.getsize(index)))

					return 200, indexfile
				elif self.dir_index:
					#If no index and directory indexing enabled, send a generated one
					return 200, self.index()
				else:
					raise web.HTTPError(403)
			else:
				file = open(self.filename, 'rb')

				#Get file size from metadata
				size = os.path.getsize(self.filename)
				length = size

				#HTTP status that changes if partial data is sent
				status = 200

				#Handle range header and modify file pointer and content length as necessary
				range_header = self.request.headers.get('Range')
				if range_header:
					range_match = re.match('bytes=(\d+)-(\d+)?', range_header)
					if range_match:
						groups = range_match.groups()

						#Get lower and upper bounds
						lower = int(groups[0])
						if groups[1]:
							upper = int(groups[1])
						else:
							upper = size - 1

						#Sanity checks
						if upper < size and upper >= lower:
							file.seek(lower)
							self.response.headers.set('Content-Range', 'bytes ' + str(lower) + '-' + str(upper) + '/' + str(size))
							length = upper - lower + 1
							status = 206

				self.response.headers.set('Content-Length', str(length))

				#Tell client we allow selecting ranges of bytes
				self.response.headers.set('Accept-Ranges', 'bytes')

				#Guess MIME by extension
				mime = mimetypes.guess_type(self.filename)[0]
				if mime:
					self.response.headers.set('Content-Type', mime)

				return status, file
		except FileNotFoundError:
			raise web.HTTPError(404)
		except NotADirectoryError:
			raise web.HTTPError(404)
		except IOError:
			raise web.HTTPError(403)

class ModifyMixIn:
	def do_put(self):
		try:
			#Make sure directories are there (including the given one if not given a file)
			os.makedirs(os.path.dirname(self.filename), exist_ok=True)

			#If not directory, open (possibly new) file and fill it with request body
			if not os.path.isdir(self.filename):
				with open(self.filename, 'wb') as file:
					bytes_left = int(self.request.headers.get('Content-Length', '0'))
					while True:
						chunk = self.request.rfile.read(min(bytes_left, web.stream_chunk_size))
						if not chunk:
							break
						bytes_left -= len(chunk)
						file.write(chunk)

			return 204, ''
		except IOError:
			raise web.HTTPError(403)

	def do_delete(self):
		try:
			if os.path.isdir(self.filename):
				#Recursively remove directory
				shutil.rmtree(self.filename)
			else:
				#Remove single file
				os.remove(self.filename)

			return 204, ''
		except FileNotFoundError:
			raise web.HTTPError(404)
		except IOError:
			raise web.HTTPError(403)

class ModifyFileHandler(ModifyMixIn, FileHandler):
	pass

def new(local, remote='/', dir_index=False, modify=False, handler=FileHandler):
	global routes

	#Remove trailing slashes if necessary
	if local.endswith('/'):
		local = local[:-1]
	if remote.endswith('/'):
		remote = remote[:-1]

	#Set the appropriate inheritance whether modification is allowed
	if modify:
		inherit = ModifyMixIn, handler
	else:
		inherit = handler,

	#Create a file handler for routes
	class GenFileHandler(*inherit):
		def respond(self):
			norm_request = normpath(self.groups[0])
			if self.groups[0] != norm_request:
				self.response.headers.set('Location', self.remote + norm_request)

				return 307, ''

			self.filename = self.local + urllib.parse.unquote(self.groups[0])

			return handler.respond(self)

	GenFileHandler.local = local
	GenFileHandler.remote = remote
	GenFileHandler.dir_index = dir_index

	return { remote + '(|/.*)': GenFileHandler }

if __name__ == '__main__':
	from argparse import ArgumentParser

	parser = ArgumentParser(description='Quickly serve up local files over HTTP')
	parser.add_argument('--no-index', action='store_false', default=True, dest='indexing', help='Disable directory listings')
	parser.add_argument('--allow-modify', action='store_true', default=False, dest='modify', help='Allow file and directory modifications using PUT and DELETE methods')
	parser.add_argument('local_dir', help='Local directory to be served as the root')

	args = parser.parse_args()

	httpd = web.HTTPServer(('', 8080), new(args.local_dir, dir_index=args.indexing, modify=args.modify))
	httpd.start()
