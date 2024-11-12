Design
======

Many things are designed the way they are in order to have the same semantics
and guarantees as a regular Git remote *without running any special code on the
server side*.

git-remote-blossom is a `Git remote helper
<https://www.kernel.org/pub/software/scm/git/docs/gitremote-helpers.html>`__.

To support all Git operations, we need to support one capability for pushing
and one capability for fetching. For our use case, the best way to do this is
to implement the ``push`` and ``fetch`` capabilities. Alternatives are better
suited for interacting with foreign version control systems.

Repository Layout
-----------------

We store repository data on Nostr in a similar way to how Git stores data on
disk. In particular, we store `references
<https://git-scm.com/book/en/v2/Git-Internals-Git-References>`__ and `loose
objects <https://git-scm.com/book/en/v2/Git-Internals-Git-Objects>`__, which
make up all information that needs to be stored on the server.

References are stored in Nostr events, objects are stored on blossom.

References
~~~~~~~~~~

References are stored in ``refs`` (relative to the repository root). The format
of references is identical to how Git stores references in the ``.git``
directory. For example, the ``master`` ref would be stored in
``refs/heads/master``, and the file would contain the SHA1 hash corresponding
to the commit that the master branch points to.

Symbolic References
~~~~~~~~~~~~~~~~~~~

Symbolic references are stored in the repository root. The format of the
symbolic refs is identical to how Git stores symbolic refs in the ``.git``
directory. For example, ``HEAD`` would be stored in ``HEAD``, and if it is
pointing to ``refs/heads/master``, the file would contain ``ref:
refs/heads/master``.

The SHA1 commit ID and blossom SHA256
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Git commit and tree objects hold references to other git objects like parent
commits and blobs. The references are in sha1 format in the git objects, but
that is not enough to be able to actually fetch the objects from a blossom
server. We need it's blossom sha256 hash for that.

For this reason, any git object with sha1 references in it also contains the
sha256 hash where the object was stored at. The sha256 hashes are simply added
at the end of the git object before storing them on the blossom server.

When we fetch, we can use this info to recursively reach all objects. Then we
trim the sha256 hashes from the end of the objects before storing them on disk.
By doing this transformation we get back the original, valid objects.

So the objects on a blossom server are invalid objects in terms of git, but they
hold the sha256 links to other objects for the git-remote-blossom.

Objects
~~~~~~~

Objects are stored in ``objects`` (relative to the repository root). The path
and file name of objects is identical to how Git stores loose objects in the
``.git`` directory. For example, an object with the hash
``5f1594aa9545fab32ae35276cb03002f29ce9b79`` would be stored in
``objects/5f/1594aa9545fab32ae35276cb03002f29ce9b79``.

The files may not actually be identical on disk due to differences in DEFLATE
compression, but in fact, if the files are copied as-is into a local Git
repository, Git will recognize the files as valid.

git-remote-blossom stores all objects as loose objects - it does not pack
objects. This means that we do not perform delta compression. In addition, we
do not perform garbage collection of dangling objects. DVMs can do that later.

Push
----

To push a ref, we need to ensure that the server has all objects reachable from
the ref, and we need to update the ref in a safe way such that concurrent
operations don't cause problems.

Objects
~~~~~~~

We can use the ``git rev-list --objects <ref>`` command to get all the objects
reachable from ``ref``. We could just upload all of these, but that would be a
lot of unnecessary work, equivalent to uploading the entire repository for
every push.

Instead, we can figure out exactly what objects the server is missing, and then
we can upload only those objects. We can get a list of refs present on the
server, and then we can compute which objects the server is missing by using
``git rev-list --objects <ref> ^<exclude>``, where ``exclude`` is a ref present
on the server. We can do this with multiple exclusions too.

Once we have the list of objects that the server is missing, we can upload them
all. Because objects are content-addressed, we don't need to worry about
conflicts.

Refs
~~~~

Pushing the ref itself is slightly more complicated. Once all the objects are
present, we need to update the remote ref atomically. First, we check if we're
performing a fast-forward, and then we perform a write operation. If
there are any concurrent changes, the older event will be overwritten.

If we're doing a force push, the process is simpler - we can just overwrite the
ref with the new value.

If we're deleting a branch, we make sure that we're not deleting the default
branch before deleting the ref.

Symbolic refs
~~~~~~~~~~~~~

The symbolic ref ``HEAD`` is set upon repository creation.

Fetch
-----

We fetch refs by recursively downloading all of the objects reachable
from the object pointed to by the ref, terminating branches of the recursion
when we reach objects that we already have locally, provided that we have the
full history from that point on.
