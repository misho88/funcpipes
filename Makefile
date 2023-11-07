GIT_BRANCH ?= "main"

checkout:
	git checkout $(GIT_BRANCH)
pull:
	git pull
install:
	./setup.py build
	./setup.py install
uninstall:
	pip3 uninstall funcpipes
