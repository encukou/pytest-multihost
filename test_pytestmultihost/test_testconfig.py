#
# Copyright (C) 2013  Red Hat
# Copyright (C) 2014  pytest-multihost contributors
# See COPYING for license
#

import json
import copy

from pytest_multihost import config

DEFAULT_OUTPUT_DICT = {
    "test_dir": "/root/multihost_tests",
    "ssh_key_filename": "~/.ssh/id_rsa",
    "ssh_password": None,
    'ssh_username': 'root',
    'ipv6': False,
    "domains": [],
}

DEFAULT_INPUT_DICT = {
    'domains': [],
}


def extend_dict(defaults, *others, **kwargs):
    result = dict(defaults)
    for other in others:
        result.update(other)
    result.update(kwargs)
    return copy.deepcopy(result)


class CheckConfig(object):
    def check_config(self, conf):
        pass

    def get_input_dict(self):
        return extend_dict(DEFAULT_INPUT_DICT, self.extra_input_dict)

    def get_output_dict(self):
        return extend_dict(DEFAULT_OUTPUT_DICT, self.extra_output_dict)

    def test_dict_to_dict(self):
        conf = config.Config.from_dict(self.get_input_dict())
        assert self.get_output_dict() == conf.to_dict()
        self.check_config(conf)

    def test_dict_roundtrip(self):
        conf = config.Config.from_dict(self.get_output_dict())
        assert self.get_output_dict() == conf.to_dict()
        self.check_config(conf)


class TestEmptyConfig(CheckConfig):
    extra_input_dict = {}
    extra_output_dict = {}


class TestMinimalConfig(CheckConfig):
    extra_input_dict = dict(
        domains=[
            dict(name='adomain.test', hosts=[
                dict(name='master', ip='192.0.2.1'),
            ]),
        ],
    )
    extra_output_dict = dict(
        domains=[
            dict(
                type='default',
                name="adomain.test",
                hosts=[
                    dict(
                        name='master.adomain.test',
                        ip="192.0.2.1",
                        external_hostname="master.adomain.test",
                        role="master",
                    ),
                ],
            ),
        ],
    )

    def check_config(self, conf):
        assert len(conf.domains) == 1
        assert conf.domains[0].name == 'adomain.test'
        assert conf.domains[0].type == 'default'
        assert len(conf.domains[0].hosts) == 1

        master = conf.domains[0].host_by_role('master')
        assert master == conf.domains[0].hosts[0]
        assert master.hostname == 'master.adomain.test'
        assert master.role == 'master'

        assert conf.domains[0].hosts_by_role('replica') == []


class TestComplexConfig(CheckConfig):
    extra_input_dict = dict(
        domains=[
            dict(name='adomain.test', hosts=[
                dict(name='master', ip='192.0.2.1', role='master'),
                dict(name='replica1', ip='192.0.2.2', role='replica'),
                dict(name='replica2', ip='192.0.2.3', role='replica',
                              external_hostname='r2.adomain.test'),
                dict(name='client1', ip='192.0.2.4', role='client'),
                dict(name='client2', ip='192.0.2.5', role='client',
                              external_hostname='c2.adomain.test'),
                dict(name='extra', ip='192.0.2.6', role='extrarole'),
                dict(name='extram1', ip='192.0.2.7', role='extrarolem'),
                dict(name='extram2', ip='192.0.2.8', role='extrarolem',
                              external_hostname='e2.adomain.test'),
            ]),
            dict(name='bdomain.test', type='B', hosts=[
                dict(name='srv', ip='192.0.2.33', role='srv'),
            ]),
            dict(name='adomain2.test', hosts=[
                dict(name='master.adomain2.test', ip='192.0.2.65'),
            ]),
        ],
    )
    extra_output_dict = dict(
        domains=[
            dict(
                type='default',
                name="adomain.test",
                hosts=[
                    dict(
                        name='master.adomain.test',
                        ip="192.0.2.1",
                        external_hostname="master.adomain.test",
                        role="master",
                    ),
                    dict(
                        name='replica1.adomain.test',
                        ip="192.0.2.2",
                        external_hostname="replica1.adomain.test",
                        role="replica",
                    ),
                    dict(
                        name='replica2.adomain.test',
                        ip="192.0.2.3",
                        external_hostname="r2.adomain.test",
                        role="replica",
                    ),
                    dict(
                        name='client1.adomain.test',
                        ip="192.0.2.4",
                        external_hostname="client1.adomain.test",
                        role="client",
                    ),
                    dict(
                        name='client2.adomain.test',
                        ip="192.0.2.5",
                        external_hostname="c2.adomain.test",
                        role="client",
                    ),
                    dict(
                        name='extra.adomain.test',
                        ip="192.0.2.6",
                        external_hostname="extra.adomain.test",
                        role="extrarole",
                    ),
                    dict(
                        name='extram1.adomain.test',
                        ip="192.0.2.7",
                        external_hostname="extram1.adomain.test",
                        role="extrarolem",
                    ),
                    dict(
                        name='extram2.adomain.test',
                        ip="192.0.2.8",
                        external_hostname="e2.adomain.test",
                        role="extrarolem",
                    ),
                ],
            ),
            dict(
                type="B",
                name="bdomain.test",
                hosts=[
                    dict(
                        name='srv.bdomain.test',
                        ip="192.0.2.33",
                        external_hostname="srv.bdomain.test",
                        role="srv",
                    ),
                ],
            ),
            dict(
                type='default',
                name="adomain2.test",
                hosts=[
                    dict(
                        name='master.adomain2.test',
                        ip="192.0.2.65",
                        external_hostname="master.adomain2.test",
                        role="master",
                    ),
                ],
            ),
        ],
    )

    def check_config(self, conf):
        assert len(conf.domains) == 3
        main_dom = conf.domains[0]
        (client1, client2, extra, extram1, extram2, master,
         replica1, replica2) = sorted(main_dom.hosts, key=lambda h: h.role)
        assert main_dom.name == 'adomain.test'
        assert main_dom.type == 'default'

        assert sorted(main_dom.static_roles) == ['master']
        assert sorted(main_dom.roles) == [
            'client', 'extrarole', 'extrarolem', 'master', 'replica']
        assert sorted(main_dom.extra_roles) == [
            'client', 'extrarole', 'extrarolem', 'replica']

        assert main_dom.hosts_by_role('replica') == [replica1, replica2]
        assert main_dom.hosts_by_role('extrarolem') == [extram1, extram2]
        assert main_dom.host_by_role('extrarole') == extra

        assert extra.ip == '192.0.2.6'
        assert extram2.hostname == 'extram2.adomain.test'
        assert extram2.external_hostname == 'e2.adomain.test'

        ad_dom = conf.domains[1]
        assert ad_dom.roles == ['srv']
        assert ad_dom.extra_roles == ['srv']
