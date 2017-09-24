#!/usr/bin/env python
# 
# Logic for parsing the Enron Email Corpus Database
# and loading it into MongoDB.
#
# This script is based on work by Bryan Nehl (http://soloso.blogspot.com/2011/07/getting-enron-mail-database-into.html)
# 
# The Enron source data is available at http://www.cs.cmu.edu/~enron/

import os
import sys
import datetime
from pymongo import Connection
from email.parser import Parser


__author__ = 'k0emt'
MAX_RUN_SIZE = 1
counter = 1
p = Parser()

def getFileContents(nameOfFileToOpen):
    dataFile = open(nameOfFileToOpen)
    contents = ""
    try:
        for dataLine in dataFile:
            contents += dataLine

    finally:
        dataFile.close()
    return contents.decode('cp1252')

def saveToDatabase(mailboxOwner, subFolder, filename, contents):
    msg = p.parsestr(contents.encode("utf-8"))
    document = {"mailbox" : mailboxOwner,
                "subFolder" : subFolder,
                "filename" : filename,
                "headers": dict( msg._headers ),
                "body": msg._payload,
                }

    messages = db.messages
    messages.insert(document)
    return

if __name__ == "__main__":

    if len(sys.argv) < 2:
        raise Exception("Please specify the path to the enron data.")
    else:
        MAIL_DIR_PATH = sys.argv[1]
        if not os.path.isdir(MAIL_DIR_PATH):
            raise Exception("Invalid or not found path for Enron Input: %s" % MAIL_DIR_PATH)

    PREFIX_TRIM_AMOUNT = len(MAIL_DIR_PATH) + 1
    cn = Connection('localhost')
    db = cn.enron_mail
    print "database initialized {0}".format(datetime.datetime.now())

    for root, dirs, files in os.walk(MAIL_DIR_PATH,topdown=False):
        directory = root[PREFIX_TRIM_AMOUNT:]

        # extract mail box owner
        parts = directory.split('/', 1)
        mailboxOwner = parts[0]

        # sub-folder info
        if 2 == len(parts):
            subFolder = parts[1]
        else:
            subFolder = ''

        # distinct file name
        for filename in files:

            # get the file contents
            nameOfFileToOpen = "{0}/{1}".format(root,filename)
            contents = getFileContents(nameOfFileToOpen)
            saveToDatabase(mailboxOwner, subFolder, filename, contents)

            counter += 1
            if counter % 100 == 0:
                print("{0} {1}".format(counter,datetime.datetime.now()))

    db.close
    print "database closed {0}".format(datetime.datetime.now())
    print "{0} total records processed".format(counter - 1)
