=======================
slurpsvn
=======================

Slurp in an SVN repository.

.. NOTE:: I originally wrote this code for a completely wrong reason.

I have left the code here, because it shows a simple way
to read in and reason about a subversion repository, but I
though I was going to use it in a subversion to git conversion.


Partial git merges -- just say no.
======================================

(Unlearning subversion, or confessions of a git newbie.)

Git spawns a lot of blog posts.  I think I read most of them, yet
something still tripped me up badly.  Fortunately, Eric Raymond
was there to set me straight.

Subversion has the concept of partial merging.  The DAG actually
records where things came from.  No, it's not great, but it kinda,
sorta works for some use cases.

Git doesn't.  Git has cherry-picking.  Now, you could, like I did,
try to recreate subversion partial merges so that you know where
each snippet originated, and keep the author information, etc. in
the metadata.

Don't.  It's a terrible idea.

The problem is not that you can't do it.  Git is powerful enough that
it will let you do fancy merge-fu.  You can explain to it that this
was partially merged in from here and that from there.  Your graphs
in gitk or on github will look seductively beautiful and fully match,
in your mind, what happened with the code.

The problem is that, as far as git is concerned, the partial merge you
expressed was actually a full merge, that conveys how these two branches
should be combined.  But this problem doesn't actually become apparent
until the next time you try to merge.

Since any merge is, according to git, a full merge, git thinks it conveys
intentions for downstream merges as well.  Deleted this file because you
weren't ready to merge it yet?  That's just what you think.  Git knows you
deleted it because it's extraneous, so if you merge again it will helpfully
re-delete it for you.

This is why the done thing in git is to create a branch to work on a single
problem, merge it in when you are done, and then delete it.  As far as git
is concerned, re-merging should only pick up development done in the branch
after the initial merge, e.g. for the case when somebody branched off your
branch right before you merged it.

Also, as far as git is concerned, the merge is fully symmetric -- the only
difference between merging A into B and merging B into A is which branch
name moves to the result of the merge and which one stays put.  So subsequent
merging of changes that others made off of either branch is an identical
operation.

The right git workflow mostly avoids cherry-picks, but going out of your
way to avoid them, or trying to map partial subversion merges to anything
but cherry-picks will be a disaster, notwithstanding the fact that
cherry-picking always destroys information.  Git is generally smart
enough to detect a cherry-pick in the next merge and avoid doing it
twice; the human just has to be smart enough to use the commit comments
and diffs to keep everything straight.﻿


Synopsis
=================

There are two scripts:

slurpsvn.py uses "svn log" "svn ls" and "svn cat" commands
to read in a repository, and generates a pickle file with
information about changed files and merges.  This operation will
be really slow if the repository is large or non-local
(do a local mirror first).

analyzeslurp.py uses the generated pickle file to figure
out where merge points and bogus parents are.  It dumps
operational information to stderr, and "merge" and "reparent"
commands for reposurgeon to stdout.

The reposurgeon commands should be analyzed before use.
In particular, slurpsvn does not care about metadata like
externals or executable, so it might decide that nothing
happened (and a reparent is required) upon one of these
events.

To use the commands, simply append them to the reposurgeon
.lift file.

Possible enhancements
=========================

For bigger repositories, the stored file data could
be replaced with checksums.  If storage is not a concern,
for better analysis, a more detailed file comparison could
be performed than looking for a pass/fail on a 100% match.

Other enhancements are entirely possible.  The code
is released as a simple example of reading in a
subversion repository using nothing but the svn command,
and then reasoning about it.
