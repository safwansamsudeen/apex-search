# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
from __future__ import unicode_literals

from datetime import datetime

from tantivy import Document, Index, SchemaBuilder, DocAddress, SnippetGenerator

from markdownify import markdownify as md


def update_progress_bar(txt, i, l, absolute=False):
    import os, sys

    if os.environ.get("CI"):
        if i == 0:
            sys.stdout.write(txt)

        sys.stdout.write(".")
        sys.stdout.flush()
        return

    lt = len(txt)
    try:
        col = 40 if os.get_terminal_size().columns > 80 else 20
    except OSError:
        # in case function isn't being called from a terminal
        col = 40

    if lt < 36:
        txt = txt + " " * (36 - lt)

    complete = int(float(i + 1) / l * col)
    completion_bar = ("=" * complete).ljust(col, " ")
    percent_complete = f"{int(float(i + 1) / l * 100)!s}%"
    status = f"{i} of {l}" if absolute else percent_complete
    sys.stdout.write(f"\r{txt}: [{completion_bar}] {status}")
    sys.stdout.flush()


class ApexSearch:
    def __init__(self, index_path, tables, id_field="name", separator="|||"):
        self.tables = tables
        self.id_field = id_field
        self.separator = separator

        self.set_schema()
        try:
            self.index = Index.open(index_path)
        except:
            self.index = Index(self.schema, path=index_path)
        self.writer = self.index.writer()
        self.searcher = self.index.searcher()

    def set_schema(self):
        schema_builder = SchemaBuilder()
        schema_builder.add_text_field("id", stored=True)
        schema_builder.add_text_field("name", stored=True)
        schema_builder.add_text_field("title", stored=True, tokenizer_name="en_stem")
        schema_builder.add_text_field("content", stored=True, tokenizer_name="en_stem")
        schema_builder.add_json_field("fields", stored=True)
        schema_builder.add_text_field("table", stored=True)
        self.schema = schema_builder.build()

    def build_complete_index(self, obtain_func):
        # Reset index
        self.writer.delete_all_documents()
        self.writer.commit()

        total = len(self.tables)
        no_records = 0

        for i, (table, details) in enumerate(self.tables.items()):
            update_progress_bar("Indexing:", i, total)

            content_fields = details["content"]
            extra_fields = details.get("fields", [])
            title_field = details.get("title", None)

            db_records = obtain_func(
                table,
                [title_field, *content_fields, *extra_fields, self.id_field],
            )

            for record in db_records:
                title = record.pop(title_field) if title_field else ""
                fields = {}

                for extra_field in extra_fields:
                    fields[extra_field] = record.pop(extra_field)

                    # Handle dates correctly
                    if isinstance(fields[extra_field], datetime):
                        fields[extra_field] = fields[extra_field].isoformat()

                data = {
                    "id": f"{table}-{record[self.id_field]}",
                    "table": table,
                    "name": record[self.id_field],
                    "title": str(title),
                    "content": self.separator.join(
                        map(
                            lambda x: md(str(x), convert=[]),
                            (getattr(record, field) for field in content_fields),
                        )
                    ),
                    "fields": fields,
                }
                # print(data)
                self.writer.add_document(Document(**data))

                no_records += 1
        self.writer.commit()

        print()
        return no_records

    def search(self, query_text, target_number=20, fuzzy=False):
        tokens = query_text.split()
        hits = []
        highlights = []

        if fuzzy:
            NON_FUZZY_QUERY = self.index.parse_query(
                query_text, ["title", "content", "name"]
            )

        # Parse individual tokens, and try to see intersections
        for token in tokens:
            if fuzzy:
                query = self.index.parse_query(
                    token,
                    ["title", "content", "name"],
                    fuzzy_fields={"title": (True, 2, True), "content": (True, 2, True)},
                )
            else:
                query = self.index.parse_query(token, ["title", "content", "name"])

            token_hit = {
                (best_doc_address.segment_ord, best_doc_address.doc)
                for _, best_doc_address in self.searcher.search(query, 1000).hits
            }
            hits.append(token_hit)

            if fuzzy:
                query = NON_FUZZY_QUERY

            highlights.extend(highlight(token_hit, self.searcher, query, self.schema))

        # If there are no hits, there are no results for this query
        if all(not hit for hit in hits):
            if fuzzy:
                return {
                    "results": [],
                    # TBD
                    "duration": 0,
                    "total": 0,
                }
            else:
                res = self.search(query_text, target_number, True)
                return {**res, "duration": res["duration"] + 0}

        results = list(set.intersection(*hits))

        # If there are no intersecting hits, parse entire query
        if not results:
            if fuzzy:
                query = self.index.parse_query(
                    query_text,
                    ["title", "content", "name"],
                    fuzzy_fields={"title": (True, 2, True), "content": (True, 2, True)},
                )
            else:
                query = self.index.parse_query(query_text, ["title", "content", "name"])

            results.extend(
                [
                    r
                    for _, best_doc_address in self.searcher.search(
                        query, target_number // 3
                    ).hits
                    if not (r := (best_doc_address.segment_ord, best_doc_address.doc))
                    in results
                ]
            )
            if fuzzy:
                query = NON_FUZZY_QUERY

            highlights.extend(
                # Smells fishy, why results?
                highlight(results, self.searcher, query, self.schema)
            )

        result_docs = []
        for r in highlights:
            if r["addr"] in results and r not in result_docs:
                result_docs.append(r)

        result_docs = sorted(
            result_docs,
            key=lambda r: (r["no_of_title_highlights"], r["no_of_content_highlights"]),
            reverse=True,
        )

        n, final_results = len(result_docs[:target_number]), result_docs[:target_number]

        if not final_results and not fuzzy:
            res = self.search(query_text, target_number, True)
            return {**res, "duration": res["duration"] + 0}

        return {
            "results": final_results,
            "duration": 0,
            "total": n,
        }


def highlight(results, searcher, query, schema):
    title_snippet_generator = SnippetGenerator.create(searcher, query, schema, "title")
    content_snippet_generator = SnippetGenerator.create(
        searcher, query, schema, "content"
    )

    cleaned_results = []
    for segment_ord, _doc in results:
        doc = searcher.doc(DocAddress(segment_ord, _doc))
        title_snippet = title_snippet_generator.snippet_from_doc(doc)
        content_snippet = content_snippet_generator.snippet_from_doc(doc)
        print(doc)
        cleaned_results.append(
            {
                "name": doc["name"][0],
                "title": doc["title"][0],
                "content": doc["content"][0],
                "table": doc["table"][0],
                "highlighted_title": title_snippet.to_html()
                .replace("<b>", "<mark>")
                .replace("</b>", "</mark>"),
                "highlighted_content": content_snippet.to_html()
                .replace("<b>", "<mark>")
                .replace("</b>", "</mark>"),
                "no_of_title_highlights": len(title_snippet.highlighted()),
                "no_of_content_highlights": len(content_snippet.highlighted()),
                "fields": doc["fields"][0],
                "id": doc["id"][0],
                "addr": (segment_ord, _doc),
            }
        )
    return cleaned_results
