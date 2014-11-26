#
# Copyright (C) 2013  Red Hat
# Copyright (C) 2014  pytest-multihost contributors
# See COPYING for license
#

import tempfile
import shutil


def check_config_dict_empty(dct, name):
    """Ensure that no keys are left in a configuration dict"""
    if dct:
        raise ValueError('Extra keys in confuguration for %s: %s' %
                         (name, ', '.join(dct)))


def shell_quote(string):
    """Quotes a string for the Bash shell"""
    return "'" + string.replace("'", "'\\''") + "'"


class TempDir(object):
    """Handle for a temporary directory that's deleted on garbage collection"""
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix='multihost_tests.')

    def __del__(self):
        shutil.rmtree(self.path)
