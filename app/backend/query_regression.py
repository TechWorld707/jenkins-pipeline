"""Bounded, opt-in CPU-query regression for the JIRA-002 learning image."""
import os
import threading
import time
from contextlib import nullcontext

from sqlalchemy import text

# No customer data, schema changes, locks or writes. PostgreSQL computes hashes
# instead of doing useful work: a deliberately wasteful post-deployment query.
QUERY = """/* JIRA-002: unnecessary enquiry preflight aggregation */
SELECT count(*) FROM generate_series(1, 10000000) AS n
WHERE md5(md5(n::text)) LIKE 'a%'
"""


class QueryRegression:
    def __init__(self, enabled=None, clock=time.monotonic):
        self.enabled = (os.getenv('QUERY_REGRESSION_DRILL', 'false') == 'true'
                        if enabled is None else enabled)
        self.clock = clock
        self.deadline = clock() + 1800
        self.slot = threading.BoundedSemaphore(1)

    def run(self, db, record, tracer=None):
        if not self.enabled or self.clock() >= self.deadline:
            return
        # At most one drill query per backend process. Skip overlapping requests
        # rather than creating a growing workload or exhausting the pool.
        if not self.slot.acquire(blocking=False):
            return
        started = self.clock()
        outcome = 'failed'
        try:
            with (tracer.start_as_current_span('enquiry.preflight.aggregate')
                  if tracer is not None else nullcontext()):
                record('enquiry.preflight.started', exercise='JIRA-002')
                # SET LOCAL settings disappear at commit/rollback. The timeout
                # is enforced by PostgreSQL even if the client disconnects.
                previous_timeout = db.execute(text('SHOW statement_timeout')).scalar_one()
                db.execute(text("SELECT set_config('statement_timeout', '8000', true)"))
                db.execute(text(QUERY)).scalar_one()
                db.execute(text("SELECT set_config('statement_timeout', :previous, true)"),
                           {'previous': previous_timeout})
                outcome = 'succeeded'
        finally:
            self.slot.release()
            record('enquiry.preflight.completed', exercise='JIRA-002',
                   outcome=outcome, duration_ms=round((self.clock() - started) * 1000))


regression = QueryRegression()
