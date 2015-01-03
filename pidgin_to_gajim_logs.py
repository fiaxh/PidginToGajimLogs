import fnmatch
import os
import re
import datetime
import calendar
import sqlite3
import optparse

import html2text

protocols = []


class Protocol(object):
    def __init__(self, name):
        self.name = name
        self.accounts = []

    def add_account(self, account):
        self.accounts.append(account)

    def contains_account(self, account_name):
        for account in self.accounts:
            if account.name == account_name:
                return account
        return None


class Account(object):
    def __init__(self, name):
        self.name = name
        self.contacts = []

    def add_contact(self, contact):
        self.contacts.append(contact)

    def contains_contact(self, contact_name):
        for contact in self.contacts:
            if contact.name == contact_name:
                return contact
        return None


class Contact(object):
    def __init__(self, name, group_chat=False):
        self.name = name
        self.alias = []
        self.messages = []
        self.group_chat = group_chat

    def add_message(self, message):
        self.messages.append(message)


class Message(object):
    def __init__(self, name, time, kind, show, message, subject):
        """
        :param kind: -1 if unknown
        """
        self.name = name
        self.time = time
        self.kind = kind
        self.show = show
        self.message = message
        self.subject = subject


def get_make_contact(root):
    """Integrates contact into protocol-account-contact-message-datastructure and returns it
    :param root: path to folder one level above log files
    :return: contact-object for that path
    """
    root_split = root.split('/')

    contact_name = root_split[-1]
    #groupchat's folder's end with .chat
    group_chat = False
    if contact_name.endswith(".chat"):
        contact_name = contact_name[:-5]
        group_chat = True

    account_name = root_split[-2]
    protocol_name = root_split[-3]

    protocol_contained = None
    for protocol in protocols:
        if protocol.name == protocol_name:
            protocol_contained = protocol
            break
    if not protocol_contained:
        protocol_contained = Protocol(protocol_name)
        protocols.append(protocol_contained)

    account_contained = protocol_contained.contains_account(account_name)
    if not account_contained:
        account_contained = Account(account_name)
        protocol_contained.add_account(account_contained)

    contact_contained = account_contained.contains_contact(contact_name)
    if not contact_contained:
        contact_contained = Contact(contact_name, group_chat)
        account_contained.add_contact(contact_contained)

    return contact_contained, account_contained


def add_message(name, time, message_text, root):
    """Adds message to global data-structure
    :param name: Name of person who wrote the msg
    :param time: Unix-timestamp of msg
    :param message_text:
    :param root: path to file (without filename)
    """
    (contact, account) = get_make_contact(root)

    show = None
    subject = None

    group_chat = False
    if root.endswith(".chat"):
        group_chat = True

    #actions
    if message_text and message_text.startswith("***"):
        for alias in contact.alias:
            if message_text.startswith("***" + alias) or message_text.startswith("*****" + alias + "**"):
                name = alias
                message_text = message_text.replace("*****" + alias + "**", "/me")
                message_text = message_text.replace("***" + alias, "/me")

    #not: status updates and encrypted messages
    if not name or name.startswith("The following message received from") or name == "OTR Error":
        return

    #more actions
    if name.startswith("***"):
        for alias in contact.alias:
            if name.startswith("***" + alias) or name.startswith("*****" + alias + "**"):
                message_text = name.replace("*****" + alias + "**", "/me")
                message_text = message_text.replace("***" + alias, "/me")
                name = alias

    kind = -1
    if group_chat:
        if name not in contact.alias:
            contact.alias.append(name)
        kind = 2
    else:
        if name not in contact.alias:
            contact.alias.append(name)

    message = Message(name, time, kind, show, message_text, subject)
    contact.add_message(message)

regex_date = re.compile("(\d{4})-(\d{2})-(\d{2})")

regex_html_time = re.compile(".*?>\(.*?(\d{2}):(\d{2}):(\d{2}).*?\).*")
regex_html_rest = re.compile(".*?>\(\d{2}:\d{2}:\d{2}.*?\)(.*)")
regex_html = re.compile(".*?>\(\d{2}:\d{2}:\d{2}.*?\)<.*?<b>(.*?):</b>(.*)")


def parse_html(root, filename):
    """Parses pidgin's html-formated log-files
    HTML within messages is converted to normal text, so messages about HTML-code will get lost
    :param root: Path to folder with logs by contact
    :param filename: Log-file (html) to be parsed
    """

    root_filename = os.path.join(root, filename)

    match_date = regex_date.findall(filename)
    if not match_date:
        raise Exception(root_filename, 'r')

    year = int(match_date[0][0])
    month = int(match_date[0][1])
    day = int(match_date[0][2])

    file = open(root_filename)
    lines = file.readlines()
    for line in lines[1:]:
        match_time = regex_html_time.match(line)
        if match_time:
            hour = int(match_time.group(1))
            minute = int(match_time.group(2))
            second = int(match_time.group(3))
            time = datetime.datetime(year, month, day, hour, minute, second)
            timestamp = calendar.timegm(time.utctimetuple())

            match_html = regex_html.match(line)
            if match_html:
                name = match_html.group(1)

                message_text = html2text.html2text(match_html.group(2)).replace("\\n", "\n").strip()

                add_message(name, timestamp, message_text, root)

            else:
                match_rest = regex_html_rest.match(line)
                message_text = None
                if match_rest:
                    message_text = html2text.html2text(match_rest.group(1)).replace("\\n", "\n").strip()
                add_message(None, timestamp, message_text, root)

