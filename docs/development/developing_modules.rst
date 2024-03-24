.. _developing-modules:

Developing modules
==================

.. note::

	Always start from ``main``, but never commit to ``main``.
    You can also start from the fresh branch synchronized with ``main``.

Let's say you want to make changes to our `Fun <https://github.com/strawberry-py/strawberry-fun>`_ repository.

You have two options to install the forked repository. 
Option one is using **repository install** command, which would place it into the ``modules/`` directory.
Option two is cloning the repository manually using ``git`` commands inside ``modules/``.


.. code-block:: bash

    cd modules/
    git clone git@github.com:<your username>/strawberry-fun.git fun

Make sure you name the cloned directory correctly (e.g. the ``fun`` argument in the command above): it has to be the same as the ``name`` in repository's ``repo.conf``.
An example of such a file is just below:

.. code-block:: ini

    [repository]
    name = fun
    modules =
        dhash
        fun
        macro
        rand

Now you can start your bot.
You should see that their database tables have been created.
All these modules should be showing up now when you run **repository list**.

Now you can make branches, commit changes and open PRs back into the main repository as usual.
