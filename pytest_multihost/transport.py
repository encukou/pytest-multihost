#
# Copyright (C) 2015  Red Hat
# Copyright (C) 2014  pytest-multihost contributors
# See COPYING for license
#

"""Objects for communicating with remote hosts

This class defines "SSHTransport" as ParamikoTransport (by default), or as
OpenSSHTransport (if Paramiko is not importable, or the
PYTESTMULTIHOST_SSH_TRANSPORT environment variable is set to "openssh").
"""

import os
import socket
import threading
import subprocess
from contextlib import contextmanager
import errno
import logging
import io
import sys

from pytest_multihost import util

try:
    import paramiko
    have_paramiko = True
except ImportError:
    have_paramiko = False


DEFAULT = object()

class Transport(object):
    """Mechanism for communicating with remote hosts

    The Transport can manipulate files on a remote host, and open a Command.

    The base class defines an interface that specific subclasses implement.
    """
    def __init__(self, host):
        self.host = host
        self.logger_name = '%s.%s' % (host.logger_name, type(self).__name__)
        self.log = host.config.get_logger(self.logger_name)
        self._command_index = 0

    def get_file_contents(self, filename, encoding=None):
        """Read the named remote file and return the contents

        The string will be decoded using the given encoding;
        if encoding is None (default), it will be returned as a bytestring.
        """
        raise NotImplementedError('Transport.get_file_contents')

    def put_file_contents(self, filename, contents, encoding='utf-8'):
        """Write the given string (or bytestring) to the named remote file

        The contents string will be encoded using the given encoding
        (default: ``'utf-8'``), unless aleady a bytestring.
        """
        raise NotImplementedError('Transport.put_file_contents')

    def file_exists(self, filename):
        """Return true if the named remote file exists"""
        raise NotImplementedError('Transport.file_exists')

    def mkdir(self, path):
        """Make the named directory"""
        raise NotImplementedError('Transport.mkdir')

    def start_shell(self, argv, log_stdout=True, encoding=None):
        """Start a Shell

        :param argv: The command this shell is intended to run (used for
                     logging only)
        :param log_stdout: If false, the stdout will not be logged (useful when
                           binary output is expected)
        :param encoding: Encoding for the resulting Command's ``stdout_text``
                         and ``stderr_text``.

        Given a `shell` from this method, the caller can then use
        ``shell.stdin.write()`` to input any command(s), call ``shell.wait()``
        to let the command run, and then inspect ``returncode``,
        ``stdout_text`` or ``stderr_text``.

        Note that ``shell.stdin`` uses bytes I/O.
        """
        raise NotImplementedError('Transport.start_shell')

    def mkdir_recursive(self, path):
        """`mkdir -p` on the remote host"""
        if not self.file_exists(path):
            parent_path = os.path.dirname(path)
            if path != parent_path:
                self.mkdir_recursive(parent_path)
            self.mkdir(path)

    def get_file(self, remotepath, localpath):
        """Copy a file from the remote host to a local file"""
        contents = self.get_file_contents(remotepath, encoding=None)
        with open(localpath, 'wb') as local_file:
            local_file.write(contents)

    def put_file(self, localpath, remotepath):
        """Copy a local file to the remote host"""
        with open(localpath, 'rb') as local_file:
            contents = local_file.read()
        self.put_file_contents(remotepath, contents, encoding=None)

    def get_next_command_logger_name(self):
        self._command_index += 1
        return '%s.cmd%s' % (self.host.logger_name, self._command_index)

    def rmdir(self, path):
        """Remove directory"""
        raise NotImplementedError('Transport.rmdir')

    def rename_file(self, oldpath, newpath):
        """Rename file"""
        raise NotImplementedError('Transport.rename_file')

    def remove_file(self, filepath):
        """Removes files"""
        raise NotImplementedError('Transport.remove_file')


class _decoded_output_property(object):
    """Descriptor for on-demand decoding of a Command's output stream
    """
    def __init__(self, name):
        self.name = name

    def __set_name__(self, cls, name):
        # Sanity check (called only on Python 3.6+).
        # This property expects to handle attributes named '<foo>_text'.
        assert name == self.name + '_text'

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        else:
            bytestring = getattr(instance, self.name + '_bytes')
            decoded = bytestring.decode(instance.encoding)
            setattr(instance, self.name + '_text', decoded)
            return decoded


