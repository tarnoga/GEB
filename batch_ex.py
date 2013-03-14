#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
from gimpfu import *
from os import path

import gettext, locale
from pdb import set_trace

gettext.install('GEB',path.join(path.dirname(__file__),
    'batch_ex','locale'),unicode=True)
locale.bindtextdomain('GEB',path.join(path.dirname(__file__),
    'batch_ex','locale'))

from batch_ex.batch_ex import BatchCodeExec


def python_ex_code():
    app = BatchCodeExec()
    gtk.main()   


register(
    "python_ex_code",
    "Python batch code execute",
    "Python batch code execute",
    "Bigboots", "Bigboots", "2012",
    _("Batch Code Execute"),
    "",
    [],
    [],
    python_ex_code,
    menu="<Image>/Filters/") 


main()   