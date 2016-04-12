#
# Copyright (C) 2013  Red Hat
# Copyright (C) 2014  pytest-multihost contributors
# See COPYING for license
#

"""Utilities for configuration of multi-master tests"""

import collections
import logging

from pytest_multihost.util import check_config_dict_empty


class FilterError(ValueError):
    """Raised when domains description could not be satisfied"""


init_args = [
    'test_dir',
    'ssh_key_filename',
    'ssh_password',
    'ssh_username',
    'domains',
    'ipv6',
]


class Config(object):
    """Container for global configuration and a list of Domains

    See README for an overview of the core classes.
    """
    extra_init_args = ()

    def __init__(self, **kwargs):
        self.log = self.get_logger('%s.%s' % (__name__, type(self).__name__))

        admin_password = kwargs.get('admin_password') or 'Secret123'

        # This unfortunately duplicates information in _setting_infos,
        # but is left here for the sake of static analysis.
        self.test_dir = kwargs.get('test_dir', '/root/multihost_tests')
        self.ssh_key_filename = kwargs.get('ssh_key_filename')
        self.ssh_password = kwargs.get('ssh_password')
        self.ssh_username = kwargs.get('ssh_username', 'root')
        self.ipv6 = bool(kwargs.get('ipv6', False))
        self.windows_test_dir = kwargs.get('windows_test_dir', '/home/Administrator')

        if not self.ssh_password and not self.ssh_key_filename:
            self.ssh_key_filename = '~/.ssh/id_rsa'

        self.domains = []
        domain_class = self.get_domain_class()
        for domain_dict in kwargs.pop('domains'):
            self.domains.append(domain_class.from_dict(dict(domain_dict), self))

    def get_domain_class(self):
        return Domain

    def get_logger(self, name):
        """Get a logger of the given name

        Override in subclasses to use a custom logging system
        """
        return logging.getLogger(name)

    @classmethod
    def from_dict(cls, dct):
        """Load a Config object from a dict

        The dict is usually loaded from an user-supplied YAML or JSON file.

        In the base implementation, the dict is just passed to the constructor.
        If more arguments are needed, include them in the class'
        extra_init_args set.
        """

        # Backwards compatibility with FreeIPA's root-only logins
        if 'root_ssh_key_filename' in dct:
            dct['ssh_key_filename'] = dct.pop('root_ssh_key_filename')
        if 'root_password' in dct:
            dct['ssh_password'] = dct.pop('root_password')
        if 'windows_test_dir' in dct:
            dct['windows_test_dir'] = dct.pop('windows_test_dir')

        all_init_args = set(init_args) | set(cls.extra_init_args)
        extra_args = set(dct) - all_init_args
        if extra_args:
            ValueError('Extra keys in confuguration for config: %s' %
                       ', '.join(extra_args))
        self = cls(**dct)

        return self

    def to_dict(self, _autosave_names=()):
        """Save this Config object to a dict compatible with from_dict

        :param _autosave_names:
            To be used by subclasses only.
            Lists names that should be included in the dict.
            Values are taken from attributes of the same name.
            Usually this is a subset of the class' extra_init_args
        """
        dct = {'domains': [d.to_dict() for d in self.domains]}

        autosave = (set(init_args) | set(_autosave_names)) - set(['domains'])
        for argname in autosave:
            value = getattr(self, argname)
            dct[argname] = value
        return dct

    def host_by_name(self, name):
        """Get a host from any domain by name

        If multiple hosts have the same name, return the first one.
        Raise LookupError if no host is found.

        See Domain.host_by_name for details on matching.
        """
        for domain in self.domains:
            try:
                return domain.host_by_name(name)
            except LookupError:
                pass
        raise LookupError(name)

    def filter(self, descriptions):
        """Destructively filters hosts and orders domains to fit description

        :param descriptions:
            List of dicts such as:

                [
                    {
                        'type': 'ipa',
                        'hosts': {
                            'master': 1,
                            'replica': 2,
                        },
                    },
                ]

            i.e. the "type" is a type of domain, and "hosts" a dict mapping
            host roles to the number of hosts of this role that are required.

        """
        unique_domain_types = set(d.get('type', 'default')
                                  for d in descriptions)
        if len(descriptions) != len(unique_domain_types):
            # TODO: The greedy algorithm used to match domains may not yield
            # the correct result if there are several domains of the same type.
            raise ValueError('Duplicate domain type not supported')

        new_domains = []

        for i, description in enumerate(descriptions):
            for domain in list(self.domains):
                if domain.fits(description):
                    domain.filter(description['hosts'])
                    new_domains.append(domain)
                    self.domains.remove(domain)
                    break
            else:
                raise FilterError(
                    'Domain %s not configured: %s' % (i, description))

        self.domains = new_domains