class Command(object):
    """A Popen-style object representing a remote command

    Instances of this class should only be created via method of a concrete
    Transport, such as start_shell.

    The standard error and output are handled by this class. They're not
    available for file-like reading, and are logged by default.
    To make sure reading doesn't stall after one buffer fills up, they are read
    in parallel using threads.

    After calling wait(), ``stdout_bytes`` and ``stderr_bytes`` attributes will
    be bytestrings containing the output, and ``returncode`` will contain the
    exit code.

    The ``stdout_text`` and ``stdout_text`` will be the corresponding output
    decoded using the given ``encoding`` (default: ``'utf-8'``).
    These are decoded on-demand; do not access them if a command
    produces binary output.

    A Command may be used as a context manager (in the ``with`` statement).
    Exiting the context will automatically call ``wait()``.
    This raises an exception if the exit code is not 0, unless the
    ``raiseonerr`` attribute is set to false before exiting the context.
    """
    def __init__(self, argv, logger_name=None, log_stdout=True,
                 get_logger=None, encoding='utf-8'):
        self.returncode = None
        self.argv = argv
        self._done = False

        if logger_name:
            self.logger_name = logger_name
        else:
            self.logger_name = '%s.%s' % (self.__module__, type(self).__name__)
        if get_logger is None:
            get_logger = logging.getLogger
        self.get_logger = get_logger
        self.log = get_logger(self.logger_name)
        self.encoding = encoding
        self.raiseonerr = True

    stdout_text = _decoded_output_property('stdout')
    stderr_text = _decoded_output_property('stderr')

    def wait(self, raiseonerr=DEFAULT):
        """Wait for the remote process to exit

        Raises an exception if the exit code is not 0, unless ``raiseonerr`` is
        true.

        When ``raiseonerr`` is not specified as argument, the ``raiseonerr``
        attribute is used.
        """
        if raiseonerr is DEFAULT:
            raiseonerr = self.raiseonerr

        if self._done:
            return self.returncode

        self._end_process()

        self._done = True

        if raiseonerr and self.returncode:
            self.log.error('Exit code: %s', self.returncode)
            raise subprocess.CalledProcessError(self.returncode, self.argv)
        else:
            self.log.debug('Exit code: %s', self.returncode)
        return self.returncode

    def _end_process(self):
        """Wait until the process exits and output is received, close channel

        Called from wait()
        """
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.wait(raiseonerr=self.raiseonerr)


class ParamikoTransport(Transport):
    """Transport that uses the Paramiko SSH2 library"""
    def __init__(self, host):
        super(ParamikoTransport, self).__init__(host)
        sock = socket.create_connection((host.external_hostname,
                                         host.ssh_port))
        self._transport = transport = paramiko.Transport(sock)
        transport.connect(hostkey=host.host_key)
        if host.ssh_key_filename:
            filename = os.path.expanduser(host.ssh_key_filename)
            key = paramiko.RSAKey.from_private_key_file(filename)
            self.log.debug(
                'Authenticating with private RSA key using user %s' %
                host.ssh_username)
            transport.auth_publickey(username=host.ssh_username, key=key)
        elif host.ssh_password:
            self.log.debug('Authenticating with password using user %s' %
                           host.ssh_username)
            transport.auth_password(username=host.ssh_username,
                                    password=host.ssh_password)
        else:
            self.log.critical('No SSH credentials configured')
            raise RuntimeError('No SSH credentials configured')

    @contextmanager
    def sftp_open(self, filename, mode='r'):
        """Context manager that provides a file-like object over a SFTP channel

        This provides compatibility with older Paramiko versions.
        (In Paramiko 1.10+, file objects from `sftp.open` are directly usable
        as context managers).
        """
        file = self.sftp.open(filename, mode)
        try:
            yield file
        finally:
            file.close()

    @property
    def sftp(self):
        """Paramiko SFTPClient connected to this host"""
        try:
            return self._sftp
        except AttributeError:
            transport = self._transport
            self._sftp = paramiko.SFTPClient.from_transport(transport)
            return self._sftp

    def get_file_contents(self, filename, encoding=None):
        """Read the named remote file and return the contents as a string"""
        self.log.debug('READ %s', filename)
        with self.sftp_open(filename, 'rb') as f:
            result = f.read()
        if encoding:
            result = result.decode(encoding)
        return result

    def put_file_contents(self, filename, contents, encoding=None):
        """Write the given string to the named remote file"""
        self.log.info('WRITE %s', filename)
        if encoding and not isinstance(contents, bytes):
            contents = contents.encode(encoding)
        with self.sftp_open(filename, 'wb') as f:
            f.write(contents)

    def file_exists(self, filename):
        """Return true if the named remote file exists"""
        self.log.debug('STAT %s', filename)
        try:
            self.sftp.stat(filename)
        except IOError as e:
            if e.errno == errno.ENOENT:
                return False
            else:
                raise
        return True

    def mkdir(self, path):
        self.log.info('MKDIR %s', path)
        self.sftp.mkdir(path)

    def start_shell(self, argv, log_stdout=True, encoding='utf-8'):
        logger_name = self.get_next_command_logger_name()
        ssh = self._transport.open_channel('session')
        self.log.info('RUN %s', argv)
        return SSHCommand(ssh, argv, logger_name=logger_name,
                          log_stdout=log_stdout,
                          get_logger=self.host.config.get_logger,
                          encoding=encoding)

    def get_file(self, remotepath, localpath):
        self.log.debug('GET %s', remotepath)
        self.sftp.get(remotepath, localpath)

    def put_file(self, localpath, remotepath):
        self.log.info('PUT %s', remotepath)
        self.sftp.put(localpath, remotepath)

    def rmdir(self, path):
        self.log.info('RMDIR %s', path)
        self.sftp.rmdir(path)

    def remove_file(self, filepath):
        self.log.info('REMOVE FILE %s', filepath)
        self.sftp.remove(filepath)

    def rename_file(self, oldpath, newpath):
        self.log.info('RENAME %s to %s', oldpath, newpath)
        self.sftp.rename(oldpath, newpath)


