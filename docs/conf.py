# pylint: disable=all
import sys
from pathlib import Path
from importlib.metadata import metadata

import sphinx_rtd_theme


# -- Project information -----------------------------------------------------

package_metadata = metadata('drover')
project = package_metadata.get('name', '')
author = package_metadata.get('author', '')
version = package_metadata.get('version', '')
release = package_metadata.get('version', '')

if author:
    copyright = f'2020 {author} via Creative Commons Attribution 4.0 International License'
else:
    copyright = 'Creative Commons Attribution 4.0 International License'

epub_description = package_metadata.get('description', '')


# -- General configuration ---------------------------------------------------

default_role = 'py:obj'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx_rtd_theme',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

html_theme_path = ['_themes']

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']


for path in templates_path + html_static_path:
    path = Path(path)
    path.mkdir(exist_ok=True)
