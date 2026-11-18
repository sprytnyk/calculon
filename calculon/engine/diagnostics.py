"""Calculation messages with their arguments kept separate for translation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    template: str
    args: tuple[object, ...] = ()

    def render(self, template: str | None = None, **kwargs: object) -> str:
        return (template or self.template).format(*self.args, **kwargs)


class DiagnosticError(Exception):
    def __init__(self, template: str, *args: object):
        self.diagnostic = Diagnostic(template, args)
        super().__init__(self.diagnostic.render())
