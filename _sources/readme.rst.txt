deshima-sensitivity
===================

|PyPI| |Python| |Test| |License| |DOI|

Sensitivity calculator for DESHIMA-type spectrometers

Overview
--------

deshima-sensitivity is a Python package which enables to calculate observation sensitivity of DESHIMA-type spectrometers. Currently it is mainly used to estimate the observation sensitivity of `DESHIMA <http://deshima.ewi.tudelft.nl>`__ and its successors.

An online Jupyter notebook is available for DESHIMA collaborators to calculate the sensitivity and the mapping speed of the DESHIMA 2.0 by themselves. Click the budge below to open it in `Google colaboratory <http://colab.research.google.com/>`__ (a Google account is necessary to re-run it).

Stable version (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

|open stable version in colab|

Latest version
~~~~~~~~~~~~~~

|open latest version in colab|

In the case of running it in a local Python environment, please follow the requirements and the installation guide below.

Requirements
------------

-  **Python:** 3.6, 3.7, or 3.8 (tested by the authors)
-  **Dependencies:** See `pyproject.toml <https://github.com/deshima-dev/deshima-sensitivity/blob/master/pyproject.toml>`__

Installation
------------

.. code:: shell

    $ pip install deshima-sensitivity

.. |PyPI| image:: https://img.shields.io/pypi/v/deshima-sensitivity.svg?label=PyPI&style=flat-square
   :target: https://pypi.org/pypi/deshima-sensitivity/
.. |Python| image:: https://img.shields.io/pypi/pyversions/deshima-sensitivity.svg?label=Python&color=yellow&style=flat-square
   :target: https://pypi.org/pypi/deshima-sensitivity/
.. |Test| image:: https://img.shields.io/github/workflow/status/deshima-dev/deshima-sensitivity/Test?logo=github&label=Test&style=flat-square
   :target: https://github.com/deshima-dev/deshima-sensitivity/actions
.. |License| image:: https://img.shields.io/badge/license-MIT-blue.svg?label=License&style=flat-square
   :target: LICENSE
.. |DOI| image:: https://img.shields.io/badge/DOI-10.5281/zenodo.3966839-blue?style=flat-square
   :target: https://doi.org/10.5281/zenodo.3966839
.. |open stable version in colab| image:: https://colab.research.google.com/assets/colab-badge.svg
   :target: https://colab.research.google.com/github/deshima-dev/deshima-sensitivity/blob/v0.2.6/sensitivity.ipynb
.. |open latest version in colab| image:: https://colab.research.google.com/assets/colab-badge.svg
   :target: https://colab.research.google.com/github/deshima-dev/deshima-sensitivity/blob/master/sensitivity.ipynb
