git-remote-nostr
================

It is a transparent bidirectional bridge between git and nostr.
It lets you push your git repositories to blossom servers and maintains
branch and tags info using NIP-34 kind 30618 repository state events.

DO NOT USE FOR PRODUCTION!

This is a proof of concept for the following reasons:

* Only sha256 repositories are supported, which severely limits its usefulness.
* Git object packing is not yet supported, which impacts performance in large repos.
* Git objects are stored uncompressed so as their hashes match the git internal object ids.
* Only single owner repos are supported.
* Relay and blossom servers are fixed via git config.

Usage
-----

Work-in-progress! sha1 support is coming soon!

To push a repo to nostr, the repository object format MUST be sha256, created with:
``` bash
mkdir myproject
cd myproject
git init --object-format=sha256
```

Work on the project, then push to nostr:
``` bash
git remote add origin nostr://<npub>/<myproject>
git push origin --all
```

As long as the nostr.sec config was set according to npub, the repo will be pushed and signed using the secret key.
The repository will be created automatically the first time you push.

Install
-------

``` bash
git clone git@github.com/lez/git-remote-nostr
cd git-remote-nostr
python -mvenv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install .
# Then make sure git-remote-nostr executable is in your $PATH.

git config --global --add nostr.relay wss://your.git.relay
git config --global --add nostr.blossom http://127.0.0.1:3000

# If you want to push to remotes, set your secret key as hex or nsec:
# MAKE SURE IT IS NOT SAVED IN YOUR SHELL HISTORY by appending a space in the beginning, unsetting HISTFILE or BASH_HISTORY envvar, or killing the shell with a KILL signal afterwards.
 git config --global --add nostr.sec 1
```

Notes
-----

- The remote helper does not support shallow cloning.

- Cloning a repository or fetching a lot of objects produces lots of loose
  objects. To save space in the local repository, run ``git gc --aggressive``.

- The work is based on git-remote-dropbox from Anish Athalye.

Design
------

To read about the design of git-remote-nostr, see `DESIGN.rst` file.
This could be especially useful if you're thinking about contributing to the
project.

Contributing
------------

Currently github's issue tracking is used for reporting bugs and discussing feature requests.
If you want to join development, contact me at the npub `npub1elta7cneng3w8p9y4dw633qzdjr4kyvaparuyuttyrx6e8xp7xnq32cume`.

License
-------

Copyright (c) 2015-2019 Anish Athalye. Released under the MIT License. See `LICENSE.rst` for details.
Copyright (c) 2024 Lez <npub1elta7cneng3w8p9y4dw633qzdjr4kyvaparuyuttyrx6e8xp7xnq32cume>.
