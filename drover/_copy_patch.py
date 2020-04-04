"""Conditional patches for Python's `copy` module"""
import copy
import re
import sys

if sys.version_info < (3, 7):
    # See: <https://stackoverflow.com/questions/6279305/typeerror-cannot-deepcopy-this-pattern-object>
    copy._deepcopy_dispatch[type(re.compile(''))] = lambda r, _: r # pylint: disable=protected-access
