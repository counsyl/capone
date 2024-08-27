# 3.1.0

- No functional changes: added support targets and refactored tests and dependencies.

## Major

- Support Django 3.2 and 4.2.
- Add support for Python 3.8 and 3.9.
- Cope with psycopg2 bug: only 2.8 is supported through Django 2.2, but 2.9 is supported for higher Django versions.
- Parameterize test suite on USE_TZ to confirm Capone works for both True and False.
- Remove unneeded dependency `enum34`.
- Refactor to use `django.utils.timezone`.

## Minor

- Convert tests to Pytest style.
- Default in tests to USE_TZ == True.
- Remove remaining Python 2 compatibility shims.
- Unpin lots of test dependencies.

# 3.0.0

- Drop Django < 1.11 support.
- Add Django 2.2 support.
- Fix some circularities and inefficiencies in the Makefile
- "Cap" some older dev dependencies whose more recent versions don't work with Capone's current version.


# 2.0.3

This version is a mis-numbered version of 3.0.0 that was released accidentally.
