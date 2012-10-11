#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gtk
from gimpfu import *
from batch_ex.batch_ex import BatchCodeExec


def python_ex_code():
    app = BatchCodeExec()
    gtk.main()   


register(
    "python_ex_code",
    "Python batch code execute",
    "Python batch code execute",
    "Bigboots", "Bigboots", "2012",
    "Batch Code Execute",
    "",
    [],
    [],
    python_ex_code,
    menu="<Image>/Filters/") 


main()   