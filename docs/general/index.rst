.. _general:

General information
=======================

.. note::

	If you are a developer, the :ref:`devel` page may be more suitable for you.

	If you want to deploy your bot instance, take a look at :ref:`containers`, :ref:`direct` or :ref:`k8s`.

To set up the bot, we recommend using Docker as it's the easiest way.


.. _general_token:

Bot token
---------

Token is equivalent to yours username & password.
Every Discord bot uses their token to identify themselves, so it's important that you keep your bot's token on private place.

Go to `Discord Developers page <https://discord.com/developers>`_, click **New Application** button and fill the form.

Go to the Bot tab on the left and convert your application to bot by clicking **Add Bot**.
Then enable all Privileged Gateway Intents (Presence, Server Members, Message Content).
There are warnings about 100 servers, but we don't need to worry about it.

On the top of this page, there is a Token section and a ``Reset Token`` button.
Copy the generated token and put it into your ``.env`` file (if you don't have any, see the section :ref:`general_env` above) after the ``TOKEN=``.

Open your ``.env`` file and put the token in.

You can invite the bot to your server by going to the **OAuth2/URL Generator page**, selecting **bot** and **applications.commands** scopes and **Administrator** bot permission to generate a URL.
Open it in new tab.
You can invite the bot only to the servers where you have Administrator privileges.

.. _installing_module:

Installing modules
-----------------

Installing modules is done through the ``repository`` command of the bot instance or by manually clonning the module as described in :ref:`developing-modules`.

To get more info of the repository command, please refer to ``help repo`` command of the bot instance.