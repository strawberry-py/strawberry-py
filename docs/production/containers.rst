.. _containers:

Containers
==========

Containers allow running the bot independent of the host environment. 
This makes things easier and containers more portable.

It is possible (and recommended) to use containers for development as well. 
Just make sure you have fetched the source code and skip :ref:`containers_no_local_repo`.

.. _containers_download:

Fetching source code (optional)
-------------------------------

.. note::
	It is not neccesary to fetch the source code when using containers. 
	See :ref:`containers_no_local_repo`.

Use ``git`` to download the source code. 

.. warning::
	It is necessary to use HTTPS, because the container should not have ssh keys set up.
	If you need to clone a private repository, you can use GitHub's Personal :ref:`access_tokens`.
	with limited REPO:READ only permissions.

.. code-block:: bash

	git clone https://github.com/strawberry-py/strawberry-py.git strawberry
	cd strawberry

To update the bot later, run

.. code-block:: bash

	git pull


.. _containers_no_local_repo:

Running without local source code
---------------------------------

If you don't want to download the source code to your host, or use Docker, 
you can leverage volumes to make your modules persistent.

Simply create a folder create a ``.env`` file with the contents of \
the ``default.docker.env`` file in the repository and create ``docker-compose.yml`` 
with the contents of the ``docker-compose.yml`` from the repository as well.

You will need to edit the volumes of the bot service in ``docker-compose.yml`` file accordingly:

.. code-block:: yaml

	volumes:
	  - strawberry_data:/strawberry-py

And add a new volume to end of the file:

.. code-block:: yaml

	volumes:
	  postgres_data:
	  strawberry_data:


.. _environment_file:

Environment file
----------------

The file called ``.env`` (that's right, just these four characters, nothing more) holds information strawberry.py needs in order to start.

When you clone your repository, this file does not exist, you have to copy the example file first:

.. code-block:: bash

	cp default.docker.env .env

You'll get content like this:

.. code-block:: bash

	DB_STRING=
	TOKEN=

After each ``=`` you must add appropriate value.

The environment variables are described bellow.


.. _containers_token:

Discord bot token
-----------------

See :ref:`general_token` in chapter General Bot Information.


.. _instance_name:

Instance name
-----------------

This variable is used to (partially) set up container names to be able to distinguish
the instances in multi-instance enviroment.

.. _containers_database:

Database
--------

The database holds all dynamic bot data (e.g. the user content). There are multiple options, 
but the provided `docker-compose.yml` is already set up with PostgreSQL with automatic backups.

If you plan to run without a local repository, you already have the ``.env`` file.
Otherwise copy the contents of ``default.docker.env`` into ``.env`` in the root directory.
This is file will be reffered to as the environment file from now on.

The docker environment file already contains prefilled ``DB_STRING`` and ``BACKUP_PATH`` variables.
You can change the ``BACKUP_PATH`` variable to any other path where the backups should be saved.

To restore a backup, point ``$BACKUPFILE`` to the path of your backup and restore the database by running the following:

.. code-block:: bash

	BACKUPFILE=path/to/backup/file.sql.gz

	zcat $BACKUPFILE | \
	docker-compose exec -T db \
	psql --username=postgres --dbname=postgres -W


.. _containers_env:

Other environment variables
---------------------------

The environment file contains other environment variables change the configuration or behavior of the application.

The following list explains some of them:

* ``BOT_TIMEZONE=Europe/Prague``  - the time zone used by the bot. Influences some message attributes.
* ``BOT_EXTRA_PACKAGES=``  - any additional ``apt`` packages that need to be installed inside the bot container
* ``BACKUP_SCHEDULE=@every 3h00m00s``  - backup schedule for the database (runs every 3 hours by default)

.. _docker_installation_linux:

Docker Installation - LINUX
-------------------

The first step is installing the docker:

.. code-block:: bash

	sudo apt install docker docker-compose

It will probably be neccesary to add the user to the Docker group (this will take effect on the next session):

.. code-block:: bash

	sudo usermod -aG docker $USER

For the next command you will probably need to log out and back in to load the group change.

.. _docker_installation_windows:

Docker Installation - WINDOWS
-----------------------------
.. warning::
	This tutorial covers the installation on Windows 10 Build 2004 or later and should be compatible
	with Windows 11 as well.


In this tutorial we will be working with Docker Desktop, which is free for non-commercial usage. 
If you plan on deploying the bot in commercial environment, consider using Rancher Desktop.

As it's recommended to use Docker Desktop with WSL2 backend (instead of HyperV), 
this tutorial will cover the WSL2 installation as well.

We recommend creating ``.wslconfig`` file in your ``userprofile`` folder to enable ``sparseVhd`` option.
This will automatically shrink virtual hard drives of the WSL2. This function is supported since September 2023 update.
The file should contain this section:

.. codeblock:: 

	[experimental]
	sparseVhd=true

If you don't have WSL2 installend, you must run following command in ``cmd`` as Administrator.

.. codeblock::
	
	wsl --install

When WSL2 is installed, follow the official tutorial on how to 	`Install Docker Desktop on Windows <https://docs.docker.com/desktop/install/windows-install/>`_.

If the installation is successful, you should be able to run ``docker --version`` command.

.. _containers_start:

Start the stack
---------------

.. note::
	Make sure you are in the right directory (the one where ``.env`` and ``docker-compose.yml`` files are) 

Build the image from the source (not necessary when running without local source code.):

.. code-block:: bash

	docker-compose build

Run the docker instance (as background service):

.. code-block:: bash

	docker-compose up --detach

If you want to run the bot in foreground (e.g. for testing, development or debugging purposes),
you can just remove the ``--detach`` parameter.

The above command will pull the necessary container images and start the stack. 
The bot will take some time to actually start responding,
because the container needs to install any additional ``apt`` dependencies first (from the aforementioned env var)
and make sure that all the required pip packages are installed as well.

Afterwards you can stop the stack at any time by:

.. code-block:: bash

	docker-compose stop

And start it again with:

.. code-block:: bash

	docker-compose start