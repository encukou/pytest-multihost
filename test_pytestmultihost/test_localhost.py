#
# Copyright (C) 2014 pytest-multihost contributors. See COPYING for license
#

import getpass
import pytest
from subprocess import CalledProcessError
import contextlib
import sys
import os

import pytest_multihost
import pytest_multihost.transport
from pytest_multihost.config import Config

try:
    from paramiko import AuthenticationException
except ImportError:
    class AuthenticationException(Exception):
        """Never raised"""

def get_conf_dict():
    return {
        'ssh_username': getpass.getuser(),
        'domains': [
            {
                'name': 'localdomain',
                'hosts': [
                    {
                        'name': 'localhost',
                        'external_hostname': 'localhost',
                        'ip': '127.0.0.1',
                        'role': 'local',
                    },
                    {
                        'name': 'localhost',
                        'external_hostname': 'localhost',
                        'ip': '127.0.0.1',
                        'username': '__nonexisting_test_username__',
                        'role': 'badusername',
                    },
                    {
                        'name': 'localhost',
                        'external_hostname': 'localhost',
                        'ip': '127.0.0.1',
                        'username': 'root',
                        'password': 'BAD PASSWORD',
                        'role': 'badpassword',
                    },
                ],
            },
        ],
    }

@pytest.fixture(scope='class', params=['paramiko', 'openssh'])
def transport_class(request):
    if request.param == 'paramiko':
        return pytest_multihost.transport.ParamikoTransport
    elif request.param == 'openssh':
        return pytest_multihost.transport.OpenSSHTransport
    else:
        raise ValueError('bad transport_class')

@pytest.fixture(scope='class')
def multihost(request, transport_class):
    conf = get_conf_dict()
    mh = pytest_multihost.make_multihost_fixture(
        request,
        descriptions=[
            {
                'hosts': {
                    'local': 1,
                },
            },
        ],
        _config=Config.from_dict(conf),
    )
    assert conf == get_conf_dict()
    mh.host = mh.config.domains[0].hosts[0]
    mh.host.transport_class = transport_class
    assert isinstance(mh.host.transport, transport_class)
    return mh.install()

@pytest.fixture(scope='class')
def multihost_baduser(request, transport_class):
    conf = get_conf_dict()
    mh = pytest_multihost.make_multihost_fixture(
        request,
        descriptions=[
            {
                'hosts': {
                    'badusername': 1,
                },
            },
        ],
        _config=Config.from_dict(conf),
    )
    mh.host = mh.config.domains[0].hosts[0]
    mh.host.transport_class = transport_class
    return mh.install()

@pytest.fixture(scope='class')
def multihost_badpassword(request, transport_class):
    conf = get_conf_dict()
    mh = pytest_multihost.make_multihost_fixture(
        request,
        descriptions=[
            {
                'hosts': {
                    'badpassword': 1,
                },
            },
        ],
        _config=Config.from_dict(conf),
    )
    mh.host = mh.config.domains[0].hosts[0]
    mh.host.transport_class = transport_class
    return mh.install()


@contextlib.contextmanager
def _first_command(host):
    """If managed command fails, prints a message to help debugging"""
    try:
        # Run dummy command first; this should catch spurious SSH messages.
        host.run_command(['echo', 'hello', 'world'])
        # Now, run the actual command
        yield
    except (AuthenticationException, CalledProcessError):
        print (
            'Cannot login to %s using default SSH key (%s), user %s. '
            'You might want to add your own key '
            'to ~/.ssh/authorized_keys.'
            'Or, run py.test with -m "not needs_ssh"') % (
                host.external_hostname,
                host.ssh_key_filename,
                getpass.getuser())
        raise


