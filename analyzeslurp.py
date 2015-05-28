#! /usr/bin/env python2
"""

Copyright (c) 2015, Patrick Maupin.  MIT License.

usage:

    analyzeslurp.py <slurp-pickle>

Analyze the pickle produced by slurpsvn, to figure
out where the merge points are.

This analysis was split out from slurpsvn to make it
easier to iterate on the logic.
"""

import sys
import collections
import bisect
import itertools
from sys import stderr

try:
   import cPickle as pickle
except:
   import pickle

def branchranges(bypath, branchrevs):
    class BranchRange(list):
        """ An object that contains a set
            of places where a file could
            have come from.  The set is
            a tuple (branch, lowrev, hirev).

            Even though logically a set, it
            is stored as a list to reduce
            operation confusion.
        """

        def __and__(self, other):
            if not isinstance(other, BranchRange):
                return other and self
            branches = set()
            for ab, al, ah in self:
                for bb, bl, bh in other:
                    if ab != bb:
                        continue
                    cl = max(al, bl)
                    ch = min(ah, bh)
                    if cl >= ch:
                        continue
                    branches.add((ab, cl, ch))
            return BranchRange(branches) or False

        def __rand__(self, other):
            return self & other

        def __or__(self, other):
            if not isinstance(other, BranchRange):
                return other or self
            mydict = collections.defaultdict(list)
            for ab, al, ah in self + other:
                mydict[ab].append((al, ah))

            branches = set()
            for ab, mylist in mydict.items():
                mylist.sort()
                for i in range(len(mylist) - 1, 0, -1):
                    if mylist[i][0] <= mylist[i - 1][1]:
                        mylist[i - 1: i + 1] = [(mylist[i - 1][0], mylist[i][1])]
                for al, ah in mylist:
                    branches.add((ab, al, ah))
            return BranchRange(branches)

        def __ror__(self, other):
            return self | other

        def choose_best(self, branch):
            if len(self) > 1:
                choices = collections.defaultdict(list)
                for x in self:
                    choices[x[0]].append(x)
                self = choices[branch] or self
                self = choices['trunk'] or self
                self.sort()
            return self and self[-1][:2]

    def factory(pathrev, target_branch, target_rev):
        path, rev = pathrev
        branch = branchinfo(path)
        try:
            info = bypath[path]
        except KeyError:
            info = branchrevs[branch]
        index = bisect.bisect(info, rev)
        low = info[index-1] if index else -1
        high = info[index] if index < len(info) else low + 1

        assert low <= target_rev
        if high >= target_rev and branch == target_branch:
            # Preexisting file on previous revision same branch
            return True
        return BranchRange([(branch, low, high)])


    return factory



def branchinfo(path):
    """ The branchinfo doesn't actually have to match
        correct branch name.  It merely has to correctly
        identify different branches based on svn file system
        location.
    """
    stuff = path.split('/', 3) + ['']
    assert not stuff.pop(0)
    branch = stuff[0]
    two_levels = '/'.join(stuff[:2])
    branch = branch.replace('tags', two_levels)
    branch = branch.replace('branches', two_levels)
    branch = branch.replace('wiki', 'trunk')
    return branch

def get_filemap(bypath, maxrev):
    filemap = collections.defaultdict(set)
    byrev = collections.defaultdict(set)
    new_bypath = {}
    for path, items in bypath.items():
        if not items:
            continue
        new_items = [-1, maxrev]
        for revid, textid in items:
            new_items.append(revid)
            byrev[revid].add(path)
            if textid:
                filemap[textid].add((path, revid))
        new_bypath[path] = sorted(new_items)

    identical = collections.defaultdict(set)
    for myset in filemap.values():
        mylist = sorted(myset, key=lambda x: x[1])
        for i in range(1, len(mylist)):
            identical[mylist[i]].update(mylist[:i])

    return new_bypath, byrev, identical

def analyze(commits, merges, bypath):
    dirnames = set()

    spurious = set()
    revbranches = collections.defaultdict(str)
    branchrevs = collections.defaultdict(list)

    assert len(commits) == len(merges)
    bypath, byrev, identical = get_filemap(bypath, len(commits))
    BranchRange = branchranges(bypath, branchrevs)

    for rev, (commit, merge) in enumerate(zip(commits, merges)):
        dirnames.update(x for x in commit if x not in bypath)
        requested = [x for x in commit if x in bypath]
        actual = byrev[rev]
        branches = collections.defaultdict(int)
        for x in itertools.chain(actual, requested):
            branches[branchinfo(x)] += 1
        allbranches = sorted(branches.items(), key = lambda x: (x[1], x[0]))
        branch = allbranches[0][0] if allbranches else '<nonexistent>'
        revbranches[rev] = branch
        myrevs = branchrevs[branch]
        myrevs.append(rev)

        if not actual:
            print >> stderr, "Spurious", branch, rev
            spurious.add(rev)
            continue

        reparenting = None
        while len(myrevs) > 1 and myrevs[-2] in spurious:
            del myrevs[-2]
            reparenting = myrevs[-2]
        if reparenting:
            print >> stderr, "Reparenting %s to %s" % (rev, reparenting)
            print '<%s>,<%s> reparent' % (reparenting, rev)

        brange = True
        for stuff in merge:
            brange &= BranchRange(stuff, branch, rev)
        copied = [identical[path, rev] for path in actual]
        copied = [x for x in copied if x]
        for pathinfo in copied:
            pathrange = False
            for stuff in pathinfo:
                pathrange |= BranchRange(stuff, branch, rev)
            brange &= pathrange

        if brange is not True:
            brange = brange and brange.choose_best(branch)
            print >> stderr
            print >> stderr,  "Target", rev, branch, brange if brange else '*************'
            if brange:
                print '<%s>,<%s> merge' % (brange[1], rev)



if __name__ == '__main__':
    picklename, = sys.argv[1:]
    with open(picklename, 'rb') as f:
        pickled = pickle.load(f)
    analyze(*pickled)
