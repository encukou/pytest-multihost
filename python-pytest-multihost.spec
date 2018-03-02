%if 0%{?rhel}
%global with_python3 0
%else
%global with_python3 1
%endif

%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

%global srcname pytest-multihost
%global modulename pytest_multihost
%global srcversion 3.0
%global versionedname %{srcname}-%{srcversion}

Name: python-%{srcname}
Version: %{srcversion}
Release: 1%{?dist}
Summary: Utility for writing multi-host tests for pytest

License: GPLv3+
URL: https://github.com/encukou/%{srcname}

Source0: https://github.com/encukou/%{srcname}/archive/v%{srcversion}.tar.gz#/%{versionedname}.tar.gz

BuildArch: noarch
BuildRequires: python-devel
BuildRequires: python-setuptools
BuildRequires: pytest
%if 0%{?with_python3}
BuildRequires: python3-devel
BuildRequires: python3-setuptools
BuildRequires: python3-pytest
%endif

Requires: python
Requires: pytest >= 2.4.0

# Should use python_provide macros, but those won't work in older EPEL
Provides: python2-%{srcname}

%if 0%{?fedora}
# These are not *strictly* required, but are part of the default workflow.
Requires: PyYAML
Requires: python-paramiko
%endif


%description
Allows pytest tests to run commands on several machines.
The machines to run on are described on the command line, the tests
specify how many machines they need and commands/checks to run on them.

%if 0%{?with_python3}
%package -n python3-%{srcname}
Summary: Utility for writing multi-host tests for pytest

Requires: python3
Requires: python3-pytest

%description -n python3-%{srcname}
Allows pytest tests to run commands on several machines.
The machines to run on are described on the command line, the tests
specify how many machines they need and commands/checks to run on them.

%endif


%prep
%setup -q -n %{versionedname}

%if 0%{?with_python3}
echo %{py3dir}
rm -rf %{py3dir}
cp -a . %{py3dir}
%endif


%build
%{__python2} setup.py build

%if 0%{?with_python3}
pushd %{py3dir}
%{__python3} setup.py build
popd
%endif

%check
# Do not run the test that needs passwordless SSH to localhost set up
%{__python2} -m pytest -m "not needs_ssh"

%if 0%{?with_python3}
pushd %{py3dir}
%{__python3} -m pytest -m "not needs_ssh"
popd
%endif

%install
%{__python2} setup.py install --skip-build --root %{buildroot}
%if 0%{?with_python3}
%py_byte_compile %{__python2} %{buildroot}%{python_sitelib}/%{srcname}
%else
# py_byte_compile is only defined in python3-devel
%{__python2} -m compileall %{buildroot}%{python_sitelib}/%{srcname}
%endif

%if 0%{?with_python3}
pushd %{py3dir}
%{__python3} setup.py install --skip-build --root %{buildroot}
%py_byte_compile %{__python3} %{buildroot}%{python3_sitelib}/%{srcname}
popd
%endif

%files
%if 0%{?rhel} && 0%{?rhel} <= 6
%doc COPYING
%else
%license COPYING
%endif
%doc README.rst
%{python_sitelib}/%{modulename}-%{version}-py2.?.egg-info
%{python_sitelib}/%{modulename}/

%if 0%{?with_python3}
%files -n python3-%{srcname}
%license COPYING
%doc README.rst
%{python3_sitelib}/%{modulename}-%{version}-py%{python3_version}.egg-info
%{python3_sitelib}/%{modulename}/
%endif


%changelog
* Fri Mar 02 2018 Petr Viktorin <encukou@gmail.com> - 3.0-1
- Do not add extra newlines to stdin contents
- Remove forgotten debug print

* Wed Apr 12 2017 Petr Viktorin <encukou@gmail.com> - 2.0-1
- Add support to run commands in background
- Fix several issues around quoting, background processes, and encoding

* Wed Apr 12 2017 Petr Viktorin <encukou@gmail.com> - 1.1.1-1
- Upstream packaging changes

* Thu Apr 22 2016 Petr Viktorin <encukou@gmail.com> - 1.1-1
- Much improved support for Windows hosts (thanks to Niranjan MR)

* Thu Feb 03 2016 Petr Viktorin <encukou@gmail.com> - 1.0-1
- Add error handling in config file handling (thanks to Abhijeet Kasurde)
- Add support to specify username/password per host (thanks to Niranjan MR)
- Add ability to reset the SSH connection (thanks to Scott Poore)

* Thu Nov 26 2015 Petr Viktorin <encukou@gmail.com> - 0.9-1
- Add more file manipulation functions (thanks to Abhijeet Kasurde)
- Slightly improve Python 3 support

* Tue Nov 10 2015 Petr Viktorin <encukou@gmail.com> - 0.8-1
- Fix creating multiple Configs from one dict

* Tue Nov 10 2015 Petr Viktorin <encukou@gmail.com> - 0.7-1
- Add compatibility with Python 2.6

* Tue Nov 10 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-4
- Rebuilt for https://fedoraproject.org/wiki/Changes/python3.5
-
* Mon Mar 2 2015 Petr Viktorin <encukou@gmail.com> - 0.6-3
- Don't use licence macro on RHEL 6

* Mon Mar 2 2015 Petr Viktorin <encukou@gmail.com> - 0.6-3
- Don't use licence macro on RHEL 6

* Tue Jan 27 2015 Petr Viktorin <encukou@gmail.com> - 0.6-2
- Also install COPYING as a license on the Python 3 version

* Mon Jan 26 2015 Petr Viktorin <encukou@gmail.com> - 0.6-1
- Run tests
- Install COPYING as a license

* Wed Nov 26 2014 Petr Viktorin <encukou@gmail.com> - 0.5-1
- Packaging fixes

* Wed Nov 26 2014 Petr Viktorin <encukou@gmail.com> - 0.4-2
- Specify minimum version of pytest

* Wed Nov 26 2014 Petr Viktorin <encukou@gmail.com> - 0.4-1
- Ensure backwards compatibility with FreeIPA's root-only logins

* Wed Nov 26 2014 Petr Viktorin <encukou@gmail.com> - 0.3-1
- "Upstream" packaging fixes

* Mon Nov 10 2014 Petr Viktorin <encukou@gmail.com> - 0.2-1
- better extensibility
- bug fixes

* Mon Nov 10 2014 Petr Viktorin <encukou@gmail.com> - 0.1-1
- initial public version of package
