import multiprocessing
import multiprocessing.dummy
import multiprocessing.pool
import posixpath
import asyncio
import os
import hashlib
import base64
import json
import random
import sys
import zlib
import aiohttp
from aiohttp.client_exceptions import ClientConnectorError
from monstr.event.event import Event

from git_remote_nostr.constants import CONCURRENCY, MAX_RETRIES
from git_remote_nostr.util import readline, Level, stdout, stderr, Poison
from git_remote_nostr import git
from git_remote_nostr.gitremote import GitRemote, GitRemoteError


class Helper(object):
    def __init__(self, remote_name, sk, path, concurrency=CONCURRENCY):
        self._remote_name = remote_name
        self._sk = sk
        self._path = path
        self._concurrency = concurrency
        self._verbosity = Level.INFO  # default verbosity
        self._refs = {}  # {refname: (sha, blossom_key)}
        self._pushed = {}  # Same, but just pushed (?).
        self._first_push = False
        self._remote = None
        self._semaphore = asyncio.Semaphore(self._concurrency)
        self._git_dir = os.environ["GIT_DIR"]
        self._blossom_server = git.get_config_value("nostr.blossom")
        self._objectformat = git.get_config_value("extensions.objectformat") or "sha1"
        self._have_blossom_key = dict()
        self._blossom_keys = {}

    @property
    def verbosity(self):
        return self._verbosity

    def _write(self, message=""):
        """Write a message to standard output, which is read by the git process."""
        self._trace(f"> {message}")
        stdout('%s\n' % message)

    def _trace(self, message, level=Level.DEBUG, exact=False):
        """
        Log a message with a given severity level.
        """
        if level > self._verbosity:
            return

        if exact:
            if level == self._verbosity:
                stderr(message)
            return

        if level <= Level.ERROR:
            stderr('error: %s\n' % message)
        elif level == Level.INFO:
            stderr('info: %s\n' % message)
        elif level >= Level.DEBUG:
            stderr('debug: %s\n' % message)

    def _fatal(self, message):
        """
        Log a fatal error and exit.
        """
        self._trace(message, Level.ERROR)
        raise SystemExit(1)

    async def connect(self):
        """Find repo announcement event and connect to relay(s)."""
        try:
            self._remote = GitRemote(self._path, self._remote_name, self._sk, self._verbosity)
            await self._remote.connect()
        except GitRemoteError as e:
            self._trace(str(e), Level.ERROR)
            return False

        return True

    async def run(self):
        """
        Run the helper following the git remote helper communication protocol.
        """
        while True:
            line = readline()
            if line:
                self._trace(f'< {line}')

            if line == 'capabilities':
                self._write('option')
                self._write('push')
                self._write('fetch')
                self._write()
            elif line.startswith('option'):
                self._do_option(line)
            elif line.startswith('list'):
                await self._do_list(line)
            elif line.startswith('push'):
                await self._do_push(line)
            elif line.startswith('fetch'):
                await self._do_fetch(line)
            elif line == '':
                break
            else:
                self._fatal('unsupported operation: %s' % line)

    def _do_option(self, line):
        """
        Handle the option command.
        """
        if line.startswith('option verbosity'):
            self._verbosity = int(line[len('option verbosity '):])
            self._write('ok')
        else:
            self._write('unsupported')

    async def _do_list(self, line):
        """
        Handle the list command.
        """
        for_push = 'for-push' in line

        first_push, self._refs = await self._remote.get_refs(for_push=for_push)
        if (first_push, self._refs) == (None, {}):
            # if we're pushing, it's okay if nothing exists beforehand,
            # but it's good to notify the user just in case
            self._trace('repository is empty', Level.INFO)

        if first_push:
            self._trace('First push to remote repository.', Level.INFO)
            self._first_push = True

        for refname, refval in self._refs.items():
            self._trace(f"remote ref: {refval[0]} {refname}")

        if self._objectformat == "sha256":
            self._write(":object-format sha256")
        else:
            assert self._objectformat == "sha1"

        self._trace(f"Git repository object format is {self._objectformat}.")

        for refname, sha in self._refs.items():
            self._write('%s %s' % (sha[0], refname))

        if not for_push:
            head = await self._remote.read_symbolic_ref('HEAD')
            if head:
                self._trace(f'remote HEAD: {head}')
                self._write(f'@{head} HEAD')
            else:
                self._trace('no default branch on remote', Level.INFO)

        for sha, blossom_key in self._refs.values():
            self._trace(f"Set blossom key of {sha} to {blossom_key} in memory.")
            self._blossom_keys[sha] = blossom_key

        self._write()

    async def _do_push(self, line):
        """
        Handle the push command.
        """
        remote_head = None
        while True:
            src, dst = line.split(' ')[1].split(':')
            if src == '':
                self._delete(dst)
            else:
                await self._push(src, dst)
                if self._first_push:
                    if not remote_head or src == git.symbolic_ref('HEAD'):
                        remote_head = dst
            line = readline()
            if line == '':
                if self._first_push:
                    self._first_push = False
                    err = await self._remote.write_symbolic_ref('HEAD', remote_head)
                    if err:
                        self._trace(f'failed to set default branch on remote: {err}', Level.INFO)
                break
            self._trace(f'< {line}')
        self._write()

    async def _do_fetch(self, line):
        """
        Handle the fetch command.
        """
        while True:
            _, sha, value = line.split(' ')
            await self._fetch(sha)
            line = readline()
            if line == '':
                break
            self._trace(f"< {line}")
        self._write()

    def _delete(self, ref):
        """
        Delete the ref from the remote.
        """
        raise Exception("WE_ARE_HERE: Not implemented.")
        head = self.read_symbolic_ref('HEAD')
        if head and ref == head[1]:
            self._write('error %s refusing to delete the current branch: %s' % (ref, head))
            return

        self._refs.pop(ref, None)  # discard
        self._pushed.pop(ref, None)  # discard
        self._write('ok %s' % ref)

    async def _push(self, src, dst):
        """Push local src to remote dst."""
        if self._remote._remote_pubkey != self._sk.public_key_hex():
            error("Only the repository owner can push." +\
                " Push by contributor is not yet supported.")

        force = False
        if src.startswith('+'):
            src = src[1:]
            force = True

        present = [sha for (sha, blossom_key) in self._refs.values()]
        # present.extend([sha for (sha, name) in self._pushed])
        # Store all referenced git objects in blossom, then update ref on the relays.
        self._trace(f"Present refs: {', '.join(present)}")
        objects = git.list_objects(src, present)
        self._trace(f"{len(objects)} objects to push: {', '.join(objects)}")

        # Initialize progressbar.
        self._total = len(objects)
        self._trace('', level=Level.INFO, exact=True)
        self._done = 0

        try:
            # Upload objects in parallel.
            tasks = []
            for sha in reversed(objects):
                self._trace(f"Adding task put_object({sha}).")
                tasks.append(asyncio.create_task(self._put_object(sha)))
                # Create async event for synchornizing sha256 calc of git objects.
                self._have_blossom_key[sha] = asyncio.Event()

                if len(tasks) < self._concurrency:
                    continue

                tasks = await self.handle_tasks(tasks)

            while len(tasks):
                tasks = await self.handle_tasks(tasks)

        except Exception as e:
            if self.verbosity >= Level.DEBUG:
                raise  # re-raise exception so it prints out a stack trace
            else:
                self._fatal(f'{str(e)} while storing objects (run with -v for traceback)\n')

        sha = git.ref_value(src)
        self._trace(f"Upload finished. HEAD is [{sha}].")

        try:
            error = await self._remote.write_ref(sha, dst, force)
        except Exception:
            if self.verbosity >= Level.DEBUG:
                raise  # re-raise exception so it prints out a stack trace
            else:
                self._fatal(f"exception while writing [{dst}]")

        if error is None:
            self._write('ok %s' % dst)
            self._pushed[dst] = sha
        else:
            self._write('error %s %s' % (dst, error))

    async def handle_tasks(self, tasks):
        self._trace(f"Waiting for {len(tasks)} tasks.")
        tasks_done, pending =\
            await asyncio.wait(
                tasks, timeout=15, return_when=asyncio.FIRST_COMPLETED)
        self._trace(f"Done: {len(tasks_done)} tasks.")
        self._done += len(tasks_done)

        exc = None
        # Raise any errors that occurred in async tasks.
        for t in tasks_done:
            e = t.exception()
            if e:
                exc = e
                self._trace(f"{t} had exception {str(e)}")

        if exc:
            for p in pending:
                p.cancel()
            # We can raise now that all (pending, done) exceptions were retrieved.
            raise exc

        pct = int(float(self._done) / self._total * 100)
        message = '\rWriting objects: {:3.0f}% ({}/{})'.format(pct, self._done, self._total)
        if self._done == self._total:
            message = '%s, done.\n' % message
            self._trace(message, level=Level.INFO, exact=True)
            return []

        self._trace(message, level=Level.INFO, exact=True)
        return list(pending)

    def _ref_name_from_path(self, path):
        """
        Return the ref name given the full path of the remote ref.
        """
        prefix = '%s/' % self._path
        assert path.startswith(prefix)
        return path[len(prefix):]

    async def _blossom_store(self, data, sha256):
        auth_event = Event(
            kind=24242,
            content=f"Upload {sha256.hex()}",
            pub_key=self._sk.public_key_hex(),
            tags=[
                ["t", "upload"],
                ["x", sha256.hex()],
                ["expiration", "1777777777"]
            ]
        )
        auth_event.sign(self._sk.private_key_hex())
        json_auth = json.dumps(auth_event.data(), separators=(',',':'))
        b64_auth = base64.b64encode(json_auth.encode()).decode()

        # Upload object to blossom.
        async with aiohttp.ClientSession() as sess:
            async with sess.put(
                    f"{self._blossom_server}/upload",
                    data=data,
                    headers={
                        "Authorization": f"Nostr {b64_auth}",
                        "Content-Type": "application/octet-stream"
                    }) as resp:

                if resp.status != 200:
                    txt = await resp.text()
                    raise Exception(txt)

                await resp.text()

    async def _put_object(self, sha):
        self._trace(f"_put_object({sha})")
        async with self._semaphore:
            return await self.__put_object(sha)

    async def __put_object(self, sha):
        """Upload an object to blossom."""
        if self._objectformat == "sha256":
            raise Exception("WE_ARE_HERE: re-add sha256 support")

        self._trace(f"__put_object({sha})")

        data = git.encode_object(sha)
        for dep in git.referenced_objects(sha):
            # Check if blossom key of referenced git object is on disk.
            blossom_key = self._remote._read_blossom_key(dep)
            if blossom_key:
                data += blossom_key
                continue

            await self._have_blossom_key[dep].wait()
            blossom_key = self._remote._read_blossom_key(dep)
            data += blossom_key

        data = zlib.compress(data)
        #NOTE: We can compress data with zlib for storage,
        # because the blossom key (sha256) is not based
        # on the uncompressed data. If it was a single sha256
        # hash that is both the hash of the data and the
        # commit id, we would need to store it plaintext.

        # Blossom key of current git object
        blossom_key = hashlib.sha256(data).digest()
        self._remote._write_blossom_key(sha, blossom_key)
        self._have_blossom_key[sha].set()

        await self._blossom_store(data, blossom_key)
        self._trace(f'Stored {sha} on blossom server.')

    async def _download(self, sha):
        async with self._semaphore:
            return await self.__download(sha)

    async def __download(self, sha):
        """Download sha object from blossom."""
        blossom_key = self._blossom_keys[sha]
        assert blossom_key

        self._trace(f"fetching {blossom_key}")
        async with aiohttp.ClientSession() as sess:
            async with sess.get(f"{self._blossom_server}/{blossom_key}") as resp:
                if resp.status != 200:
                    txt = await resp.text()
                    #WE_ARE_HERE: error handling
                    raise Exception(txt)

                data = await resp.read()

        assert len(data) > 0, data

        decompressed = zlib.decompress(data)
        # Decompressed data starts with the git object in the classic git format.
        # Referenced git objects' blossom hashes are read from the end.
        header, tail = decompressed.split(b"\x00", 1)
        obj_type, obj_len = header.split()
        obj_len = int(obj_len)
        obj_data = tail[:obj_len]
        blossom_keys = tail[obj_len:]

        computed_sha = git.decode_object_raw(obj_type, obj_data)

        if computed_sha != sha:
            raise Exception(f"hash mismatch {computed_sha} != {sha}")

        for referenced_sha in git.referenced_objects(sha):
            self._blossom_keys[referenced_sha] = blossom_keys[:32].hex()
            blossom_keys = blossom_keys[32:]
        assert len(blossom_keys) == 0

        return sha

    async def _fetch(self, sha):
        """
        Recursively fetch the given object and the objects it references.
        """
        # have multiple threads downloading in parallel
        queue = asyncio.Queue()
        await queue.put(sha)
        pending = set()
        downloaded = set()
        self._trace('', level=Level.INFO, exact=True)  # for showing progress
        done_cnt = total = 0
        tasks = set()

        while queue.qsize() or pending:
            if queue.qsize():
                # if possible, queue up download
                sha = await queue.get()
                if sha in downloaded or sha in pending:
                    continue
                if git.object_exists(sha):
                    if not git.history_exists(sha):
                        # Previous fetch was aborted beforehand
                        # or this is the first blob object in repo.
                        for referenced in git.referenced_objects(sha):
                            #TODO: Prioritize commit objects for better concurrency
                            await queue.put(referenced)
                else:
                    self._trace(f"GET {sha} ")
                    pending.add(sha)
                    tasks.add(asyncio.create_task(self._download(sha)))
            else:
                # Download complete.
                done, pending_tasks = await asyncio.wait(\
                    tasks, timeout=15, return_when=asyncio.FIRST_COMPLETED)
                for done_task in done:
                    if done_task.exception():
                        raise done_task.exception()

                    res = done_task.result()
                    # self._trace(f"Downloaded {res}")
                    pending.remove(res)
                    downloaded.add(res)
                    for sha in git.referenced_objects(res):
                        await queue.put(sha)
                    # show progress
                    done_cnt = len(downloaded)
                    total = done_cnt + len(pending)
                    pct = int(float(done_cnt) / total * 100)
                    message = '\rReceiving objects: {:3.0f}% ({}/{})'.format(pct, done_cnt, total)
                    self._trace(message, level=Level.INFO, exact=True)

                tasks = pending_tasks

        if total:
            self._trace('\rReceiving objects: 100% ({}/{}), done.\n'.format(done_cnt, total),
                        level=Level.INFO, exact=True)

