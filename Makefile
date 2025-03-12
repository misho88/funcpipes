PYTHON_SITE=$(shell python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
MODULE=funcpipes.py
GIT_BRANCH ?= "main"

checkout:
	git checkout $(GIT_BRANCH)
pull:
	git pull
install:
	install $(MODULE) $(PYTHON_SITE)
uninstall:
	rm -f $(PYTHON_SITE)/$(MODULE)
