#
# Copyright (C) 2013  Red Hat
# Copyright (C) 2014  pytest-multihost contributors
# See COPYING for license
#

"""Host class for integration testing"""

import os
import socket
import subprocess

from pytest_multihost import transport
from pytest_multihost.util import check_config_dict_empty, shell_quote

try:
    basestring
except NameError:
    basestring = str


class BaseHost(object):
    """Representation of a remote host

    See README for an overview of the core classes.
    """
    transport_class = None

    def __init__(self, domain, hostname, role, ip=None,
                 external_hostname=None, username=None, password=None):
        self.domain = domain
        self.role = str(role)
        if username is None:
            self.ssh_username = self.config.ssh_username
        else:
            self.ssh_username = username
        if password is None:
            self.ssh_key_filename = self.config.ssh_key_filename
            self.ssh_password = self.config.ssh_password
        else:
            self.ssh_key_filename = None
            self.ssh_password = password

        shortname, dot, ext_domain = hostname.partition('.')
        self.shortname = shortname

        self.hostname = (hostname[:-1]
                         if hostname.endswith('.')
                         else shortname + '.' + self.domain.name)

        self.external_hostname = str(external_hostname or hostname)

        self.netbios = self.domain.name.split('.')[0].upper()

        self.logger_name = '%s.%s.%s' % (
            self.__module__, type(self).__name__, shortname)
        self.log = self.config.get_logger(self.logger_name)

        if ip:
            self.ip = str(ip)
        else:
            if self.config.ipv6:
                # $(dig +short $M $rrtype|tail -1)
                dig = subprocess.Popen(
                    ['dig', '+short', self.external_hostname, 'AAAA'])
                stdout, stderr = dig.communicate()
                self.ip = stdout.splitlines()[-1].strip()
            else:
                try:
                    self.ip = socket.gethostbyname(self.external_hostname)
                except socket.gaierror:
                    self.ip = None

            if not self.ip:
                raise RuntimeError('Could not determine IP address of %s' %
                                   self.external_hostname)

        self.host_key = None
        self.ssh_port = 22

        self.env_sh_path = os.path.join(domain.config.test_dir, 'env.sh')

        self.log_collectors = []

    def __str__(self):
        template = ('<{s.__class__.__name__} {s.hostname} ({s.role})>')
        return template.format(s=self)

    def __repr__(self):
        template = ('<{s.__module__}.{s.__class__.__name__} '
                    '{s.hostname} ({s.role})>')
        return template.format(s=self)

    def add_log_collector(self, collector):
        """Register a log collector for this host"""
        self.log_collectors.append(collector)

    def remove_log_collector(self, collector):
        """Unregister a log collector"""
        self.log_collectors.remove(collector)

    @classmethod
    def from_dict(cls, dct, domain):
        """Load this Host from a dict"""
        if isinstance(dct, basestring):
            dct = {'name': dct}
        try:
            role = dct.pop('role').lower()
        except KeyError:
            role = domain.static_roles[0]

        hostname = dct.pop('name')
        if '.' not in hostname:
            hostname = '.'.join((hostname, domain.name))

        ip = dct.pop('ip', None)
        external_hostname = dct.pop('external_hostname', None)

        username = dct.pop('username', None)
        password = dct.pop('password', None)

        check_config_dict_empty(dct, 'host %s' % hostname)

        return cls(domain, hostname, role, ip, external_hostname,
                   username, password)

    def to_dict(self):
        """Export info about this Host to a dict"""
        return {
            'name': str(self.hostname),
            'ip': self.ip,
            'role': self.role,
            'external_hostname': self.external_hostname,
        }

    @property
    def config(self):
        """The Config that this Host is a part of"""
        return self.domain.config

    @property
    def transport(self):
        """Provides means to manipulate files & run processs on the remote host

        Accessing this property might connect to the remote Host
        (usually via SSH).
        """
        try:
            return self._transport
        except AttributeError:
            cls = self.transport_class
            if cls:
                # transport_class is None in the base class and must be
                # set in subclasses.
                # Pylint reports that calling None will fail
                self._transport = cls(self)  # pylint: disable=E1102
            else:
                raise NotImplementedError('transport class not available')
            return self._transport

    def reset_connection(self):
        """Reset the connection

        The next time a connection is needed, a new Transport object will be
        made. This new transport will take into account any configuration
        changes, such as external_hostname, ssh_username, etc., that were made
        on the Host.
        """
        try:
            del self._transport
        except:
            pass

    def get_file_contents(self, filename, encoding=None):
        """Shortcut for transport.get_file_contents"""
        return self.transport.get_file_contents(filename, encoding=encoding)

    def put_file_contents(self, filename, contents):
        """Shortcut for transport.put_file_contents"""
        self.transport.put_file_contents(filename, contents)

    def collect_log(self, filename):
        """Call all registered log collectors on the given filename"""
        for collector in self.log_collectors:
            collector(self, filename)

    def run_command(self, argv, set_env=True, stdin_text=None,
                    log_stdout=True, raiseonerr=True,
                    cwd=None):
        """Run the given command on this host

        Returns a Command instance. The command will have already run in the
        shell when this method returns, so its stdout_text, stderr_text, and
        returncode attributes will be available.

        :param argv: Command to run, as either a Popen-style list, or a string
                     containing a shell script
        :param set_env: If true, env.sh exporting configuration variables will
                        be sourced before running the command.
        :param stdin_text: If given, will be written to the command's stdin
        :param log_stdout: If false, standard output will not be logged
                           (but will still be available as cmd.stdout_text)
        :param raiseonerr: If true, an exception will be raised if the command
                           does not exit with return code 0
        :param cwd: The working directory for the command
        """
        raise NotImplementedError()


class Host(BaseHost):
    """A Unix host"""
    transport_class = transport.SSHTransport

    def run_command(self, argv, set_env=True, stdin_text=None,
                    log_stdout=True, raiseonerr=True,
                    cwd=None):
        # This will give us a Bash shell
        command = self.transport.start_shell(argv, log_stdout=log_stdout)

        # Set working directory
        if cwd is None:
            cwd = self.config.test_dir
        command.stdin.write('cd %s\n' % shell_quote(cwd))

        # Set the environment
        if set_env:
            command.stdin.write('. %s\n' % shell_quote(self.env_sh_path))
        command.stdin.write('set -e\n')

        if isinstance(argv, basestring):
            # Run a shell command given as a string
            command.stdin.write('(')
            command.stdin.write(argv)
            command.stdin.write(')')
        else:
            # Run a command given as a popen-style list (no shell expansion)
            for arg in argv:
                command.stdin.write(shell_quote(arg))
                command.stdin.write(' ')

        command.stdin.write(';exit\n')
        if stdin_text:
            command.stdin.write(stdin_text)
        command.stdin.flush()

        command.wait(raiseonerr=raiseonerr)
        return command


class WinHost(BaseHost):
    """
    Representation of a remote Windows host.

    This is a stub; Windows hosts can't currently be interacted with.
    """

    pass
