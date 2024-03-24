.. _devel:

Development installation
========================

Everyone's development environment is different. This is an attempt to make it as easy as possible to setup.


.. _devel_fork:

Forking the bot
---------------

Fork is a repository that is a copy of another repository.
By performing a fork you'll be able to experiment and alter modules withou affecting the main, official repository.
The fork is also used for opening Pull Requests back to our repository.

.. note::

	This section also applies to strawberry.py module repositories, not just main repository.
	Just change the URLs.

Open `our official GitHub page <https://github.com/strawberry-py/strawberry-py>`_.
Assuming you are logged in, you should see a button named **Fork** (at the top right).
Click it.

After a while, the site will load and you'll see the content of your fork repository, which will look exactly the same as the official one -- because it's a copy.

Under a colored button **Code**, you can obtain a SSH URL which will be used with ``git clone`` to copy it to your local machine.

.. note::

	This manual will assume you have your SSH keys set up.
	It's out of scope of this manual to describe full steps.
	Refer to `GitHub <https://docs.github.com/en/authentication/connecting-to-github-with-ssh>`_ documentation or use your preferred search engine.


.. _devel_system_pre_setup:

System setup
------------

There are few necessary things you have to install on your computer before you start with development.

.. _devel_system_pre_setup_git:

Install GIT
------------

First thing you'll need is ``git``.
It may be on your system already.

Please follow the official tutorial for `Installing GIT <https://git-scm.com/book/en/v2/Getting-Started-Installing-Git>`_ on your OS.

.. _devel_system_pre_setup_python:

Install Python
------------

The two most important things to install are Python and PIP (python package manager, on Windows and Mac should be part of Python installer).

For Linux, we'd recommend using your system package manager (e.h. `apt`) to install Python and it's extensions:

.. code-block:: bash

	apt install \
	    python3 python3-dev python3-pip python3-venv python3-setuptools

For Windows and MacOS, Python can be installed from `Official site <https://www.python.org/downloads/>`_.

To simplify few things on Windows, we'd recommend to run the installer as administrator and select ``Customize instalation`` during setup to be able to install Python for all users.

If you'd like to use multiple Python versions at once, we might recommend `pyenv <https://github.com/pyenv/pyenv>`_ for Unix based systems or `pyenv-win <https://github.com/pyenv-win/pyenv-win>` for Windows

.. _devel_code_setup:

Code setup
----------

Clone your fork:

.. code-block:: bash

	git clone git@github.com:<your username>/strawberry-py.git strawberry
	cd strawberry

Then you have to setup a link back to our main repository, which is usually called upstream:

.. code-block:: bash

	git remote add upstream https://github.com/strawberry-py/strawberry-py.git




.. _devel_database:

Database
--------

We have two options with the database. We can either use PostgreSQL or SQLite.

When working with databases, it's always good for testing purposes to test out the new code on both of them, as soem features might not be available for one of them.

For the start, we'd recommend using SQLite, because it's simple to access - the data file can be easily opened in tools like `SQLite Browser <https://sqlitebrowser.org/>`_.
The second argument for SQLite is also the fact that wiping the DB means just deleting ``strawberry.db`` file.
Also, in case of :ref:`direct` it's easier to set up SQLite than PostgreSQL, which does not matter in case of :ref:`direct` setup, which is recommended.



.. _devel_running-bot:

Running the bot
-----------------

There are basically two recommended ways to run the bot.

The recommended one is using docker as it makes the whole setup simple and the bot environment separated from your OS.
This is specially useful when working with PostgreSQL. The setup is the same as described in :ref:`containers`.
We can recommend using ``docker-compose up`` without ``detach`` parameter to see the bot's log easily.

The second way is similar to :ref:`direct`. The only difference is that we can omit few things, such as PostgreSQL setup (and use SQLite only).
In that case we can also run the bot directly with `python ./strawberry.py` and avoid using daemon and services.
However, with this setup it's more complicated to test out our code with PostgreSQL database.

In all cases, when the bot runs, the output should look like this:
.. code-block::

	Imported database models in modules.base.base.database.
	Imported database models in modules.base.admin.database.
	Loaded module base.acl
	Loaded module base.admin
	Loaded module base.base
	Loaded module base.logging
	Loaded module base.errors
	Loaded module base.language
	     (
	  (   )  )
	   )  ( )
	   .....
	.:::::::::.
	~\_______/~
	2022-02-18 08:18:02 CRITICAL: The pie is ready.


.. _devel_venv:

Development environment
---------------
.. note::
	This is not necessary to test out the bot if you are using :ref:`containers` to run the bot.

There are two reasons to install all the requirements. The first is that your IDE should be able to give you hints based on the installed python libraries.
The second reason is that you can use pre-commit hook, which helps us maintain :ref:`code_quality`.

Using virtual environment is optional and depends on your OS and IDE as some of them (e.g. PyCharm) have it's own way of managing virtual environments.
See :ref:`direct_venv` in chapter Production section on how to setup a virtual environment.

This code can be also run directly in your main (not virtual) environment, but in that case there might be colisions with already installed libraries.

.. code-block:: bash

	python3 -m pip install wheel
	python3 -m pip install -r requirements.txt
	python3 -m pip install -r requirements-dev.txt
	python3 -m pre-commit install