class Domain(object):
    """Configuration for a domain

    See README for an overview of the core classes.
    """
    def __init__(self, config, name, domain_type):
        self.log = config.get_logger('%s.%s' % (__name__, type(self).__name__))
        self.type = str(domain_type)

        self.config = config
        self.name = str(name)
        self.hosts = []

    def get_host_class(self, host_dict):
        host_type = host_dict.get('host_type', 'default')
        return self.host_classes[host_type]

    @property
    def host_classes(self):
        from pytest_multihost.host import Host, WinHost
        return {
            'default': Host,
            'windows': WinHost,
        }

    @property
    def roles(self):
        """All the roles of the hosts in this domain"""
        return sorted(set(host.role for host in self.hosts))

    @property
    def static_roles(self):
        """Roles typical for this domain type

        To be overridden in subclasses
        """
        return ('master', )

    @property
    def extra_roles(self):
        """Roles of this Domain's hosts that aren't included in static_roles
        """
        return [role for role in self.roles if role not in self.static_roles]

    @classmethod
    def from_dict(cls, dct, config):
        """Load this Domain from a dict
        """
        domain_type = dct.pop('type', 'default')
        domain_name = dct.pop('name')
        self = cls(config, domain_name, domain_type)

        for host_dict in dct.pop('hosts'):
            host_class = self.get_host_class(host_dict)
            host = host_class.from_dict(dict(host_dict), self)
            self.hosts.append(host)

        check_config_dict_empty(dct, 'domain %s' % domain_name)

        return self

    def to_dict(self):
        """Export this Domain from a dict
        """
        return {
            'type': self.type,
            'name': self.name,
            'hosts': [h.to_dict() for h in self.hosts],
        }

    def host_by_role(self, role):
        """Return the first host of the given role"""
        hosts = self.hosts_by_role(role)
        if hosts:
            return hosts[0]
        else:
            raise LookupError(role)

    def hosts_by_role(self, role):
        """Return all hosts of the given role"""
        return [h for h in self.hosts if h.role == role]

    def host_by_name(self, name):
        """Return a host with the given name

        Checks all of: hostname, external_hostname, shortname.

        If more hosts match, returns the first one.
        Raises LookupError if no host is found.
        """
        for host in self.hosts:
            if name in (host.hostname, host.external_hostname, host.shortname):
                return host
        raise LookupError(name)

    def fits(self, description):
        """Return True if the this fits the description

        See Domain.filter for discussion of the description.
        """
        if self.type != description.get('type', 'default'):
            return False
        for role, number in description['hosts'].items():
            if len(self.hosts_by_role(role)) < number:
                return False
        return True

    def filter(self, host_counts):
        """Destructively filter hosts in this domain

        :param host_counts:
            Mapping of host role to number of hosts wanted for that role

        All extra hosts are removed from this Domain.
        """
        new_hosts = []
        for host in list(self.hosts):
            if host_counts.get(host.role, 0) > 0:
                new_hosts.append(host)
                host_counts[host.role] -= 1
        if any(h > 0 for h in host_counts.values()):
            raise ValueError(
                'Domain does not fit host counts, extra hosts needed: %s' %
                host_counts)
        self.hosts = new_hosts
