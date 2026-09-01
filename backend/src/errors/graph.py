"""Errors raised by ``utils.graph``'s topological sort."""


class GraphCycleError(ValueError):
    """The graph has at least one cycle, so no topological order exists."""


class UnknownNodeError(ValueError):
    """An edge references a node id that isn't in the graph."""
