##
# copyright 2009, James William Pye
# http://python.projects.postgresql.org
##
"""
TestCase subclasses used by postgresql.test.
"""
import sys
import os
import random
import socket
import math
import atexit
import unittest

from . import exceptions as pg_exc
from . import cluster as pg_cluster
from . import installation as pg_inn

class TestCaseWithCluster(unittest.TestCase):
	"""
	postgresql.driver *interface* tests.
	"""
	def __init__(self, *args, **kw):
		super().__init__(*args, **kw)
		self.installation = pg_inn.Installation.default()
		self.cluster_path = \
			'py_unittest_postgresql_cluster_' \
			+ str(os.getpid()) + '_' + type(self).__name__

		if self.installation is None:
			sys.stderr.write("ERROR: cannot find 'default' pg_config\n")
			sys.stderr.write(
				"HINT: set the PGINSTALLATION environment " \
				"variable to the `pg_config` path\n"
			)
			sys.exit(1)

		self.cluster = pg_cluster.Cluster(
			self.cluster_path, self.installation
		)
		if self.cluster.initialized():
			self.cluster.drop()

	def _gen_cluster_port(self):
		i = 0
		limit = 1024
		while i < limit:
			i += 1
			port = (math.floor(random.random() * 50000) + 1024)
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM,)
			try:
				s.bind(('localhost', port))
			except socket.error as e:
				if e.errno in (errno.EACCES, errno.EADDRINUSE, errno.EINTR):
					# try again
					continue
			s.close()
			break
		else:
			port = None
		return port

	def configure_cluster(self):
		self.cluster_port = self._gen_cluster_port()
		if self.cluster_port is None:
			e = pg_exc.ClusterError(
				'failed to find a port for the test cluster'
			)
			self.cluster.ife_descend(e)
			e.raise_exception()
		self.cluster.settings.update(dict(
			port = str(self.cluster_port), # XXX: identify an available port and use it
			max_connections = '16',
			shared_buffers = '64',
			listen_addresses = 'localhost',
			log_destination = 'stderr',
			log_min_messages = 'FATAL',
		))

	def initialize_database(self):
		c = self.cluster.connection(
			user = 'test',
			database = 'template1',
		)
		with c:
			if c.prepare(
				"select true from pg_catalog.pg_database " \
				"where datname = 'test'"
			).first() is None:
				c.execute('create database test')
			print("============ INITIALIZED test ==============")

	def run(self, *args, **kw):
		if not self.cluster.initialized():
			self.cluster.encoding = 'utf-8'
			self.cluster.init(
				user = 'test',
				encoding = self.cluster.encoding,
				logfile = sys.stderr,
			)
			try:
				atexit.register(self.cluster.drop)
				self.configure_cluster()
				self.cluster.start(logfile = sys.stdout)
				self.cluster.wait_until_started()
				self.initialize_database()
			except Exception:
				self.cluster.drop()
				atexit.unregister(self.cluster.drop)
				raise
		if not self.cluster.running():
			self.cluster.start()
			self.cluster.wait_until_started()

		db = self.cluster.connection(user = 'test',)
		with db:
			self.db = db
			return super().run(*args, **kw)
			self.db = None
