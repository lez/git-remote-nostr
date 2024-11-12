import sys
import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from monstr.encrypt import Keys

from git_remote_blossom import git
from git_remote_blossom.util import Config, stderr
from git_remote_blossom.helper import Helper


def error(msg):
    stderr(msg)
    sys.exit(1)

async def get_helper(remote_name, url):
    """
    Return a Helper configured to point at the given URL.

    url: blossom://<npub>/<project>
    """
    url = urlparse(url)
    if url.scheme != "blossom":
        error('Git remote URL must start with "blossom://".')

    if url.password or url.username:
        raise SystemExit(
            "Git remote URL must not specify username or password.")

    sk = None
    nsec = git.get_config_value("nostr.nsec") or git.get_config_value("nostr.sec")
    if nsec:
        if nsec.startswith("nsec1"):
            # Bech32 encoded secret key
            sk = Keys(nsec)
        else:
            # Hex encoded secret key.
            # NOTE: nostr.sec=1 is a perfectly valid value for testing (npub: .
            sk = Keys('{:>064s}'.format(nsec))

    remote_npub = url.netloc
    if not remote_npub.startswith("npub1"):
        #TODO: Add support for other URL formats, see README.
        error("Invalid remote URL. Use blossom://<npub>/<project>")

    repo = url.path.split("/")[1]
    path = f"{remote_npub}/{repo}"

    helper = Helper(remote_name, sk, path)
    success = await helper.connect()
    if not success:
        error('could not connect to relay')

    return helper
