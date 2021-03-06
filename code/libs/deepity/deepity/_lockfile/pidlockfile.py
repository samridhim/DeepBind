# Copyright (c) 2015, Andrew Delong and Babak Alipanahi All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
# 
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation and/or
# other materials provided with the distribution.
# 
# 3. Neither the name of the copyright holder nor the names of its contributors
# may be used to endorse or promote products derived from this software without
# specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# Author's note: 
#     This file was distributed as part of the Nature Biotechnology 
#     supplementary software release for DeepBind. Users of DeepBind
#     are encouraged to instead use the latest source code and binaries 
#     for scoring sequences at
#        http://tools.genes.toronto.edu/deepbind/
# 
# -*- coding: utf-8 -*-

# pidlockfile.py
#
# Copyright © 2008–2009 Ben Finney <ben+python@benfinney.id.au>
#
# This is free software: you may copy, modify, and/or distribute this work
# under the terms of the Python Software Foundation License, version 2 or
# later as published by the Python Software Foundation.
# No warranty expressed or implied. See the file LICENSE.PSF-2 for details.

""" Lockfile behaviour implemented via Unix PID files.
    """

from __future__ import absolute_import

import os
import sys
import errno
import time

from . import (LockBase, AlreadyLocked, LockFailed, NotLocked, NotMyLock,
               LockTimeout)


class PIDLockFile(LockBase):
    """ Lockfile implemented as a Unix PID file.

    The lock file is a normal file named by the attribute `path`.
    A lock's PID file contains a single line of text, containing
    the process ID (PID) of the process that acquired the lock.

    >>> lock = PIDLockFile('somefile')
    >>> lock = PIDLockFile('somefile')
    """

    def __init__(self, path, threaded=False):
        # pid lockfiles don't support threaded operation, so always force
        # False as the threaded arg.
        LockBase.__init__(self, path, False)
        dirname = os.path.dirname(self.lock_file)
        basename = os.path.split(self.path)[-1]
        self.unique_name = self.path

    def read_pid(self):
        """ Get the PID from the lock file.
            """
        return read_pid_from_pidfile(self.path)

    def is_locked(self):
        """ Test if the lock is currently held.

            The lock is held if the PID file for this lock exists.

            """
        return os.path.exists(self.path)

    def i_am_locking(self):
        """ Test if the lock is held by the current process.

        Returns ``True`` if the current process ID matches the
        number stored in the PID file.
        """
        return self.is_locked() and os.getpid() == self.read_pid()

    def acquire(self, timeout=None):
        """ Acquire the lock.

        Creates the PID file for this lock, or raises an error if
        the lock could not be acquired.
        """

        end_time = time.time()
        if timeout is not None and timeout > 0:
            end_time += timeout

        while True:
            try:
                write_pid_to_pidfile(self.path)
            except OSError, exc:
                if exc.errno == errno.EEXIST:
                    # The lock creation failed.  Maybe sleep a bit.
                    if timeout is not None and time.time() > end_time:
                        if timeout > 0:
                            raise LockTimeout
                        else:
                            raise AlreadyLocked
                    time.sleep(timeout is not None and timeout/10 or 0.1)
                else:
                    raise LockFailed
            else:
                return

    def release(self):
        """ Release the lock.

            Removes the PID file to release the lock, or raises an
            error if the current process does not hold the lock.

            """
        if not self.is_locked():
            raise NotLocked
        if not self.i_am_locking():
            raise NotMyLock
        remove_existing_pidfile(self.path)

    def break_lock(self):
        """ Break an existing lock.

            Removes the PID file if it already exists, otherwise does
            nothing.

            """
        remove_existing_pidfile(self.path)

def read_pid_from_pidfile(pidfile_path):
    """ Read the PID recorded in the named PID file.

        Read and return the numeric PID recorded as text in the named
        PID file. If the PID file cannot be read, or if the content is
        not a valid PID, return ``None``.

        """
    pid = None
    try:
        pidfile = open(pidfile_path, 'r')
    except IOError:
        pass
    else:
        # According to the FHS 2.3 section on PID files in /var/run:
        # 
        #   The file must consist of the process identifier in
        #   ASCII-encoded decimal, followed by a newline character.
        # 
        #   Programs that read PID files should be somewhat flexible
        #   in what they accept; i.e., they should ignore extra
        #   whitespace, leading zeroes, absence of the trailing
        #   newline, or additional lines in the PID file.

        line = pidfile.readline().strip()
        try:
            pid = int(line)
        except ValueError:
            pass
        pidfile.close()

    return pid


def write_pid_to_pidfile(pidfile_path):
    """ Write the PID in the named PID file.

        Get the numeric process ID (“PID”) of the current process
        and write it to the named file as a line of text.

        """
    open_flags = (os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    open_mode = 0644
    pidfile_fd = os.open(pidfile_path, open_flags, open_mode)
    pidfile = os.fdopen(pidfile_fd, 'w')

    # According to the FHS 2.3 section on PID files in /var/run:
    #
    #   The file must consist of the process identifier in
    #   ASCII-encoded decimal, followed by a newline character. For
    #   example, if crond was process number 25, /var/run/crond.pid
    #   would contain three characters: two, five, and newline.

    pid = os.getpid()
    line = "%(pid)d\n" % vars()
    pidfile.write(line)
    pidfile.close()


def remove_existing_pidfile(pidfile_path):
    """ Remove the named PID file if it exists.

        Removing a PID file that doesn't already exist puts us in the
        desired state, so we ignore the condition if the file does not
        exist.

        """
    try:
        os.remove(pidfile_path)
    except OSError, exc:
        if exc.errno == errno.ENOENT:
            pass
        else:
            raise
