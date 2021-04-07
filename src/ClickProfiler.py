import sys
import click
import cProfile
from pstats import Stats


class ClickProfiler:
    """cProfile wrapper for Click. Modeled after ProfilerMiddleware."""

    def __init__(
        self,
        stream=sys.stdout,
        sort_by=("time", "calls"),
        restrictions=(),
    ):
        self.stream = stream
        self.sort_by = sort_by
        self.restrictions = restrictions
        self.pr = cProfile.Profile()

    def profile(self, ctx: click.Context):
        self.pr.enable()
        ctx.call_on_close(self.on_close)

    def on_close(self):
        self.pr.disable(),
        stats = Stats(self.pr)
        stats.sort_stats(*self.sort_by)
        print("-" * 80, file=self.stream)
        stats.print_stats(*self.restrictions)
        print("-" * 80 + "\n", file=self.stream)
