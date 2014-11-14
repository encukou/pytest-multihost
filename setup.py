#!/usr/bin/python2
# Copyright (C) 2014  Red Hat
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
#

from setuptools import setup

setup_args = dict(
    name = "pytest-multihost",
    version = "0.2",
    license = "GPL",
    author = "Petr Viktorin",
    author_email = "pviktori@redhat.com",
    packages = ["pytest_multihost"],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Quality Assurance',
    ],
    install_requires=['pytest'],  # (paramiko & PyYAML are suggested)
    entry_points = {
        'pytest11': [
            'multihost = pytest_multihost.plugin',
        ],
    },
)

if __name__ == '__main__':
    setup(**setup_args)
