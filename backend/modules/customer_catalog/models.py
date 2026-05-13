"""Re-export the existing CustomerProductSelection ORM class.

The canonical model lives in `modules.catalog.models` (defined in Phase 6
groundwork commits) and is referenced by:
  - modules.import_jobs.service  — stale detection on sync job finalize
  - tests.conftest                — cleanup
  - tests.test_stale_detection    — direct integration test

This module's job is to add the API surface (routes/schemas) on top of
the existing model. The re-export keeps `from modules.customer_catalog.models
import CustomerProductSelection` valid for any future imports.
"""
from modules.catalog.models import CustomerProductSelection  # noqa: F401
