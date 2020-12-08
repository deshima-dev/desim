# Project information
project = "deshima-sensitivity"
copyright = "2018-2020 DESHIMA software team"
author = "Akira Endo"
release = "0.2.6"


# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
]
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# Options for HTML output
html_static_path = ["_static"]
html_logo = "_static/logo.png"
html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "github_url": "https://github.com/deshima-dev/deshima-sensitivity/",
}
