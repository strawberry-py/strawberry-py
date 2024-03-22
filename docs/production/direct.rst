.. _direct:

Direct installation
===================

If you can't/don't want to install Docker on your system, you can run the bot directly.
This may be helpful if you want to run the bot on Raspberry Pi or other low-powered hardware.

We'll be using Ubuntu 20.04 LTS in this guide, but it should generally be similar for other systems, too.
Consult your favourite search engine in case of problems.

.. note::

	You will need ``sudo`` privileges on your server to change the configuration and install packages.


.. _direct_system:

System setup
------------

.. note::

	If you have physical access to the server and are not planning on connecting there via SSH, you can skip this step.

First you have to make sure you have the bare minimum: ``git`` and ``ssh`` server, along with some modules that will be required later.

.. code-block:: bash

	apt install git openssh-server build-essential
	systemctl start sshd

Take your time and go through the SSH server settings to make the server as secure as possible.

Servers usually have static IP address, so you can always find them when you need to connect to them.
On Ubuntu, this can be set via the file ``/etc/network/interfaces``:

.. code-block::

	allow-hotplug enp0s8
	iface eth0 inet static
	    address 10.0.0.10
	    netmask 255.0.0.0

.. note::

	Alter the addresses so they match your network.
	You can find interface and mask information by running ``ip a``.

.. warning::

	If you are connected over SSH, you'll lose connection and lock yourself up.
	Consider restarting the server instead.

You can apply the settings by running

.. code-block:: bash

	ifdown eth0
	ifup eth0



.. note::

	If your server contains Desktop Environment with Network Manager or similar program, consider using it instead.

You may also want to configure firewall.
The complete setup is out the scope of this documentation; if you don't plan on running other services (like Apache, FTP or Samba) on your server, you can just run the commands below (don't forget to change the IPs!).

.. warning::

	If you don't know what ``iptables`` is or what it does, go read about it before continuing.

.. code-block:: bash

	iptables -A INPUT -i lo -j ACCEPT
	iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
	iptables -A INPUT -s 10.0.0.0/8 -p icmp --icmp-type echo-request -j ACCEPT
	iptables -A INPUT -s 10.0.0.0/8 -p tcp --dport ssh -j ACCEPT
	iptables -A INPUT -j DROP

	ip6tables -A INPUT -i lo -j ACCEPT
	ip6tables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
	ip6tables -A INPUT -p ipv6-icmp -j ACCEPT
	ip6tables -A INPUT -m tcp -p tcp --dport ssh -j ACCEPT
	ip6tables -A INPUT -j REJECT --reject-with icmp6-port-unreachable

``iptables`` rules are reset on every reboot.
To make the changes persistent, use the following package:

.. code-block:: bash

	apt install iptables-persistent
	# to save changes next time, run
	dpkg-reconfigure iptables-persistent


.. _direct_dependencies:

Dependency setup
----------------

Besides ``git``, strawberry.py has additional system dependencies which have to be installed.

.. include:: ../_snippets/_apt_dependencies.rst


.. _direct_account:

Account setup
-------------

Next you'll need to create the user account.
You can pick whatever name you want, we'll be using ``discord``.

.. code-block:: bash

	useradd discord
	passwd discord
	mkdir /home/discord
	touch /home/discord/.hushlogin
	chown -R discord:discord /home/discord

	cd /home/discord

	cat << EOF >> .profile
	alias ls="ls --color=auto --group-directories-first -l"
	source /etc/bash_completion.d/git-prompt
	PS1="\u@\h:\w$(__git_ps1)\$ "
	EOF
	echo "source .profile" > .bashrc

If you want to follow the least-privilege rule, you can allow the ``discord`` user to run some privileged commands (for restarting the bot), but not others (like rebooting the system). If you'll be using ``systemd`` to manage the bot (read :ref:`the the section below <direct_systemd>` to see the setup), you can run ``visudo`` and enter the following:

.. code-block::

	Cmnd_Alias PIE_CTRL = /bin/systemctl start strawberry, /bin/systemctl stop strawberry, /bin/systemctl restart strawberry
	Cmnd_Alias PIE_STAT = /bin/systemctl status strawberry, /bin/journalctl -u strawberry, /bin/journalctl -f -u strawberry

	discord ALL=(ALL) NOPASSWD: PIE_CTRL, PIE_STAT


.. _direct_database:

Database setup
--------------

strawberry.py officialy supports two database engines: PostgreSQL and SQLite.
We strongly recommend using PostgreSQL for production use, as it is fast and reliable.

.. note::

	If you only have small server, SQLite may be enough.
	See :ref:`devel_database` in Development Section to learn how to use it as database engine.

You can choose whatever names you want.
We will use ``strawberry`` for both the database user and the database name.

