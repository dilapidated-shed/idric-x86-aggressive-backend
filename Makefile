PYTHON ?= python3
IDRIC_REPO ?= $(CURDIR)/.idric
IDRIC_COMPILER_REF ?= $(shell tr -d '\n' < IDRIC_COMPILER_REF)
IDRIC_COMPLEX_CORPUS ?= $(IDRIC_REPO)/_/fixtures/complex-projective/float32.json
COMPLEX_PROJECTIVE_ARTIFACTS ?= $(CURDIR)/build/complex-projective

.PHONY: unit ci-unit integration ci complex-projective complex-projective-thin-debian

unit:
	$(PYTHON) -m unittest discover -s tests -v

ci-unit:
	EDRIC_COMPILER="$(IDRIC_REPO)/edric" \
	EDRIC_R128_SOURCE="$(IDRIC_REPO)/examples/mathematical-one-step/R128Pipeline.idric" \
	$(PYTHON) scripts/run_test_suite.py --fail-on-skip

integration:
	IDRIC_REPO="$(IDRIC_REPO)" \
	IDRIC_COMPILER_REF="$(IDRIC_COMPILER_REF)" \
	scripts/run_checked_integration.sh

complex-projective:
	$(PYTHON) scripts/run_complex_projective_acceptance.py \
		--corpus "$(IDRIC_COMPLEX_CORPUS)" \
		--artifacts "$(COMPLEX_PROJECTIVE_ARTIFACTS)"

complex-projective-thin-debian: complex-projective
	scripts/run_complex_projective_thin_debian.sh "$(COMPLEX_PROJECTIVE_ARTIFACTS)"

ci: ci-unit integration
