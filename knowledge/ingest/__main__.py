"""Allow ``python -m knowledge.ingest`` to invoke the CLI directly."""

from knowledge.ingest.cli import main

raise SystemExit(main())
