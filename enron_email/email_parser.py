import os
from datetime import datetime
from email.parser import Parser
from pathlib import Path


class EmailParser:
    def __init__(self, email_file_encoding):
        self.encoding = email_file_encoding
        self._parser = Parser()

    def walk(self, path):
        prefix_trim_amount = len(path) + 1
        for root, dirs, files in os.walk(path):
            user_directory = root[prefix_trim_amount:]

            # Split user_directory and sub directories into parts
            parts = Path(user_directory).parts

            # Ignore rows without sub folder
            # parts[0] is guaranteed to be a mailbox owner name
            # parts[1] exists when os.walk steps into user directory
            # and contains mail folders
            if len(parts) < 2:
                continue

            # Extract mailbox owner name
            mailbox_owner = parts[0]

            # Extract mail folder name
            mail_folder = os.path.join(parts[1], *parts[2:])

            # Index each email
            for file_name in files:
                file_path = os.path.join(root, file_name)
                email = self._parse(file_path)

                # validate email
                if email:
                    email['mail_folder'] = mail_folder
                    email['mailbox_owner'] = mailbox_owner
                    email['filename'] = file_name
                    yield email

    def _parse(self, path):
        with open(path, mode='r', encoding=self.encoding) as msg_file:
            msg = self._parser.parse(msg_file)

            # Message Id will be generated automatically by ElasticSearch
            email = {'body': msg.get_payload()}
            email['headers'] = {key: value for key, value in msg.items()}

            date = self._convert_date_to_es_format(
                email['headers'].get('Date', None)
            )
            email['headers']['Date'] = date
            return email if date is not None else None


    @staticmethod
    def _convert_date_to_es_format(date_string):
        try:
            # Example from email:
            # Thu, 2 Nov 2000 08:12:00 -0800 (PST)
            # Example from ES docs:
            # yyyy/MM/dd HH:mm:ss Z
            # First, cut off non standard time zone at the end
            date_string, _ = date_string.rsplit(' ', 1)
            date = datetime.strptime(
                date_string,
                '%a, %d %b %Y %H:%M:%S %z'
            )
            es_date = datetime.strftime(
                date,
                '%Y/%m/%d %H:%M:%S %z'
            )
            return es_date
        except ValueError:
            return None