class OpenSSHTransport(Transport):
    """Transport that uses the `ssh` binary"""
    def __init__(self, host):
        super(OpenSSHTransport, self).__init__(host)
        self.control_dir = util.TempDir()

        self.ssh_argv = self._get_ssh_argv()

        # Run a "control master" process. This serves two purposes:
        # - Establishes a control socket; other SSHs will connect to it
        #   and reuse the same connection. This way the slow handshake
        #   only needs to be done once
        # - Writes the host to known_hosts so stderr of "real" connections
        #   doesn't contain the "unknown host" warning
        # Popen closes the stdin pipe when it's garbage-collected, so
        # this process will exit when it's no longer needed
        command = ['-o', 'ControlMaster=yes', '/usr/bin/cat']
        self.control_master = self._run(command, collect_output=False)

    def _get_ssh_argv(self):
        """Return the path to SSH and options needed for every call"""
        control_file = os.path.join(self.control_dir.path, 'control')
        known_hosts_file = os.path.join(self.control_dir.path, 'known_hosts')

        argv = ['ssh',
                '-l', self.host.ssh_username,
                '-o', 'ControlPath=%s' % control_file,
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=%s' % known_hosts_file]

        if self.host.ssh_key_filename:
            key_filename = os.path.expanduser(self.host.ssh_key_filename)
            argv.extend(['-i', key_filename])
        elif self.host.ssh_password:
            self.log.critical('Password authentication not supported')
            raise RuntimeError('Password authentication not supported')
        else:
            self.log.critical('No SSH credentials configured')
            raise RuntimeError('No SSH credentials configured')

        argv.append(self.host.external_hostname)
        self.log.debug('SSH invocation: %s', argv)

        return argv

    def start_shell(self, argv, log_stdout=True, encoding='utf-8'):
        self.log.info('RUN %s', argv)
        command = self._run(['bash'], argv=argv, log_stdout=log_stdout,
                            encoding=encoding)
        return command

    def _run(self, command, log_stdout=True, argv=None, collect_output=True,
             encoding='utf-8'):
        """Run the given command on the remote host

        :param command: Command to run (appended to the common SSH invocation)
        :param log_stdout: If false, stdout will not be logged
        :param argv: Command to log (if different from ``command``
        :param collect_output: If false, no output will be collected
        """
        if argv is None:
            argv = command
        logger_name = self.get_next_command_logger_name()
        ssh = SSHCallWrapper(self.ssh_argv + list(command))
        return SSHCommand(ssh, argv, logger_name, log_stdout=log_stdout,
                          collect_output=collect_output,
                          get_logger=self.host.config.get_logger,
                          encoding=encoding)

    def file_exists(self, path):
        self.log.info('STAT %s', path)
        cmd = self._run(['ls', path], log_stdout=False)
        cmd.wait(raiseonerr=False)

        return cmd.returncode == 0

    def mkdir(self, path):
        self.log.info('MKDIR %s', path)
        cmd = self._run(['mkdir', path])
        cmd.wait()

    def put_file_contents(self, filename, contents, encoding='utf-8'):
        self.log.info('PUT %s', filename)
        if encoding and not isinstance(contents, bytes):
            contents = contents.encode(encoding)
        cmd = self._run(['tee', filename], log_stdout=False)
        cmd.stdin.write(contents)
        cmd.wait()
        assert cmd.stdout_bytes == contents

    def get_file_contents(self, filename, encoding=None):
        self.log.info('GET %s', filename)
        cmd = self._run(['cat', filename], log_stdout=False)
        cmd.wait(raiseonerr=False)
        if cmd.returncode == 0:
            result = cmd.stdout_bytes
            if encoding:
                result = result.decode(encoding)
            return result
        else:
            raise IOError('File %r could not be read' % filename)

    def rmdir(self, path):
        self.log.info('RMDIR %s', path)
        cmd = self._run(['rmdir', path])
        cmd.wait()

    def remove_file(self, filepath):
        self.log.info('REMOVE FILE %s', filepath)
        cmd = self._run(['rm', filepath])
        cmd.wait()
        if cmd.returncode != 0:
            raise IOError('File %r could not be deleted' % filepath)

    def rename_file(self, oldpath, newpath):
        self.log.info('RENAME %s TO %s', oldpath, newpath)
        cmd = self._run(['mv', oldpath, newpath])
        cmd.wait()
        if cmd.returncode != 0:
            raise IOError('File %r could not be renamed to %r '
                          % (oldpath, newpath))


class SSHCallWrapper(object):
    """Adapts a /usr/bin/ssh call to the paramiko.Channel interface

    This only wraps what SSHCommand needs.
    """
    def __init__(self, command):
        self.command = command

    def invoke_shell(self):
        self.command = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    def makefile(self, mode):
        return {
            'wb': self.command.stdin,
            'rb': self.command.stdout,
        }[mode]

    def makefile_stderr(self, mode):
        assert mode == 'rb'
        return self.command.stderr

    def recv_exit_status(self):
        return self.command.wait()

    def close(self):
        return self.command.wait()


class SSHCommand(Command):
    """Command implementation for ParamikoTransport and OpenSSHTranspport"""
    def __init__(self, ssh, argv, logger_name, log_stdout=True,
                 collect_output=True, encoding='utf-8', get_logger=None):
        super(SSHCommand, self).__init__(argv, logger_name,
                                         log_stdout=log_stdout,
                                         get_logger=get_logger,
                                         encoding=encoding)
        self._stdout_lines = []
        self._stderr_lines = []
        self.running_threads = set()

        self._ssh = ssh

        self.log.debug('RUN %s', argv)

        self._ssh.invoke_shell()

        self._use_bytes = (encoding is None)

        def wrap_file(file, encoding):
            if self._use_bytes:
                return file
            else:
                return io.TextIOWrapper(file, encoding=encoding)
        self.stdin = self._ssh.makefile('wb')
        stdout = self._ssh.makefile('rb')
        stderr = self._ssh.makefile_stderr('rb')

        if collect_output:
            self._start_pipe_thread(self._stdout_lines, stdout, 'out',
                                    log_stdout)
            self._start_pipe_thread(self._stderr_lines, stderr, 'err', True)

    def _end_process(self):
        self.stdin.close()

        while self.running_threads:
            self.running_threads.pop().join()

        self.stdout_bytes = b''.join(self._stdout_lines)
        self.stderr_bytes = b''.join(self._stderr_lines)

        self.returncode = self._ssh.recv_exit_status()
        self._ssh.close()

    def _start_pipe_thread(self, result_list, stream, name, do_log=True):
        """Start a thread that copies lines from ``stream`` to ``result_list``

        If do_log is true, also logs the lines under ``name``

        The thread is added to ``self.running_threads``.
        """
        log = self.get_logger(self.logger_name)

        def read_stream():
            for line in stream:
                if do_log:
                    log.debug(line.rstrip(b'\n').decode('utf-8',
                                                        errors='replace'))
                result_list.append(line)

        thread = threading.Thread(target=read_stream)
        self.running_threads.add(thread)
        thread.start()
        return thread


if (
    not have_paramiko or
    os.environ.get('PYTESTMULTIHOST_SSH_TRANSPORT') == 'openssh'
):
    SSHTransport = OpenSSHTransport
else:
    SSHTransport = ParamikoTransport
