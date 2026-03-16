.PHONY: all
all: build install

.PHONY: build
build:
	./build.sh

.PHONY: install
install:
	./install.sh
