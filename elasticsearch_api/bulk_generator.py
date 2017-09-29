from elasticsearch_api import Bulk


class BulkGenerator:
    def __init__(
            self,
            bulk_index_definition,
            bulk_size,
            item_generator):

        self.bulk_index_definition = bulk_index_definition
        self.bulk_size = bulk_size
        self.item_generator = item_generator

    def generate(self):
        bulk = Bulk(self.bulk_index_definition)

        # yield items in portions
        for item in self.item_generator:
            bulk.add(item)

            if bulk.size % self.bulk_size == 0:
                yield bulk
                bulk.clear()

        # yield last portion smaller than bulk_size
        if bulk.size:
            yield bulk
