import sys

import structlog

from website import betterdb

logger = structlog.get_logger()


class DryRunCommandMixin:
    """Command for working with dry runs.
    Implement _handle_mutatable,
    which should raise or return an exist code.
    If --dry-run is used, an error is raised, or a > 0 code is returned,
    the transaction is rolled back.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Use a dry run (roll transaction back).",
        )

    def handle(self, *args, **options):
        with betterdb.transaction(reraise_rollback=False):
            code = self._handle_mutatable(*args, **options) or 0
            if options.get("dry_run") or code > 0:
                logger.info("rolling back", reason="dry run")
                raise betterdb.Rollback()
        sys.exit(code)

    def _handle_mutatable(self, *args, **options) -> int:
        raise NotImplemented
