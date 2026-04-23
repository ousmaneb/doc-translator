"""
DOCX in-place translation: open the ZIP, translate XML text runs, rewrite ZIP.
Preserves all formatting, images, styles — only replaces text content.
"""
import io
import re
import zipfile

from services.translate import translate_texts


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _xml_unescape(text: str) -> str:
    return (
        text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
    )


def _translate_xml_text(xml: str, from_lang: str, to_lang: str) -> str:
    """Translate text content in OOXML while preserving all markup."""

    # ── Phase 1: paragraph-level <w:t> translation ───────────────────────────
    para_re = re.compile(r"<w:p(?:\s[^>]*)?>[\s\S]*?</w:p>")
    wt_re = re.compile(r"(<w:t(?:[^>]*)>)([^<]*)(</w:t>)")

    jobs: list[dict] = []

    for pm in para_re.finditer(xml):
        para_start = pm.start()
        para_xml = pm.group(0)
        wts: list[dict] = []

        for wm in wt_re.finditer(para_xml):
            if wm.group(2).strip():
                wts.append({
                    "full": wm.group(0),
                    "open": wm.group(1),
                    "raw_text": wm.group(2),
                    "close": wm.group(3),
                    "index": para_start + wm.start(),
                })

        if wts:
            combined = " ".join(_xml_unescape(w["raw_text"]) for w in wts)
            combined = re.sub(r"\s{2,}", " ", combined).strip()
            if combined:
                jobs.append({"wts": wts, "combined": combined})

    if jobs:
        translated = translate_texts([j["combined"] for j in jobs], from_lang, to_lang)
        replacements: list[dict] = []

        for ji, job in enumerate(jobs):
            wts = job["wts"]
            trans_text = translated[ji] if ji < len(translated) else job["combined"]

            if len(wts) == 1:
                w = wts[0]
                replacements.append({
                    "index": w["index"],
                    "orig_len": len(w["full"]),
                    "replacement": w["open"] + _xml_escape(trans_text) + w["close"],
                })
            else:
                first = wts[0]
                open_tag = first["open"]
                if "xml:space" not in open_tag:
                    open_tag = open_tag.replace("<w:t", '<w:t xml:space="preserve"', 1)
                replacements.append({
                    "index": first["index"],
                    "orig_len": len(first["full"]),
                    "replacement": open_tag + _xml_escape(trans_text) + first["close"],
                })
                for w in wts[1:]:
                    replacements.append({
                        "index": w["index"],
                        "orig_len": len(w["full"]),
                        "replacement": w["open"] + w["close"],
                    })

        replacements.sort(key=lambda r: -r["index"])
        for r in replacements:
            xml = xml[: r["index"]] + r["replacement"] + xml[r["index"] + r["orig_len"] :]

    # ── Phase 2: <a:t> elements (text boxes, charts, SmartArt) ──────────────
    at_re = re.compile(r"(<a:t(?:[^>]*)>)([^<]*)(</a:t>)")
    at_segs = [
        {"full": m.group(0), "open": m.group(1), "raw_text": m.group(2), "close": m.group(3), "index": m.start()}
        for m in at_re.finditer(xml)
        if m.group(2).strip()
    ]

    if at_segs:
        at_texts = [_xml_unescape(s["raw_text"]) for s in at_segs]
        at_translated = translate_texts(at_texts, from_lang, to_lang)
        for i in range(len(at_segs) - 1, -1, -1):
            seg = at_segs[i]
            t = at_translated[i] if i < len(at_translated) else _xml_unescape(seg["raw_text"])
            xml = xml[: seg["index"]] + seg["open"] + _xml_escape(t) + seg["close"] + xml[seg["index"] + len(seg["full"]) :]

    return xml


def translate_docx_in_place(buffer: bytes, from_lang: str, to_lang: str, output_path: str) -> None:
    """Translate DOCX preserving all formatting, images, and styles."""
    translatable = {"word/document.xml"}

    with zipfile.ZipFile(io.BytesIO(buffer), "r") as zin:
        names = zin.namelist()
        for n in names:
            if (
                re.match(r"^word/(header|footer)\d*\.xml$", n)
                or re.match(r"^word/(footnotes|endnotes)\.xml$", n)
                or n == "word/comments.xml"
                or re.match(r"^word/charts/chart\d*\.xml$", n)
                or re.match(r"^word/diagrams/data\d*\.xml$", n)
                or re.match(r"^word/drawings/drawing\d*\.xml$", n)
            ):
                translatable.add(n)

        out_data: dict[str, bytes] = {}
        for name in names:
            try:
                info = zin.getinfo(name)
            except KeyError:
                continue
            if info.is_dir():
                continue

            is_xml = name.endswith(".xml") or name.endswith(".rels")

            if name in translatable:
                raw = zin.read(name).decode("utf-8", errors="replace")
                translated_xml = _translate_xml_text(raw, from_lang, to_lang)
                out_data[name] = translated_xml.encode("utf-8")
            else:
                out_data[name] = zin.read(name)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in out_data.items():
            zout.writestr(name, data)
