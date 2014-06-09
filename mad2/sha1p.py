
import argparse
import collections
import logging
from multiprocessing import Pool, Lock
from multiprocessing.dummy import Pool as ThreadPool
import os
import sys
import time

from lockfile import FileLock, LockTimeout

from mad2 import hash
from mad2 import util

from colorlog import ColoredFormatter
color_formatter = ColoredFormatter(
    "%(log_color)s%(name)s:%(reset)s "+
    "%(blue)s%(message)s %(purple)s(%(threadName)s)",
    datefmt=None, reset=True,
    log_colors={'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
               'CRITICAL': 'red'})

lg = logging.getLogger('sha1p')

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(color_formatter)
logging.getLogger("").handlers = [] #leip defined handlers
lg.setLevel(logging.INFO)
lg.addHandler(stream_handler)

lg.info('start sha1p')


SHADATA = collections.defaultdict(list)
LOCKED = ""

def write_to_sha1sum(hashfile, files):

    j = 0
    lg.debug("writing %d sha1sums to %s", len(files), hashfile)

    hashes = {}

    #read old sha1file
    if os.path.exists(hashfile):
        with open(hashfile) as F:
            for line in F:
                hsh, fn = line.strip().split(None, 1)
                hashes[fn] = hsh

    lg.debug("found %d hashes", len(hashes))

    #insert our sha1 - possibly overwriting other version
    for fn, hs in files:
        j += 1
        hashes[fn] = hs

    #write new sha1file
    lg.debug("now has %d hashes", len(hashes))

    try:
        lg.debug("start writing %d hashs to %s", len(hashes), hashfile)
        with open(hashfile, 'w') as F:
            for fn in sorted(hashes.keys()):
                if fn in ['QDSUMS', 'SHA1SUMS']:
                    continue
                F.write("{}  {}\n".format(hashes[fn], fn))

    except IOError:
        lg.warning("can not write to checksum file: %s", hashfile)
        return

    #fix permissions  - but only when root
    if os.geteuid() != 0:
        return j

    #change SHA1SUM file
    dirname = os.path.dirname(hashfile)
    if not dirname.strip():
        dirname = '.'
    dstats = os.stat(dirname)

    if os.path.exists(hashfile):
        os.chmod(hashfile, dstats.st_mode-73)
        os.chown(hashfile, dstats.st_uid, dstats.st_gid)

    return j



def process_file(*args, **kwargs):
    try:
        process_file_2(*args, **kwargs)
    except:
        import traceback
        traceback.print_exception()
        exit(-1)

def process_file_2(datalock, i, fn, force, echo):

    global SHADATA, LOCKED

    filename = os.path.basename(fn)
    dirname = os.path.dirname(fn)

    qd_hash_file = os.path.join(dirname, 'QDSUMS')
    sha1_hash_file = os.path.join(dirname, 'SHA1SUMS')

    sha1_file = hash.check_hashfile(sha1_hash_file, filename)

    qd = hash.get_qdhash(fn)
    qd_file = hash.check_hashfile(qd_hash_file, filename)

    if (not force) and (not sha1_file is None) and (qd == qd_file):
        #nothing changed - sha1 is present - not force - return
        return

    sha1 = hash.get_sha1sum(fn)
    lg.debug('hash of %s is %s', fn, sha1)

    datalock.acquire() #processing the SHADATA global data structure - lock
    assert(LOCKED == "")
    LOCKED = "YES"
    SHADATA[dirname].append((filename, sha1))

    if i > 0 and i % 100 == 0:
        for dirname in SHADATA:
            if len(SHADATA[dirname]) == 0:
                continue
            lg.debug('flushing to dir %s', dirname)
            hashfile = os.path.join(dirname, 'SHA1SUMS')
            write_to_sha1sum(hashfile, SHADATA[dirname])
            SHADATA[dirname] = []
        lg.info('processed & written %d files', i)

    LOCKED = ""
    datalock.release()


def dispatch():
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--force', action='store_true')
    parser.add_argument('-d', '--do_dot_dirs', action='store_true')
    parser.add_argument('-j', '--threads', type=int, default=4)
    parser.add_argument('-e', '--echo', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-s', '--silent', action='store_true')
    parser.add_argument('file', nargs='*')

    args = parser.parse_args()

    if args.verbose:
        lg.setLevel(logging.DEBUG)
    if args.silent:
        lg.setLevel(logging.WARNING)

    pool = ThreadPool(args.threads)

    dlock = Lock()

    for i, fn in enumerate(util.get_filenames(args)):
        if '/.' in fn and (not args.do_dot_dirs):
            #no dot dirs
            lg.debug("ignoring in dotdir %s", fn)
            continue
        pool.apply_async(process_file, (dlock, i, fn, args.force, args.echo))

    lg.info(("processed all (%d) files - waiting for threads to " +
            "finish"),i)
    pool.close()
    pool.join()

    lg.info("finished - flushing cache")
    for dirname in SHADATA:
        lg.debug("flushing to %s/SHA1SUMS", dirname)
        if len(SHADATA[dirname]) == 0:
                continue
        hashfile = os.path.join(dirname, 'SHA1SUMS')
        write_to_sha1sum(hashfile, SHADATA[dirname])
