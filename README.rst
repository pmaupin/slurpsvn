=======================
slurpsvn
=======================

Slurp in an SVN repository to help in git migration.

This provides a preprocessor tool for reposurgeon 3.22, and
a small example of reading in and reasoning about an svn
repository.

Later versions of reposurgeon may well include this functionality,
and of course, at some point svn will die out :-)

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
