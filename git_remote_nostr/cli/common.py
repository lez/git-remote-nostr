import sys
import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from monstr.encrypt import Keys

from git_remote_nostr import git
from git_remote_nostr.util import Config, stderr
from git_remote_nostr.helper import Helper


def error(msg):
    stderr(msg)
    sys.exit(1)

async def get_helper(remote_name, url):
    """
    Return a Helper configured to point at the given URL.

    url: nostr://<npub>/<project>
    """
    url = urlparse(url)
    if url.scheme != "nostr":
        error('Git remote URL must start with "nostr://".')

    if url.password or url.username:
        raise SystemExit(
            "Git remote URL must not specify username or password.")

    sk = None
    nsec = git.get_config_value("nostr.nsec") or git.get_config_value("nostr.sec")
    if nsec:
        if nsec.startswith("nsec1"):
            sk = Keys(nsec)
        else:
            # nostr.sec=1 is valid.
            sk = Keys('{:>064s}'.format(nsec))

    remote_npub = url.netloc
    if not remote_npub.startswith("npub1"):
        #TODO: Add support for nevent1 and nip5 remote URL.
        error("Invalid remote URL. Use nostr://<npub>/<project>")

    repo = url.path.split("/")[1]
    path = f"{remote_npub}/{repo}"

    helper = Helper(remote_name, sk, path)
    success = await helper.connect()
    if not success:
        error('could not connect to relay')

    return helper
