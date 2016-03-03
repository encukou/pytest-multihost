# This automates the maintainer's build & release process

PROJECT=pytest-multihost
FEDORA_PROJECT=python-${PROJECT}
VERSION=$(shell python -c "import setup; print(setup.setup_args['version'])")
VERSIONEDNAME=${PROJECT}-${VERSION}
TARBALLNAME=${VERSIONEDNAME}.tar.gz
FEDORA_USERNAME=$(shell whoami)

all: wheel
	python setup.py sdist

install:
	python setup.py install

tarball: ${TARBALLNAME}

${TARBALLNAME}:
	if [ -n "$$(git status --porcelain)" ]; then \
		echo "Changes not commited to Git"; \
		exit 1; \
	fi
	git archive HEAD -o ${TARBALLNAME} --prefix ${VERSIONEDNAME}/

upload-fedorahosted: tarball
	scp ${TARBALLNAME} fedorahosted.org:${FEDORA_PROJECT}

upload-pypi:
	python setup.py sdist upload
	python setup.py bdist_wheel upload

upload-fedorapeople: srpm
	SRPMNAME=$$(ls rpmbuild/SRPMS); \
	scp rpmbuild/SRPMS/$$SRPMNAME fedorapeople.org:public_html/srpms

upload: upload-fedorahosted upload-pypi upload-fedorapeople

copr-build: srpm
	copr-cli build pviktori/pytest-plugins rpmbuild/SRPMS/*.src.rpm

wheel:
	python setup.py bdist_wheel

srpm: tarball
	rm -rvf rpmbuild
	mkdir -p rpmbuild/SOURCES
	mkdir -p rpmbuild/SRPMS
	cp ${TARBALLNAME} rpmbuild/SOURCES/
	rpmbuild --define "_topdir ${PWD}/rpmbuild" -bs ${FEDORA_PROJECT}.spec

mock: srpm
	cp $(TARBALLNAME) $$(rpm -E '%{_topdir}')/SOURCES
	mock rebuild rpmbuild/SRPMS/*.src.rpm

release: upload

.PHONY: all install ${TARBALLNAME} tarball upload upload-fedorahosted upload-pypi wheel srpm copr-build release