regex_txt_time = re.compile("\(.*?(\d{2}):(\d{2}):(\d{2}).*")
regex_txt_rest = re.compile("\(\d{2}:\d{2}:\d{2}.*?\) (.*)")
regex_txt = re.compile("\(\d{2}:\d{2}:\d{2} .*\) (.*?): (.*)")


def parse_txt(root, filename):
    """Parses pidgin's txt-formated log-files
    :param root: Path to folder with logs by contact
    :param filename: Log-file (txt) to be parsed
    """

    root_filename = os.path.join(root, filename)

    match_date = regex_date.findall(filename)
    if not match_date:
        raise Exception(root_filename, 'r')

    year = int(match_date[0][0])
    month = int(match_date[0][1])
    day = int(match_date[0][2])

    file = open(root_filename)
    lines = file.readlines()

    i = 0
    while i < len(lines):
        match_time = regex_txt_time.match(lines[i])
        if match_time:
            hour = int(match_time.group(1))
            minute = int(match_time.group(2))
            second = int(match_time.group(3))
            time = datetime.datetime(year, month, day, hour, minute, second)
            timestamp = calendar.timegm(time.utctimetuple())

            match_txt = regex_txt.match(lines[i])
            if match_txt:

                name = match_txt.group(1)
                message_text = match_txt.group(2).strip()

                i += 1
                if i < len(lines):
                    match_time = regex_txt_time.match(lines[i])
                    while not match_time and i < len(lines):
                        message_text += "\n" + lines[i].strip()
                        i += 1
                        if i < len(lines):
                            match_time = regex_txt_time.match(lines[i])

                add_message(name, timestamp, message_text, root)
            else:
                match_rest = regex_txt_rest.match(lines[i])
                message_text = None
                if match_rest:
                    message_text = match_rest.group(1)
                add_message(None, timestamp, message_text, root)
                i += 1
        else:
            i += 1


def database_insert(db):
    """Insert messages (from global data-structure) into db
    :param db: Path to db to insert into
    """
    con = sqlite3.connect(db)
    cur = con.cursor()
    for protocol in protocols:
        if protocol.name == "jabber":
            for account in protocol.accounts:
                for contact in account.contacts:
                    print("Inserting", contact.name)
                    cur.execute("SELECT jid_id FROM jids WHERE jid=\"" + contact.name + "\"")
                    jid_id = cur.fetchone()

                    #contact doesn't exist in db
                    if not jid_id:
                        print("Adding", contact.name)
                        if contact.group_chat:
                            value = 1
                        else:
                            value = 0
                        cur.execute("INSERT INTO jids(jid, type) VALUES(?, ?)", (contact.name, value))
                        cur.execute("SELECT jid_id FROM jids WHERE jid=\"" + contact.name + "\"")
                        jid_id = cur.fetchone()

                    #insert msg
                    jid_id = jid_id[0]
                    for message in contact.messages:
                        if message.kind == 2:
                            sql_insert = jid_id, message.name, message.time, message.kind, message.message
                            print(sql_insert)
                            cur.execute("SELECT * FROM logs WHERE jid_id=? and contact_name=? and time=? and kind=? and message=?", sql_insert)
                            if not cur.fetchone():
                                cur.execute("INSERT INTO logs(jid_id, contact_name, time, kind, message) VALUES(?, ?, ?, ?, ?)", sql_insert)
                        elif message.kind == 4 or message.kind == 6:
                            sql_insert = jid_id, message.time, message.kind, message.message
                            cur.execute("SELECT * FROM logs WHERE jid_id=? and time=? and kind=? and message=?", sql_insert)
                            if not cur.fetchone():
                                cur.execute("INSERT INTO logs(jid_id, time, kind, message) VALUES(?, ?, ?, ?)", sql_insert)

    con.commit()
    con.close()


def parse_dir(root, filenames):
    """Parses files into global datastructure
    :param root: Path to files to parse
    :param filenames: Files to parse
    """
    for filename in fnmatch.filter(filenames, '*.html'):
        parse_html(root, filename)
    for filename in fnmatch.filter(filenames, '*.txt'):
        parse_txt(root, filename)


def names_interaction():
    """Asks user for own nicks after listing all encountered ones
    :return:List of entered nicks
    """
    already_printed = []
    for protocol in protocols:
        for account in protocol.accounts:
            for contact in account.contacts:
                for message in contact.messages:
                    if message.name not in already_printed:
                        already_printed.append(message.name)
                        print(message.name)
    nicks = input("Own nicks, comma separated: ")
    nicks = nicks.split(",")
    nicks = [nick.strip() for nick in nicks]
    return nicks


def message_update_kind(alias_me):
    """Updates global data-structure with message type (own, not own)
    :param alias_me: list of nicks of self
    """
    for protocol in protocols:
        for account in protocol.accounts:
            for contact in account.contacts:
                for message in contact.messages:
                    #if kind not jet known
                    if message.kind == -1:
                        if message.name in alias_me:
                            message.kind = 6
                        else:
                            message.kind = 4


def main():
    parser = optparse.OptionParser()
    parser.add_option("-i", "--indir", action="store", type="string", dest="in_dir")
    parser.add_option("-o", "--outfile", action="store", type="string", dest="out_file")
    parser.parse_args()

    own_checked = []

    for root, dirnames, filenames in os.walk(parser.values.in_dir):
        print("Parsing", root)

        parse_dir(root, filenames)

    alias_me = names_interaction()
    message_update_kind(alias_me)
    database_insert(parser.values.out_file)

if __name__ == '__main__':
    main()