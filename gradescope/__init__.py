# -*- coding: utf-8 -*-

"""
gradescope

Provides a convenient toolkit of methods for use with Gradescope

   Name: gradescope
 Author: Edward Li and Jérémie Lumbroso
  Email: edwardli@andrew.cmu.edu
    URL: https://github.com/mooey5775/gradescope
License: Copyright (c) 2020 Edward Li, 2019 Jérémie Lumbroso, licensed under the LGPL3 license
"""

from __future__ import absolute_import

# Documentation

from gradescope.version import __version__

# Configuration file

import os as _os
import confuse as _confuse

APPNAME = "gradescope"

class GradescopeConfiguration(_confuse.LazyConfig):

    def config_dir(self):

        local_config = _os.path.join(_os.getcwd(), _confuse.CONFIG_FILENAME)
        if _os.path.exists(local_config):
            return _os.getcwd()

        return super(GradescopeConfiguration, self).config_dir()


class GradescopeConfigurationException(Exception):

    def __init__(self, section=None, src=None):
        msg = "There is an error with the configuration file.\n\n"

        if section is not None:
            msg = ("The configuration file does not contain the "
                   "correct parameters for {}.\n\n").format(section)

        if src is not None:
            msg += "Original message was: {}\n\n".format(src)

        super(GradescopeConfigurationException, self).__init__(msg)


config = GradescopeConfiguration(APPNAME, __name__)

def get_local_config(section, template):

    try:
        valid = config.get(template)

    except _confuse.NotFoundError as exc:
        raise GradescopeConfigurationException(
            section=section,
            src=exc.args,
        )

    return valid[section]

SECTION_NAME = "gradescope"

config = get_local_config(
    section=SECTION_NAME,
    template={
        SECTION_NAME: {
            "username": str,
            "password": str,
        },
    })


# Import top-level methods
from gradescope.macros import *