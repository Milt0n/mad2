import logging
import os

import fantail

from mad2.exception import MadPermissionDenied
from mad2.recrender import recrender

lg = logging.getLogger(__name__)
# lg.setLevel(logging.DEBUG)


def dummy_hook_method(*args, **kw):
    return None


STORES = None


class MadFile(fantail.Fanstack):

    """
    Represents a single file
    """

    def __init__(self,
                 inputfile,
                 stores=None,
                 base=fantail.Fantail(),
                 hook_method=dummy_hook_method):

        self.stores = stores
        self.hook_method = hook_method

        lg.debug('madfile start %s', inputfile)
        super(MadFile, self).__init__(
            stack=[fantail.Fantail(),
                   base.copy()])

        self.dirmode = False
        if os.path.isdir(inputfile):
            self.dirmode = True
            dirname = inputfile
            filename = ''
        else:
            dirname = os.path.dirname(inputfile)
            filename = os.path.basename(inputfile)

        lg.debug(
            "Instantiating a madfile for '{}' / '{}'".format(
                dirname, filename))

        self.all['inputfile'] = inputfile
        self.all['dirname'] = os.path.abspath(dirname)
        self.all['filename'] = filename
        self.all['fullpath'] = os.path.abspath(inputfile)

        self.mad['sha1sum'] = ""
        #self.all['sha1sum'] = ""

        if not os.path.exists(inputfile):
            self.all['orphan'] = True

        for s in self.stores:
            store = self.stores[s]
            store.prepare(self)

        self.load()

    def render(self, template, data):
        """
        Render a template from, adding self to the context
        """
        if not isinstance(data, list):
            data = [data]
        return recrender(template, [self] + data)

    @property
    def mad(self):
        return self.stack[0]

    @property
    def all(self):
        return self.stack[1]

    def __str__(self):
        return '<mad2.madfile.MadFile {}>'.format(self['inputfile'])

    def check_sha1sum(self):
        import mad2.hash
        mad2.hash.get_sha1sum_mad(self)

    def load(self):

        if os.path.exists(self.all['inputfile']):
            self.all['orphan'] = False
        else:
            self.all['orphan'] = True

        self.hook_method('madfile_pre_load', self)

        for s in self.stores:
            store = self.stores[s]
            store.load(self)

        self.hook_method('madfile_load', self)
        self.hook_method('madfile_post_load', self)

    def save(self):
        self.hook_method('madfile_save', self)
        self.hook_method('madfile_pre_save', self)

        for s in self.stores:
                store = self.stores[s]
                store.save(self)

        self.hook_method('madfile_post_save', self)
