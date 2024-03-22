.. _code_quality:
Code quality
============

.. include:: ../_snippets/_rfc_notice.rst

Your code has to pass the Github Actions CI before it can be merged. You can pretty much ensure this by using the **pre-commit**:

.. code-block::

   pre-commit install

The code will be tested everytime you create new commit, by manually running

.. code-block::

   pre-commit run --all
   pytest

Every pull request has to be accepted by at least one of the core developers.

PIP module pre-commit should be always included in requirements-dev.txt.