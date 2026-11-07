#!/usr/bin/env bash
# =============================================================================
# Pipeline policy guard (SEC-08)
# Fails the pipeline if someone tries to weaken a security gate inside the
# workflow files, e.g. making a scanner "never fail" or removing a stage.
#
# This is a DETECTIVE control. The PREVENTIVE controls are:
#   - CODEOWNERS on .github/** + branch protection (review required)
#   - the delivery gates living in a SEPARATE repository (auto-monitor-deployment)
# =============================================================================
set -euo pipefail

WF_DIR=".github/workflows"
fail=0

# 1) Patterns that turn a blocking check into a non-blocking one.
patterns=(
  'continue-on-error:[[:space:]]*true'
  '--exit-code[ =]0([^0-9]|$)'
  'exit-code:[[:space:]]*["'"'"']?0["'"'"']?[[:space:]]*$'
  'soft_fail:[[:space:]]*true'
  '--soft-fail'
  '\|\|[[:space:]]*true'
  '--no-verify'
)

for p in "${patterns[@]}"; do
  if hits=$(grep -nE -- "$p" "$WF_DIR"/*.yml 2>/dev/null); then
    echo "::error::Security gate weakened - forbidden pattern '$p':"
    echo "$hits"
    fail=1
  fi
done

# 2) Every security stage must still be wired into the CI orchestrator.
for stage in ci_validate.yml ci_test.yml ci_sast.yml ci_sca.yml ci_build.yml; do
  if ! grep -q "uses: ./.github/workflows/${stage}" "$WF_DIR/ci_main.yml"; then
    echo "::error::Stage ${stage} was removed from ci_main.yml"
    fail=1
  fi
done

# 3) The build must still depend on the security stages.
if ! grep -qE 'needs:[[:space:]]*\[test, sast, sca\]' "$WF_DIR/ci_main.yml"; then
  echo "::error::Build no longer waits for test + sast + sca"
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "Pipeline policy guard FAILED - see errors above."
  exit 1
fi
echo "Pipeline policy guard passed - no security gate was weakened."
