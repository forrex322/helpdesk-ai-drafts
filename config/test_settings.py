"""Settings for pytest: the real settings plus the values a test run cannot get from the environment."""

import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key")

from .settings import *  # noqa: E402, F403
