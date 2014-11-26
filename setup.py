#!/usr/bin/python2
#
# Copyright (C) 2014 pytest-multihost contributors. See COPYING for license
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
