#! /usr/bin/env python2
"""

usage:

   slurpsvn <repo-name>

will create <name>-slurp.pickle, where <name> is extracted
from repo-name.


Copyright (c) 2015, Patrick Maupin.  MIT License.

This program uses the svn command to read an svn repository, and
creates and pickles a data structure based on what it finds.

The data structure is a tuple with three members:

  commits is a list of list:

    There is one inner list for each subversion revision.
    Each inner list contains a list of paths that the
    subversion log command reported changed.

  merges is also a list of lists by revision:

    Each inner list contains a list of paths that the
    subversion log command reported were merged into the
    revision.  Most of these lists will be empty.

  bypath is a dictionary, indexed by subversion file path:

    This is built using the subversion ls and cat commands
    to extract repository information based on the commits
    data received from the log command.

    The value of each dictionary entry is a list of 2-tuples.
    The first item in each tuple is the revision where this
    version of the file was placed in the repository, and the
    second item in the tuple is an identifier that maps to
    the contents of the file (allowing identical files
    at different filesystem locations to be correlated.)
    This identifier will be 0 if the file empty, or None
    if the file has been deleted.
"""

import os
import sys
import collections
import re
from subprocess import Popen, PIPE, STDOUT

try:
   import cPickle as pickle
except:
   import pickle


class SlurpSvn(object):

    def __init__(self, repo):
        self.repo = repo.rstrip('/')
        self.pathsets = collections.defaultdict(set)
        self.parselog()
        self.readrepo()

    def parselog(self):
        """ Ask subversion to dump the log verbosely,
            and parse the things we care out of it --
            commits and merge info.
        """
        repo = self.repo
        repo_str = r'-{72}\nr.+ \| .+ \| .+ \| [0-9]+ lines?\n'
        split = re.compile('(%s)' % repo_str).split
        logtext = split(self.log('-v'))
        logtext = zip(logtext[1::2], logtext[2::2])
        logtext.reverse()
        logtext[0] = logtext[0][0], logtext[0][-1].rstrip().rstrip('-')
        commits = [[]]  # Add commit zero
        merges = [[]]
        for x in logtext:
            rev, changes, mergeinfo = self.parse_one_commit(x)
            assert len(commits) == rev
            commits.append(changes)
            merges.append(mergeinfo)
        self.commits = commits
        self.merges = merges

    def parse_one_commit(self, text):
        """ Called by parselog once per commit
        """
        header, body = text
        rev, author, date, lines = (x.strip() for x in header.split('|'))
        _, rev = rev.split('\n')
        assert rev[0] == 'r' and rev[1:].isdigit()
        numlines, linetext = lines.split()
        assert linetext in ('line', 'lines'), lines
        numlines = int(numlines)
        body = body.split('\n')
        assert body.pop() == ''
        msg = body[-numlines:]
        data = body[:-numlines]
        assert data.pop(0) == 'Changed paths:'
        assert data.pop() == ''
        changes = []
        mergeinfo = []
        addpath = self.addpath
        for line in data:
            assert line[4:6] == ' /', repr(line)
            changetype = line[:4]
            path = line[5:].split(' (from ', 1)
            if len(path) > 1:
                merge, = path[1:]
                assert merge.endswith(')'), path
                mpath, mrev = merge[:-1].rsplit(':')
                mergeinfo.append((addpath(mpath), int(mrev)))
            changes.append(addpath(path[0]))
        return int(rev[1:]), changes, mergeinfo

    def readrepo(self):
        """ Once the log file has been parsed, we are ready
            to read in the directory structure and file
            contents for changes for each revision.
        """
        def content_id(content):
            return bycontents.setdefault(content, len(bycontents))

        pathsets = self.pathsets
        self.bypath = bypath = collections.defaultdict(list)
        self.bycontents = bycontents = {}
        content_id('') # Give empty file a code of 0

        for rev, changes in enumerate(self.commits):
            known_files = set()
            paths = set()
            for path in changes:
                known_files.update(self.allfiles(path, rev))
                if path not in known_files:
                    # Could be directory or deleted file
                    paths.add(path)
            unknown_paths = set()
            for path in paths:
                unknown_paths.update(pathsets[path])

            print >> sys.stderr, "Rev", rev
            for fname in known_files:
                data = content_id(self.cat(fname, rev))
                finfo = bypath[fname]
                if not finfo or finfo[-1][-1] != data:
                    finfo.append((rev, data))

            # Mark the path as deleted if it used to exist.
            for fname in unknown_paths - known_files:
                finfo = bypath[fname]
                if finfo and finfo[-1][-1] is not None:
                    finfo.append((rev, None))

    def dump(self, fname):
        """ Dump everything out to let another program
            deal with the analysis.
        """
        print >> sys.stderr, "Dumping"
        with open(fname, 'wb') as f:
            pickle.dump((self.commits, self.merges, self.bypath), f, -1)

    def allfiles(self, path, rev):
        """ Return all the files under a given path.
            Subversion is kind of loose with path handling,
            so we usually read the parent of the path to
            figure out whether it is a directory or a file.
        """
        addpath = self.addpath
        results = set()
        parent, fname = path.rsplit('/', 1)
        if fname:
            ftype = self.readdir(parent, rev).get(fname)
            if not ftype:
                if ftype is not None:
                    results.add(path)
                return results
        for fname, ftype in self.readdir(path, rev).items():
            fname = '%s/%s' % (path, fname)
            if ftype:
                results.update(self.allfiles(fname, rev))
            else:
                results.add(addpath(fname))
        return results

    def readdir(self, dirname, rev):
        """ Use "svn ls" command to read a directory.

            Return a dictionary reflecting the results.
        """
        result = {}
        for fname in self.ls(dirname, rev).split('\n'):
            if fname.endswith('/'):
                result[fname[:-1]] = True
            elif fname:
                result[fname] = False
        return result

    def addpath(self, path):
        """ Subversion is kind of loosey-goosey with
            pathspecs as returned from ls calls, so
            we make no assumptions about whether a
            path is a directory or a filename.
            We canonicalize the paths, and also
            make sets of every subpath that ever appears
            under a given path.
        """
        # This seems to be how subversion itself canonicalizes
        # a path given to the ls or cat command
        path = intern('/' + path.strip('/'))

        # pathsets is what lets us correlate a directory with
        # all the files underneath.  We describe each path as
        # being in the pathset of every one of its parent
        # directories.
        pathsets = self.pathsets
        if path not in pathsets:
            parts = path.split('/')
            parts.reverse()
            key = parts.pop()
            while parts:
                key = intern('%s/%s' % (key, parts.pop()))
                pathsets[key].add(path)
        return path

    def log(self, *options):
        options += self.repo,
        return self(False, 'log', *options)

    def ls(self, fname, rev='HEAD'):
        return self(True, 'ls', '-r' + str(rev),  self.repo + fname)

    def cat(self, fname, rev='HEAD'):
        target = '%s%s@%s' % (self.repo, fname, rev)
        return intern(self(False, 'cat', target))

    def __call__(self, err_ok, *cmd):
        p = Popen(('svn',) + cmd, stdout=PIPE, stderr=STDOUT)
        data, edata = p.communicate()
        ecode = p.returncode
        assert not edata, edata
        if err_ok:
            return data if not ecode else ''
        assert not ecode, (ecode, cmd, data)
        return data


if __name__ == '__main__':
    reponame, = sys.argv[1:]
    name = reponame.rstrip('/').rsplit('/', 1)[-1].split('-')[0]
    print name
    repo = SlurpSvn('file://%s/' % os.path.abspath(reponame))
    repo.dump('%s-slurp.pickle' % name)
