git-remote-nostr+blossom
========================

This program lets you push git repositories onto nostr relays + blossom servers.

It produces kind 30618 events on the relay that is specified in NIP-34.

This is Proof of Concept code for the following reasons:
* It supports a single blossom server.
* It supports a single nostr relay.
* It supports a single repo owner.
* It is relatively but not prohibively slow. The initial cloning of large projects can take a while, but everyday work is fine.

Usage (PoC)
-----------

For now, the nostr relay and the blossom server must be manually set in git config:

``` bash
git config --global --add nostr.relay wss://your.relay.org
git config --global --add nostr.blossom https://your.blossom.org:3000
```

If you want to push, set your secret key as hex or nsec in ``nostr.sec`` or ``nostr.nsec``:
``` bash
 git config --global --add nostr.sec 1  # This is a test key with npub=npub10xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqpkge6d
```

Now you can use the ``nostr+blossom://`` scheme in your git remote URLs.
``` bash
git remote add nostr nostr+blossom://<npub>/<project>
git push origin nostr  # Use -v to see what's going on under the hood.
```

The repository is created automatically the first time you push.

Install
-------

``` bash
$ pip install git+https://github.com/lez/git-remote-nostr

The executable `git-remote-nostr+blossom` should be now in your PATH.
```

Notes, bugs
-----------

- ``--force-with-lease`` is not supported yet.
- packing git objects is not supported (as far as I know). This would make a huge improvement on speed.
- shallow cloning is not supported.
- progress bar is not very helpful when cloning.
- you should run ``git gc --aggressive`` regularly.
- This project is based on git-remote-dropbox from Anish Athalye.
- Make sure you do not leave your nsec in your shell history in order to not leak it accidentally in a screenshare session.

Design
------

To read about the design of git-remote-nostr, see `DESIGN.rst` file.
This could be especially useful if you're thinking about contributing to the
project.

Future Plans
------------

Planned remote URL formats:

* nostr+blossom://your@nip-05.address/project
* nostr+blossom://nprofile.../project
* nostr+blossom://nevent...

The bootstrap relay will be read either from the relay list in the nip-05 json or decoded from nprofile or nevent "relay" field.

Also, deeper NIP-34 integration is planned.

Contributing
------------

Currently github's issue tracking is used for reporting bugs and discussing feature requests.
If you want to join development, contact me at the npub `npub1elta7cneng3w8p9y4dw633qzdjr4kyvaparuyuttyrx6e8xp7xnq32cume`.

License
-------

Copyright (c) 2015-2019 Anish Athalye. Released under the MIT License.
Copyright (c) 2024 Lez <nostr:npub1elta7cneng3w8p9y4dw633qzdjr4kyvaparuyuttyrx6e8xp7xnq32cume>.
