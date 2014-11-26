#
# Copyright (C) 2014 pytest-multihost contributors. See COPYING for license
#

import pytest

from pytest_multihost.config import Config, FilterError


@pytest.fixture
def config():
    return Config.from_dict({
        'domains': [
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
    })


def test_empty_filter(config):
    config.filter({})
    assert config.domains == []


def test_no_hosts_filter(config):
    config.filter([{'type': 'default', 'hosts': {}}])
    assert len(config.domains) == 1
    assert config.domains[0].hosts == []


def test_one_domain(config):
    config.filter([{'type': 'default', 'hosts': {
        'master': 1,
        'replica': 1,
        'extrarolem': 2,
    }}])
    assert len(config.domains) == 1
    assert [h.role for h in config.domains[0].hosts] == [
        'master', 'replica', 'extrarolem', 'extrarolem']


def test_two_domains(config):
    config.filter(
        [
            {
                'type': 'B',
                'hosts': {
                    'srv': 1,
                }
            },
            {
                'type': 'default',
                'hosts': {
                    'master': 1,
                    'replica': 1,
                    'extrarolem': 2,
                }
            }
        ],
    )
    assert len(config.domains) == 2
    assert [h.role for h in config.domains[0].hosts] == [
        'srv']
    assert [h.role for h in config.domains[1].hosts] == [
        'master', 'replica', 'extrarolem', 'extrarolem']


def test_bad_type(config):
    with pytest.raises(FilterError):
        config.filter([{
            'type': 'badtype',
            'hosts': {
                'srv': 1,
            }
        }])


def test_too_many_hosts(config):
    with pytest.raises(FilterError):
        config.filter([{
            'type': 'B',
            'hosts': {
                'srv': 2,
            }
        }])


def test_bad_many_host(config):
    with pytest.raises(FilterError):
        config.filter([{
            'type': 'B',
            'hosts': {
                'badhost': 1,
            }
        }])
