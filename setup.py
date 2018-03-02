#!/usr/bin/python2
#
# Copyright (C) 2014 pytest-multihost contributors. See COPYING for license
#

from setuptools import setup
import io

with io.open('README.rst', 'rt', encoding='utf-8') as f:
    readme_contents = f.read()

setup_args = dict(
    name = "pytest-multihost",
    version = "3.0",
    description = "Utility for writing multi-host tests for pytest",
    long_description = readme_contents,
    url = "https://pagure.io/python-pytest-multihost",
    license = "GPL",
    author = "Petr Viktorin",
    author_email = "pviktori@redhat.com",
    packages = ["pytest_multihost"],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX',
        'Framework :: Pytest',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Quality Assurance',
    ],
    install_requires=['pytest>=2.4.0'],  # (paramiko & PyYAML are suggested)
    entry_points = {
        'pytest11': [
            'multihost = pytest_multihost.plugin',
        ],
    },
)

if __name__ == '__main__':
    setup(**setup_args)
