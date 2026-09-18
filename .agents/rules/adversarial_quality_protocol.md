# Mandatory Adversarial Quality Process & Git Synchronization Protocol

## Scope
This rule applies unconditionally to every change made to the live codebase across all engines, runners, scripts, and clients.

## Protocol Requirements
1. **Adversarial Regression Testing:**
   - Any time code is modified, the agent must run regression testing (targeted unit tests and the Bulletproof Master Invariant Harness `tests/run_bulletproof_harness.py`).
   - All tests must pass with 100% success before any change is finalized.
2. **Production Runtime Verification:**
   - Confirm that background daemons, logs, and sentry monitors are operating cleanly without syntax errors, missing imports, or runtime exceptions.
3. **Immediate Git Synchronization:**
   - Immediately stage, commit, and push the verified changes to the private remote repository (`gitlab main`).
