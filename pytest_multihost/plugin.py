import json
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
        if 'BEAKERLIB' not in os.environ:
            raise exit('$BEAKERLIB not set, cannot use --with-beakerlib')

        with open(ns.multihost_config) as conffile:
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
    def __init__(self, confdict):
        self.confdict = confdict


class MultihostFixture(object):
    def __init__(self, config):
        self.config = config


def make_fixture(request, domains, config_class=Config):
    plugin = request.config.pluginmanager.getplugin('MultihostPlugin')
    if not plugin:
        pytest.skip('Multihost tests not configured')
    config = config_class.from_dict(plugin.confdict)
    try:
        config.filter(domains)
    except FilterError as e:
        pytest.skip('Not enough resources configured: %s' % e)
    return MultihostFixture(config)