@pytest.mark.needs_ssh
class TestLocalhost(object):
    def test_echo(self, multihost):
        host = multihost.host
        with _first_command(host):
            echo = host.run_command(['echo', 'hello', 'world'])
        assert echo.stdout_text == 'hello world\n'

    def test_put_get_file_contents(self, multihost, tmpdir):
        host = multihost.host
        filename = str(tmpdir.join('test.txt'))
        with _first_command(host):
            host.put_file_contents(filename, 'test')
        result = host.get_file_contents(filename)
        assert result == b'test'

        result = host.get_file_contents(filename, encoding='utf-8')
        assert result == 'test'

    def test_get_file_contents_nonexisting(self, multihost, tmpdir):
        host = multihost.host
        filename = str(tmpdir.join('test.txt'))
        with pytest.raises(IOError):
            host.get_file_contents(filename)

    def test_get_put_file_contents_bytes(self, multihost, tmpdir):
        host = multihost.host
        filename = str(tmpdir.join('test-bytes.txt'))
        testbytes = u'test \0 \N{WHITE SMILING FACE}'.encode('utf-8')
        with _first_command(host):
            host.put_file_contents(filename, testbytes, encoding=None)
        result = host.get_file_contents(filename, encoding=None)
        assert result == testbytes

    @pytest.mark.parametrize('encoding', ('utf-8', 'utf-16'))
    def test_put_file_contents_utf(self, multihost, tmpdir, encoding):
        host = multihost.host
        filename = str(tmpdir.join('test-{}.txt'.format(encoding)))
        teststring = u'test \N{WHITE SMILING FACE}'
        with _first_command(host):
            host.put_file_contents(filename, teststring, encoding=encoding)
        result = host.get_file_contents(filename, encoding=None)
        assert result == teststring.encode(encoding)
        with open(filename, 'rb') as f:
            assert f.read() == teststring.encode(encoding)

    @pytest.mark.parametrize('encoding', ('utf-8', 'utf-16'))
    def test_get_file_contents_encoding(self, multihost, tmpdir, encoding):
        host = multihost.host
        filename = str(tmpdir.join('test-{}.txt'.format(encoding)))
        teststring = u'test \N{WHITE SMILING FACE}'
        with open(filename, 'wb') as f:
            f.write(teststring.encode(encoding))
        result = host.get_file_contents(filename, encoding=encoding)
        assert result == teststring
        assert type(result) == type(u'')

    def test_rename_file(self, multihost, tmpdir):
        host = multihost.host
        filename = str(tmpdir.join('test.txt'))
        filename2 = str(tmpdir.join('renamed.txt'))
        with open(filename, 'w') as f:
            f.write('test')
        with _first_command(host):
            host.transport.rename_file(filename, filename2)
        with open(filename2, 'r') as f:
            assert f.read() == 'test'

    def test_remove_file(self, multihost, tmpdir):
        host = multihost.host
        filename = str(tmpdir.join('test.txt'))
        with open(filename, 'w') as f:
            f.write('test')
        assert os.path.exists(filename)
        with _first_command(host):
            host.transport.remove_file(filename)
        assert not os.path.exists(filename)

    def test_mkdir(self, multihost, tmpdir):
        host = multihost.host
        filename = str(tmpdir.join('testdir'))
        with _first_command(host):
            host.transport.mkdir(filename)
        assert os.path.exists(filename)
        assert os.path.isdir(filename)

    def test_rmdir(self, multihost, tmpdir):
        host = multihost.host
        filename = str(tmpdir.join('testdir'))
        os.mkdir(filename)
        with _first_command(host):
            host.transport.rmdir(filename)
        assert not os.path.exists(filename)

    def test_escaping(self, multihost, tmpdir):
        host = multihost.host
        test_file_path = str(tmpdir.join('testfile.txt'))

        stdin_text = '"test", test, "test", $test, '
        stdin_text += ''.join(chr(x) for x in range(32, 127))
        stdin_text += r', \x66\0111\x00, '
        stdin_text += ''.join('\\' + chr(x) for x in range(32, 127))
        tee = host.run_command(
            ["tee", test_file_path],
            stdin_text=stdin_text,
            raiseonerr=False,
        )
        print(tee.stderr_text)
        assert tee.stdout_text == stdin_text + '\n'
        with open(test_file_path, "r") as f:
            assert f.read() == tee.stdout_text

    def test_escaping_binary(self, multihost, tmpdir):
        host = multihost.host
        test_file_path = str(tmpdir.join('testfile.txt'))

        stdin_bytes = b'"test", test, "test", $test, '
        stdin_bytes += bytes(range(0, 256))
        stdin_bytes += br', \x66\0111\x00'
        tee = host.run_command(
            ["tee", test_file_path],
            stdin_text=stdin_bytes,
            raiseonerr=False,
        )
        assert tee.stdout_bytes == stdin_bytes + b'\n'
        with open(test_file_path, "rb") as f:
            assert f.read() == tee.stdout_bytes

    def test_background(self, multihost, tmpdir):
        host = multihost.host

        pipe_filename = str(tmpdir.join('test.pipe'))

        with _first_command(host):
            host.run_command(['mkfifo', pipe_filename])

        cat = host.run_command(['cat', pipe_filename], bg=True)
        host.run_command('cat > ' + pipe_filename, stdin_text='expected value')

        cat.wait()
        assert cat.stdout_text == 'expected value\n'
        assert cat.returncode == 0


@pytest.mark.needs_ssh
class TestLocalhostBadConnection(object):
    def test_reset(self, multihost):
        host = multihost.host
        with _first_command(host):
            echo = host.run_command(['echo', 'hello', 'world'])
        assert echo.stdout_text == 'hello world\n'

        host.ssh_password = 'BAD PASSWORD'
        host.ssh_key_filename = None
        echo = host.run_command(['echo', 'hello', 'world'])
        assert echo.stdout_text == 'hello world\n'

        host.reset_connection()
        with pytest.raises((AuthenticationException, RuntimeError)):
            echo = host.run_command(['echo', 'hello', 'world'])


    def test_baduser(self, multihost_baduser, tmpdir):
        host = multihost_baduser.host
        if host.transport_class == pytest_multihost.transport.OpenSSHTransport:
            # Avoid the OpenSSH password prompt
            return
        with pytest.raises(AuthenticationException):
            echo = host.run_command(['echo', 'hello', 'world'])

    def test_badpassword(self, multihost_badpassword, tmpdir):
        host = multihost_badpassword.host
        with pytest.raises((AuthenticationException, RuntimeError)):
            echo = host.run_command(['echo', 'hello', 'world'])
