import json


class Bulk:
    def __init__(self, index_definition):
        self._index_definition_line = json.dumps(index_definition)
        self.contents = ''
        self.size = 0

    def add(self, obj):
        self.contents += self._index_definition_line + '\n'
        self.contents += json.dumps(obj) + '\n'
        self.size += 1

    def clear(self):
        self.contents = ''
        self.size = 0
