"""Calculon: a natural-language notepad calculator."""

try:
    from ._version import __version__
except ImportError:  # running from a checkout without a tag build
    __version__ = "0.0.0.dev0"

__author__ = "https://sprytnyk.dev"
__repo__ = "sprytnyk/calculon"  # on GitHub

__all__ = ["__author__", "__repo__", "__version__"]
