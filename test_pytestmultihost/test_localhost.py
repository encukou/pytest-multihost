#
# Copyright (C) 2014 pytest-multihost contributors. See COPYING for license
#

import getpass
import pytest
from subprocess import CalledProcessError
import contextlib
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

    def test_background(self, multihost):
	host = multihost.host
	run_nc = 'nc -l 12080 > /tmp/filename.out'
	cmd = host.run_command(run_nc, bg=True, raiseonerr=False)
	send_file = 'nc localhost 12080 < /root/anaconda-ks.cfg'
	cmd = host.run_command(send_file)
	assert cmd.returncode == 0
