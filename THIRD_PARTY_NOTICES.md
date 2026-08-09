# Third-Party Notices

xVAULT is distributed under the GNU General Public License version 3 only
(`GPL-3.0-only`), unless a file contains a more specific license notice.

The following in-tree components already contain their own license notices and
must keep those notices intact:

- `resources/lib/bookmarkDB.py` and `resources/lib/searchDB.py` include parts of
  the SimplePlugin micro-framework for Kodi content plugins and are marked as
  GPL v3.
- `scrapers/modules/dom_parser.py` is marked as free software under the GNU
  General Public License, version 3 or later.
- `scrapers/modules/jsunpack.py` contains a ResolveURL Kodi Addon notice and is
  marked as free software under the GNU General Public License, version 3 or
  later.

Runtime dependencies such as Kodi, ResolveURL, Requests, InputStream components,
TMDb/Trakt integrations and other Kodi add-ons are not vendored by this notice.
They remain under their own licenses and distribution terms.

When adding or replacing third-party code, preserve upstream copyright and
license notices and update this file if the component is stored in this
repository.
