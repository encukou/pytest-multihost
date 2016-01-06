#
# Copyright (C) 2014 pytest-multihost contributors. See COPYING for license
#

import json
import os
import traceback

import pytest

from pytest_multihost.config import Config, FilterError

try:
    import yaml
except ImportError:
    yaml = None


def pytest_addoption(parser):
    parser.addoption(
        '--multihost-config', dest="multihost_config",
        help="Site configuration for multihost tests")


@pytest.mark.tryfirst
def pytest_load_initial_conftests(args, early_config, parser):
    ns = early_config.known_args_namespace
    if ns.multihost_config:
        try:
            conffile = open(ns.multihost_config)
        except IOError as e:
            raise exit('Unable to open multihost configuration file %s: %s\n'
                       'Please check path of configuration file and retry.'
                       % (ns.multihost_config, e.args[1]))
        with conffile:
            if yaml:
                confdict = yaml.safe_load(conffile)
            else:
                try:
                    confdict = json.load(conffile)
                except Exception:
                    traceback.print_exc()
                    raise exit(
                        'Could not load %s. If it is a YAML file, you need '
                        'PyYAML installed.' % ns.multihost_config)
        plugin = MultihostPlugin(confdict)
        pluginmanager = early_config.pluginmanager.register(
            plugin, 'MultihostPlugin')


class MultihostPlugin(object):
    """The Multihost plugin

    The plugin is available as pluginmanager.getplugin('MultihostPlugin'),
    and its presence indicates that multihost testing has been configured.
    """
    def __init__(self, confdict):
        self.confdict = confdict


class MultihostFixture(object):
    """A fixture containing the multihost testing configuration

    Contains the `config`; other attributes may be added to it for convenience.
    """
    def __init__(self, config, request):
        self.config = config
        self._pytestmh_request = request

    def install(self):
        """Call install()/uninstall() for the class this fixture is used on

        This function is DEPRECATED.
        """
        request = self._pytestmh_request
        cls = request.cls
        install = getattr(cls, 'install', None)
        if install:
            request.addfinalizer(lambda: cls().uninstall(self))
            cls().install(self)
        return self


def make_multihost_fixture(request, descriptions, config_class=Config,
                           _config=None):
    """Create a MultihostFixture, or skip the test

    :param request: The Pytest request object
    :param descriptions:
        Descriptions of wanted domains (see README or Domain.filter)
    :param config_class: Custom Config class to use
    :param _config:
        Config to be used directly.
        Intended mostly for testing the plugin itself.

    Skips the test if there are not enough resources configured.
    """
    if _config is None:
        plugin = request.config.pluginmanager.getplugin('MultihostPlugin')
        if not plugin:
            pytest.skip('Multihost tests not configured')
        confdict = plugin.confdict
        _config = config_class.from_dict(confdict)
    try:
        _config.filter(descriptions)
    except FilterError as e:
        pytest.skip('Not enough resources configured: %s' % e)
    return MultihostFixture(_config, request)
