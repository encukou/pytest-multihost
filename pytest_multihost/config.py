# Authors:
#   Petr Viktorin <pviktori@redhat.com>
#   Tomas Babej <tbabej@redhat.com>
#
# Copyright (C) 2013  Red Hat
# see file 'COPYING' for use and warranty information
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Utilities for configuration of multi-master tests"""

import collections
import logging

from pytest_multihost.util import check_config_dict_empty


class FilterError(ValueError):
    """Raised when domains description could not be satisfied"""


_SettingInfo = collections.namedtuple('Setting', 'name default')
_setting_infos = (
    # Directory on which test-specific files will be stored,
    _SettingInfo('test_dir', '/root/multihost_tests'),

    # File with root's private RSA key for SSH (default: ~/.ssh/id_rsa)
    _SettingInfo('root_ssh_key_filename', None),

    # SSH password for root (used if root_ssh_key_filename is not set)
    _SettingInfo('root_password', None),
)


class Config(object):
    """Container for global configuration and a list of Domains

    See README for an overview of the core classes.
    """
    def __init__(self, **kwargs):
        self.log = logging.getLogger('%s.%s' % (__name__, type(self).__name__))

        admin_password = kwargs.get('admin_password') or 'Secret123'

        # This unfortunately duplicates information in _setting_infos,
        # but is left here for the sake of static analysis.
        self.test_dir = kwargs.get('test_dir', '/root/multihost_tests')
        self.root_ssh_key_filename = kwargs.get('root_ssh_key_filename')
        self.root_password = kwargs.get('root_password')

        if not self.root_password and not self.root_ssh_key_filename:
            self.root_ssh_key_filename = '~/.ssh/id_rsa'

        self.domains = []

    @classmethod
    def from_dict(cls, dct):
        """Load a Config object from a dict

        The dict is usually loaded from an user-supplied YAML or JSON file.
        """
        kwargs = {s.name: dct.pop(s.name, s.default) for s in _setting_infos}
        self = cls(**kwargs)

        for domain_dict in dct.pop('domains'):
            self.domains.append(Domain.from_dict(domain_dict, self))

        check_config_dict_empty(dct, 'config')

        return self

    def to_dict(self):
        """Save this Config object to a dict compatible with from_dict"""
        dct = {'domains': [d.to_dict() for d in self.domains]}
        for setting in _setting_infos:
            value = getattr(self, setting.name)
            dct[setting.name] = value
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
        unique_domain_types = set(d['type'] for d in descriptions)
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
        self.log = logging.getLogger('%s.%s' % (__name__, type(self).__name__))
        self.type = str(domain_type)

        self.config = config
        self.name = str(name)
        self.hosts = []

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
        from pytest_multihost.host import BaseHost

        domain_type = dct.pop('type', 'default')
        domain_name = dct.pop('name')
        self = cls(config, domain_name, domain_type)

        for host_dict in dct.pop('hosts'):
            host = BaseHost.from_dict(host_dict, self)
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
