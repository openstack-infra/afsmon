afsmon
======

Python library and utilities for monitoring AFS file-systems using
`OpenAFS <https://www.openafs.org/>`__ tools.

Many of the details are inspired by
`<https://github.com/openafs-contrib/afs-tools>`__

Command-line
------------

The ``afsmon`` tool provides

* ``show`` : produce tabular output of key statistics for a cell,
  such as threads on file-servers, partition usage, volume usage and
  quotas.

* ``statsd`` : report similar results to a `statsd
  <https://github.com/etsy/statsd>`__ host.

Configuration is minimal, see the ``sample.cfg``.

Library
-------

The core of ``afsmon`` should suitable for use in other contexts.

.. code-block:: python

   import afsmon
   fs = afsmon.FileServerStats('hostname')
   fs.get_stats()

The ``fs`` object now contains a ``FileServerStats`` with all
available information for the server, partitions and volumes.
