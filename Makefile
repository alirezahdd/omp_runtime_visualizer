# OMPT Runtime Visualizer Tool
# Builds an OMPT tool using LLVM's OpenMP (requires libomp, not libgomp)

# Configuration
CC = gcc
# Set the LLVM version explicitly or auto-detect
# Uncomment the next line to set a specific LLVM version
# LLVM_VERSION = 18
ifndef LLVM_VERSION
LLVM_VERSION = $(shell ls /usr/bin/llvm-config-* 2>/dev/null | sed 's/.*-//' | sort -n | tail -1)
endif
ifeq ($(strip $(LLVM_VERSION)),)
LLVM_VERSION = 18
endif
# LLVM_PATH = /usr/lib/llvm-$(LLVM_VERSION)
LLVM_PATH = $(shell llvm-config-$(LLVM_VERSION) --prefix)
OMP_INCLUDE = $(shell dpkg -L libomp-$(LLVM_VERSION)-dev | grep omp-tools.h)
OMP_TOOL_INCLUDE = $(shell dpkg -L libomp-$(LLVM_VERSION)-dev | grep omp.h)
OPENMP_LIB = $(LLVM_PATH)/lib
OMPT_LIB = visualizer_tool.so
SRC_DIR = src
LIB_DIR = lib

OMPT_CFLAGS = -fopenmp -fPIC -g -O3 -include $(OMP_INCLUDE) -include $(OMP_TOOL_INCLUDE)
OMPT_LDFLAGS = -fopenmp -shared -L$(OPENMP_LIB) -lomp

# Build targets
all: $(OMPT_LIB) setup-script

$(OMPT_LIB): $(SRC_DIR)/visualizer_tool.c
	@mkdir -p $(LIB_DIR)
	$(CC) $(OMPT_CFLAGS) $(OMPT_LDFLAGS) -o $(LIB_DIR)/$@ $<
	@echo "✔ Build successful: $(LIB_DIR)/$@"

clean:
	rm -f $(LIB_DIR)/$(OMPT_LIB)
	rm -f env_setup.sh

# Utility targets
check-deps:
	@command -v $(CC) >/dev/null || { echo "Error: $(CC) not found"; exit 1; }
	@if [ -z "$(OMP_INCLUDE)" ]; then echo "Error: Could not find omp-tools.h. Is libomp-$(LLVM_VERSION)-dev installed?"; exit 1; fi
	@test -f $(OMP_INCLUDE) || { echo "Error: omp-tools.h not found at $(OMP_INCLUDE)"; exit 1; }
	@if [ -z "$(OMP_TOOL_INCLUDE)" ]; then echo "Error: Could not find omp.h. Is libomp-$(LLVM_VERSION)-dev installed?"; exit 1; fi
	@test -f $(OMP_TOOL_INCLUDE) || { echo "Error: omp.h not found at $(OMP_TOOL_INCLUDE)"; exit 1; }
	@test -d $(OPENMP_LIB) || { echo "Error: LLVM OpenMP library not found at $(OPENMP_LIB)"; exit 1; }
	@echo "All dependencies available"

install-deps:
	sudo apt update
	sudo apt install -y gcc build-essential \
		llvm-$(LLVM_VERSION)-dev libomp-$(LLVM_VERSION)-dev \
		python3 python3-pip
	pip3 install matplotlib numpy pandas

setup-script:
	@echo "Generating environment setup script..."
	@echo '#!/bin/bash' > env_setup.sh
	@echo 'export LD_LIBRARY_PATH=$(OPENMP_LIB):$$LD_LIBRARY_PATH' >> env_setup.sh
	@echo 'export OMP_TOOL_LIBRARIES=$(shell pwd)/$(LIB_DIR)/$(OMPT_LIB)' >> env_setup.sh
	@chmod +x env_setup.sh
	@echo "✔ Environment setup script created: env_setup.sh"

info:
	@echo "Compiler: $(CC)"
	@echo "LLVM Version: $(LLVM_VERSION)"
	@echo "OpenMP Library: $(OPENMP_LIB)"
	@echo "CFLAGS: $(OMPT_CFLAGS)"
	@echo "LDFLAGS: $(OMPT_LDFLAGS)"

.PHONY: all clean check-deps install-deps info setup-script
