import sys
import asyncio

from git_remote_blossom.util import Level, stdout_to_binary
from git_remote_blossom.cli.common import error, get_helper


async def _main():
    """
    Main entry point for git-remote-nostr Git remote helper.
    """
    # configure system
    stdout_to_binary()

    remote_name = sys.argv[1]
    url = sys.argv[2]
    # print("remote {} {}".format(remote_name, url), file=sys.stderr)
    helper = await get_helper(remote_name, url)
    try:
        await helper.run()
    except Exception:
        if helper.verbosity >= Level.DEBUG:
            raise  # re-raise exception so it prints out a stack trace
        else:
            error('unexpected exception (run with -v for details)')
    except KeyboardInterrupt:
        # exit silently with an error code
        exit(1)

def main():
    asyncio.run(_main())
