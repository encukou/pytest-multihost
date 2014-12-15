A pytest plugin for multi-host testing.


Downloading
-----------

Release tarballs will be made available for download from Fedora Hosted:
    https://fedorahosted.org/released/python-pytest-multihost/

The goal is to include this project in Fedora repositories. Until that happens,
you can use testing builds from COPR – see "Developer links" below.

You can also install using pip:
    https://pypi.python.org/pypi/pytest-multihost


Usage
-----

This plugin takes a description of your infrastructure,
and provides, via a fixture, Host objects that commands can be called on.

It is intended as a general base for a framework; any project using it will
need to extend it for its own needs.


The object provided to tests is a Config object, which has (among others)
these attributes::

    test_dir – directory to store test-specific data in,
               defaults to /root/multihost_tests
    ipv6 – true if connecting via IPv6

    domains – the list of domains

Hosts to run on are arranged in domains, which have::

    name – the DNS name of the domain
    type – a string specifying the type of the domain ('default' by default)

    config – the Config this domain is part of
    hosts – list of hosts in this domain

And the hosts have::

    role – type of this host; should encode the OS and installed packages
    hostname – fully qualified hostname, usually reachable from other hosts
    shortname – first component of hostname
    external_hostname – hostname used to connect to this host
    ip – IP address

    domain – the Domain this host is part of

    transport – allows operations like uploading and downloading files
    run_command() – runs the given command on the host

For each object – Config, Domain, Host – one can provide subclasses
to modify the behavior (for example, FreeIPA would add Host methods
to run a LDAP query or to install an IPA server).
Each object has from_dict and to_dict methods, which can add additional
attributes – for example, Config.ntp_server.


To use the multihost plugin in tests, create a fixture listing the domains
and what number of which host role is needed::

    import pytest
    from pytest_multihost import make_multihost_fixture

    @pytest.fixture(scope='class')
    def multihost(request):
        mh = make_multihost_fixture(
            request,
            descriptions=[
                {
                    'type': 'ipa',
                    'hosts': {
                        'master': 1,
                        'replica': 2,
                    },
                },
            ],
        )
        return mh.install()

If not enough hosts are available, all tests that use the fixture are skipped.

The object returned from ``make_multihost_fixture`` only has the "config"
attribute (and the install method).
Users are expected to add convenience attributes.
For example, FreeIPA, which typically uses a single domain with one master,
several replicas and some clients, would do::

    from pytest_multihost import make_multihost_fixture

    @pytest.fixture
    def multihost(request):
        mh = make_multihost_fixture(request, descriptions=[
                {
                    'type': 'ipa',
                    'hosts': {
                        'master': 1,
                        'replica': 1,
                        'client': 1,
                    },
                },
            ],
        )
        mh.domain = mh.config.domains[0]
        [mh.master] = mh.domain.hosts_by_role('master')
        mh.replicas = mh.domain.hosts_by_role('replica')
        mh.clients = mh.domain.hosts_by_role('client')
        return mh.install()


As with any pytest fixture, this can be used by getting it as
a function argument.
Unlike regular pytest fixtures, it needs to be used on a class: its
install() method calls the class' install(), and at cleanup time, uninstall()
is called.
For a simplified example, FreeIPA usage could look something like this::

    class TestMultihost(object):
        def install(self, multihost):
            multihost.master.run_command(['ipa-server-install'])

        def uninstall(self, multihost):
            multihost.master.run_command(['ipa-server-install', '--uninstall'])

        def test_installed(self, multihost):
            multihost.master.run_command(['ipa', 'ping'])

.. note::
    install() and uninstall() are not testing functions, they are only
    called with (self, multihost).


The description of infrastructure is provided in a JSON or YAML file,
which is named on the py.test command line. For example::

    ssh_key_filename: ~/.ssh/id_rsa
    domains:
      - name: adomain.test
        type: test-a
        hosts:
          - name: master
            ip: 192.0.2.1
            role: master
          - name: replica1
            ip: 192.0.2.2
            role: replica
          - name: replica2
            ip: 192.0.2.3
            role: replica
            external_hostname: r2.adomain.test
          - name: client1
            ip: 192.0.2.4
            role: client
          - name: extra
            ip: 192.0.2.6
            role: extrarole
      - name: bdomain.test
        type: test-b
        hosts:
          - name: master.bdomain.test
            ip='192.0.2.65
            role: master

$ py.test --multihost-config=/path/to/configfile.yaml

To use YAML files, the PyYAML package is required. Without it only JSON files
can be used.

Contributing
------------

The project is happy to accept patches!
Please format your contribution using the FreeIPA `patch guidelines`_,
and send it to <freeipa-devel@redhat.com>.
Any development discussion is welcome there.

Someday the project might get its own list, but that seems premature now.


Developer links
---------------

  * Bug tracker: https://fedorahosted.org/python-pytest-multihost/report/3
  * Code browser: ​https://git.fedorahosted.org/cgit/python-pytest-multihost
  * git clone ​https://git.fedorahosted.org/git/python-pytest-multihost.git
  * Unstable packages for Fedora: https://copr.fedoraproject.org/coprs/pviktori/pytest-plugins/

To release, update version in setup.py, add a Git tag like "v0.3",
and run `make tarball`.
Running `make upload` will put the tarball to Fedora Hosted and PyPI,
and a SRPM on Fedorapeople, if you have the rights.
Running `make release` will upload and fire a COPR build.

.. _patch guidelines: http://www.freeipa.org/page/Contribute/Patch_Format
