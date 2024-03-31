## Welcome to Apex Search

This is a library designed by [Frappe]() as a high level implementation of full text search using [Tantivy]().

### Installation
```
pip install apex-search
```

### Usage
Import `ApexSearch` and configure it:

```py
from apexsearch import ApexSearch
apex = ApexSearch('/path/to/index', CONFIG_DICT)
``` 
`CONFIG_DICT` is a dictionary with keys being the names of the tables and values being dictionaries containing the content fields (the fields that will be used in search) the "title" field (optional), and the "fields" field (optional, defaults to []).

```py
CONFIG_DICT = {
    "GP Discussion": {
        "content": ["content"],
        "extras": ["team", "project"],
        "title": "title",
    }
}
```
Initializing allows two optional arguments:
- `id_field`, the field used as an ID (primary key) in your tables. Defaults to `name`.
- `seperator`, the marker used to separate your content fields while indexing. Defaults to `|||`.
**To index:**
Apex Search will connect to the index when you initialize the class. To completely (re)build the index, use `.build_complete_index`:
```py
apex.build_complete_index(lambda table, fields: db_method(table, fields))
```

This method takes in a function that returns a list of dictionaries containing all the records to be indexed from that `table`, and the `fields` required. *Note that this deletes the previous index*.

To exclusively reindex one record, use `.reindex_record`:
```py
apex.reindex_record(record, table)
```
This reindexes the record within that table. If the `record` dictionary has the field `table`, the `table` argument is optional.

*There is currently an issue which might result in duplication of records while reindexing. If this happens, please open an issue with details.*

**To search:**
Use the `.search` method:
```py
apex.search('query to be searched')
```

This returns results in this format: note that `duration` is in milliseconds.
```py
{
    "results": [
        ...
    ],
    "duration": 16.167,
    "total": 3
}
```


Each record will be have the following keys:
- `title`: original title of the record.
- `content`: original content of the record.
- `highlighted_title`: highlighted content of the record (along with `no_of_title_highlights`).
- `highlighted_content`: highlighted content of the record (along with `no_of_content_highlights`).
- `table`: the table of the record.
- `name`: the record name as determined by `apex.id_field`.
- `id`: unique identifier of index, a string of the format `{doctype}-{name}`.
- `addr`: the address in the Tantivy index.
- `fields`: an object containing key value pairs of all the extra fields and values.

`.search` takes in the following optional arguments:
- `target_number` - the amount of results to be returned, defaults to 20.
- `fuzzy` - whether or not to use fuzzy search. By default, a non-fuzzy search is returned - if there are no results, fuzzy search is used.

