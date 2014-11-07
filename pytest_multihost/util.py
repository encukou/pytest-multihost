# Authors:
#   Petr Viktorin <pviktori@redhat.com>
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


def check_config_dict_empty(dct, name):
    """Ensure that no keys are left in a configuration dict"""
    if dct:
        raise ValueError('Extra keys in confuguration for %s: %s' %
                         (name, ', '.join(dct)))


def shell_quote(string):
    return "'" + string.replace("'", "'\\''") + "'"


class TempDir(object):
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix='multihost_tests.')

    def __del__(self):
        shutil.rmtree(self.path)
