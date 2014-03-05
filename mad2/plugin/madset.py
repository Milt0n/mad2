
import logging
import os
import sys
import tempfile
import subprocess

from dateutil.parser import parse as dateparse
import leip

from mad2.util import  get_mad_file, get_all_mad_files
from mad2.ui import message, error, errorexit
import mad2.ui

lg = logging.getLogger(__name__)


##
## define unset
##
@leip.arg('file', nargs="+")
@leip.arg('key')
@leip.arg('-e', '--echo', help='echo ')
@leip.command
def unset(app, args):
    lg.debug("unsetting: %s".format(args.key))
    key = args.key
    keyinfo = app.conf.get_branch('keywords.{}'.format(key))
    if keyinfo.get('cardinality', '1') == '+':
        errorexit("Not implemented - unsetting keys with cardinality > 1")

    for madfile in get_all_mad_files(app, args):
        #print(madfile)
        #print(madfile.mad.pretty())
        if args.key in madfile.mad:
            del(madfile.mad[args.key])

        madfile.save()

def _getkeyval(app, key, val, force):

    # First check if this will become a list.
    list_mode = False
    if key[0] == '+':
        lg.debug("treating {} as a list".format(key))
        list_mode = True
        key = key[1:]

    keyinfo = app.conf.get_branch('keywords.{}'.format(key))
    keytype = keyinfo.get('type', 'str')

    if (not force) and (not keyinfo.get('description')):
        errorexit('invalid key: "{0}" (use -f?)'.format(key))

    if list_mode and str(keyinfo.get('cardinality', '1')) == '1':
        errorexit("Cardinality == 1 - no lists!")
    elif keyinfo.get('cardinality', '1') == '+':
        list_mode = True

    if keytype == 'int':
        try:
            val = int(val)
        except ValueError:
            lg.error("Invalid integer: %s" % val)
            sys.exit(-1)
    elif keytype == 'float':
        try:
            val = float(val)
        except ValueError:
            lg.error("Invalid float: %s" % val)
            sys.exit(-1)
    elif keytype == 'boolean':
        if val.lower() in ['1', 'true', 't', 'yes', 'aye', 'y', 'yep']:
            val = True
        elif val.lower() in ['0', 'false', 'f', 'no', 'n', 'nope']:
            val = False
        else:
            lg.error("Invalid boolean: %s" % val)
            sys.exit(-1)
    elif keytype == 'date':
        try:
            val = dateparse(val)
        except ValueError:
            lg.error("Invalid date: %s" % val)
            sys.exit(-1)
        lg.debug("date interpreted as: %s" % val)

    if keytype == 'restricted':
        allowed = keyinfo.get_branch('allowed')
        if not val in allowed.keys():
            errorexit("Value '{0}' not allowed for key '{1}'".format(val, key))

    return key, val, list_mode

@leip.arg('file', nargs='*')
@leip.arg('-k', '--kv', help='key & value to set', metavar=('key', 'val'),
                nargs=2, action='append')
@leip.usage("usage: mad mset [-h] [-f] [-e] -k key val [[-k key val] ...] [file [file ...]]")
@leip.arg('-f', '--force', action='store_true', help='apply force')
@leip.arg('-e', '--echo', action='store_true', help='echo filename')
@leip.command
def mset(app, args):
    """
    Set multiple key/value pairs.
    """
    all_kvs = []
    for k, v in args.kv:
        all_kvs.append(_getkeyval(app, k, v, args.force))

    for madfile in get_all_mad_files(app, args):
        for key, val, list_mode in all_kvs:
            if list_mode:
                if not key in madfile:
                    oldval = []
                else:
                    oldval = madfile[key]
                    if not isinstance(oldval, list):
                        oldval = [oldval]
                madfile.mad[key] = oldval + [val]

            else:
                #not listmode
                madfile.mad[key] = val

        if args.echo:
            print(madfile.filename)
        madfile.save()


@leip.arg('-f', '--force', action='store_true', help='apply force')
@leip.arg('-p', '--prompt', action='store_true', help='show a prompt')
@leip.arg('-d', '--editor', action='store_true', help='open an editor')
@leip.arg('-e', '--echo', action='store_true', help='echo filename')
@leip.arg('file', nargs='*')
@leip.arg('value', help='value to set', nargs='?')
@leip.arg('key', help='key to set')
@leip.command
def set(app, args):
    """
    Set a key/value for one or more files.

    Use this command to set a key value pair for one or more files.

    This command can take the following forms::

        mad set project test genome.fasta
        ls *.fasta | mad set project test
        find . -size +10k | mad set project test

    """

    key = args.key
    val = args.value


    if args.prompt or args.editor:
        if not args.value is None:
            # when asking for a prompt - the next item on sys.argv
            # is assumed to be a file, and needs to be pushed
            # into args.file
            args.file = [args.value] + args.file

    madfiles = []

    #gather all madfiles for later parsing
    use_stdin = not (args.prompt or args.editor)
    for m in get_all_mad_files(app, args, use_stdin):
        madfiles.append(m)

    #check if mad needs to show a prompt or editor
    if val is None and not (args.prompt or args.editor):
        args.prompt = True

    # show prompt or editor
    if args.prompt or args.editor:
        # get a value from the user

        default = ''
        #Show a prompt asking for a value
        data = madfiles[0]
        default = madfiles[0].get(key, "")

        if args.prompt:
            sys.stdin = open('/dev/tty')
            val = mad2.ui.askUser(key, default, data)
            sys.stdin = sys.__stdin__

        elif args.editor:
            editor = os.environ.get('EDITOR','vim')
            tmp_file = tempfile.NamedTemporaryFile('wb', delete=False)

            #write default value to the tmp file
            if default:
                tmp_file.write(default + "\n")
            else:
                tmp_file.write("\n")
            tmp_file.close()

            tty = open('/dev/tty')

            subprocess.call('{} {}'.format(editor, tmp_file.name),
                stdin=tty, shell=True)
            sys.stdin = sys.__stdin__


            #read value back in
            with open(tmp_file.name, 'r') as F:
                #removing trailing space
                val = F.read().rstrip()
            #remove tmp file
            os.unlink(tmp_file.name)

    #process key & val
    key, val, list_mode = _getkeyval(app, key, val, args.force)

    # Now process madfiles
    lg.debug("processing %d files" % len(madfiles))

    for madfile in madfiles:
        if list_mode:
            if not key in madfile:
                oldval = []
            else:
                oldval = madfile.get(key)
                if not isinstance(oldval, list):
                    oldval = [oldval]
            madfile.stack[1][key] = oldval + [val]
        else:
            #not listmode
            madfile.stack[1][key] = val

        if args.echo:
            print(madfile['filename'])
        madfile.save()
