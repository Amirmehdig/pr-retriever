from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from pr_retriever.models import ThreadOut


def write_xml(provider: str, source_url: str, threads: list[ThreadOut], out_file: str) -> None:
    root = ET.Element(
        "pr_review",
        {
            "provider": provider,
            "source_url": source_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "open_thread_count": str(len(threads)),
        },
    )

    for thread in threads:
        attrs = {
            "id": thread.thread_id,
            "status": thread.status,
            "location": thread.location,
        }
        if thread.file_path:
            attrs["file"] = thread.file_path
        if thread.line_start:
            attrs["line_start"] = thread.line_start
        if thread.line_end:
            attrs["line_end"] = thread.line_end
        if thread.side:
            attrs["side"] = thread.side

        thread_el = ET.SubElement(root, "thread", attrs)
        comments_el = ET.SubElement(thread_el, "comments")

        for comment in thread.comments:
            cattrs: dict[str, str] = {}
            if comment.author:
                cattrs["author"] = comment.author
            if comment.username:
                cattrs["username"] = comment.username
            if comment.created_at:
                cattrs["created_at"] = comment.created_at
            if comment.comment_id:
                cattrs["id"] = comment.comment_id

            comment_el = ET.SubElement(comments_el, comment.role, cattrs)
            comment_el.text = comment.body

        ET.SubElement(thread_el, "todo")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(out_file, encoding="utf-8", xml_declaration=True)
