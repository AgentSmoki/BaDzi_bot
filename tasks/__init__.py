"""TaskIQ worker package.

The worker is launched with ``taskiq worker tasks.broker:broker``
and that import alone won't bring in the task modules — TaskIQ only
sees a task once its module is imported. We do that here, by side
effect, so the worker registry is complete the moment the broker is
loaded.

Add new task modules below as they're created.
"""

# Side-effect imports: each submodule registers its tasks on the
# shared broker via @broker.task. Order doesn't matter.
from tasks import consultation as _consultation  # noqa: F401  (registers tasks)
from tasks import master_meeting as _master_meeting  # noqa: F401  (Wave 5)