.. code-block:: bash

	apt install postgresql postgresql-contrib libpq-dev
	su - postgres
	createuser --pwprompt strawberry # set strong password
	psql -c "CREATE DATABASE <database>;"
	exit

The user, its password and database will be your connection string:

.. code-block::

	postgresql://<username>:<password>@localhost:5432/<database>
	# so, in our case
	postgresql://strawberry:<password>@localhost:5432/strawberry

To allow access to the database to newly created user, alter your ``/etc/postgresql/<version>/main/pg_hba.conf``:

.. code-block::

	# TYPE  DATABASE        USER            ADDRESS                 METHOD
	local   all             strawberry                                 md5

And restart the database:

.. code-block::

	systemctl restart postgresql

To allow passwordless access to the database, create file ``~/.pgpass`` with the following content:

.. code-block::

	<hostname>:<port>:<database>:<username>:<password>
	# so, in our case
	localhost:*:strawberry:strawberry:<password>

The file has to be readable only by the owner:

.. code-block:: bash

	chmod 600 ~/.pgpass

You can verify that everything has been set up correctly by running

.. code-block::

	psql -U strawberry

You should not be asked for password.
It will open an interactive console; you can run ``exit`` to quit.


.. _direct_download:

Downloading the code
--------------------

Use ``git`` to download the source code:

.. code-block:: bash

	git clone git@github.com:strawberry-py/strawberry-py.git strawberry
	cd strawberry

To update the bot later, run

.. code-block:: bash

	git pull


.. _direct_env:

Environment file
----------------

The file called ``.env`` (that's right, just these four characters, nothing more) holds information strawberry.py needs in order to start.

When you clone your repository, this file does not exist, you have to copy the example file first:

.. code-block:: bash

	cp default.env .env

You'll get content like this:

.. code-block:: bash

	DB_STRING=
	TOKEN=

After each ``=`` you must add appropriate value.
For ``TOKEN``, see the section :ref:`general_token` below.
For ``DB_STRING``, see the manual for installation that applies to your setup.

.. _direct_venv:

Virtual environment
-------------------
To prevent clashes between libraries on the system, especially when running multiple bot instances,
it's recommended to set up virtual environment.

Virtual environment makes keeping different Python library versions on the same system possible.

.. _direct_venv_setup:

venv setup
^^^^^^^^^^

You may need to install the virtual environment package first:

.. code-block:: bash

	sudo apt install python3-venv

Once available on your system, you can run

.. code-block:: bash

	python3 -m venv .venv

to set up the virtual environment in current working directory.

This only has to be done once, then it is set up forever.
If you install newer version of Python (e.g. from 3.9 to 3.10), you may need to remove the ``.venv/`` directory and perform the setup again.


.. _direct_venv_usage:

venv usage
^^^^^^^^^^

The following step has to be performed every time you want to run the bot.

.. code-block:: bash

	source .venv/bin/activate

Once activated, you can install packages as you want, they will be contained in this separate directory.

To exit the environment, run

.. code-block:: bash

	deactivate


See installation manuals for details on what to do once you are in virtual environment.


Once you are in virtual environment, you can install required libraries:

.. code-block:: bash

	python3 -m pip install wheel
	python3 -m pip install -r requirements.txt

Before the bot can start, you have to load the contents of ``.env`` file into your working environment.
This can be done by running

.. include:: ../_snippets/_source_env.rst

.. note::
	To make sure that the variables from ``.env``` file are always loaded, you can do this trick.
	Open the activate script (the ``.venv/bin/activate`` file) and insert the code above at the end of the file.

	This way the variables will be set whenever you enter the virtual environment with the ``source .venv/bin/activate`` command, and you won't have to run the ``source .env`` manually.


.. _direct_token:

Discord bot token
-----------------

See :ref:`general_token` in chapter General Bot Information.


.. _direct_systemd:

systemd service
---------------

Systemd service can autostart or restart the application when it crashes.
Docker does this manually, you'll have to add support via ``systemd`` yourself.
The service file may look like this:

.. code-block:: ini

	[Unit]
	Description = strawberry.py bot

	Requires = postgresql.service
	After = postgresql.service
	Requires = network-online.target
	After = network-online.target

	[Service]
	Restart = on-failure
	RestartSec = 5
	User = discord
	StandardOutput = journal+console

	EnvironmentFile = /home/discord/strawberry/.env
	WorkingDirectory = /home/discord/strawberry
	ExecStart = /home/discord/strawberry/.venv/bin/python3 strawberry.py

	[Install]
	WantedBy = multi-user.target

Create the file and copy it to ``/etc/systemd/system/strawberry.service``.
Refresh the systemd with ``systemctl daemon-reload``.


.. _direct_run:

Running the bot
---------------

.. code-block:: bash

	systemctl start strawberry.service

To start the bot automatically when system starts, run

.. code-block:: bash

	systemctl enable strawberry.service
