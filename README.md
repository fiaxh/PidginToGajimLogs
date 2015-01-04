PidginToGajimLogs
=================

Merges Pidgin's log-files into a Gajim-style-formatted database

(Sort of) Features
------------------
Why "sort of"? Due to the log-format chosen by Pidgin it is not possible to perfectly parse them into Gajim-style-DB's.

- .txt log-files (problems if multiple lines where quoted)
- .html log-files (problems if messages actually contained html-code)
- Multi-user-chats
- Distinguish between who wrote messages

Not-Features
------------
- Status messages not parsed
- Contacts from not-jabber-protocols are not merged into (possibly existing) gateways

Usage
-----
You probably want to backup any existing Gajim-DB first.

	python3 pidgin_to_gajim_logs.py -i PATH_TO_PIDGIN_LOGS -o PATH_TO_GAJIM_DB
	-i Can hereby also point to a subset of logs