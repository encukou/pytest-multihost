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

import os
import collections
import random
import json
import logging

from pytest_multihost.util import check_config_dict_empty


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
        kwargs = {s.name: dct.pop(s.name, s.default) for s in _setting_infos}
        self = cls(**kwargs)

        for domain_dict in dct.pop('domains'):
            self.domains.append(Domain.from_dict(domain_dict, self))

        check_config_dict_empty(dct, 'config')

        return self

    def to_dict(self):
        dct = {'domains': [d.to_dict() for d in self.domains]}
        for setting in _setting_infos:
            value = getattr(self, setting.name)
            dct[setting.name] = value
        return dct

    def host_by_name(self, name):
        for domain in self.domains:
            try:
                return domain.host_by_name(name)
            except LookupError:
                pass
        raise LookupError(name)


class Domain(object):
    """Configuration for a domain"""
    def __init__(self, config, name, domain_type):
        self.log = logging.getLogger('%s.%s' % (__name__, type(self).__name__))
        self.type = str(domain_type)

        self.config = config
        self.name = str(name)
        self.hosts = []

    @property
    def roles(self):
        return sorted(set(host.role for host in self.hosts))

    @property
    def static_roles(self):
        """Specific roles for this domain type

        To be overridden in subclasses
        """
        return ('master', )

    @property
    def extra_roles(self):
        return [role for role in self.roles if role not in self.static_roles]

    @classmethod
    def from_dict(cls, dct, config):
        from pytest_multihost.host import BaseHost

        domain_type = dct.pop('type', 'DEFAULT')
        domain_name = dct.pop('name')
        self = cls(config, domain_name, domain_type)

        for host_dict in dct.pop('hosts'):
            host = BaseHost.from_dict(host_dict, self)
            self.hosts.append(host)

        check_config_dict_empty(dct, 'domain %s' % domain_name)

        return self

    def to_dict(self):
        return {
            'type': self.type,
            'name': self.name,
            'hosts': [h.to_dict() for h in self.hosts],
        }

    def host_by_role(self, role):
        if self.hosts_by_role(role):
            return self.hosts_by_role(role)[0]
        else:
            raise LookupError(role)

    def hosts_by_role(self, role):
        return [h for h in self.hosts if h.role == role]

    @property
    def other_hosts(self):
        return self.hosts_by_role('other')

    def host_by_name(self, name):
        for host in self.hosts:
            if name in (host.hostname, host.external_hostname, host.shortname):
                return host
        raise LookupError(name)
