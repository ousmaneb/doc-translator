import os
import re
import time

import httpx

try:
    import deepl as deepl_sdk
    DEEPL_AVAILABLE = True
except ImportError:
    DEEPL_AVAILABLE = False

SEP = "\n\n"


def should_translate(text: str) -> bool:
    t = text.strip()
    if not t or len(t) <= 2:
        return False
    if re.fullmatch(r"[\d\s,.''/\\|—–\-@#%*()\[\]{}<>^~`!?:;]+", t):
        return False
    if re.match(r"^[$€£¥₹]", t):
        return False
    if re.match(r"^\d", t) and re.fullmatch(r"[\d,.%]+", t):
        return False
    if re.fullmatch(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", t):
        return False
    if re.match(r"^https?://", t):
        return False
    if re.fullmatch(r"[A-Z]{2}\d{5,}[A-Z]?", t):
        return False
    if re.match(r"^[A-Z]{2,6}[-_]\d{5,}", t):
        return False
    return True


def detect_language(text: str) -> str:
    s = text[:3000].lower()
    fr = len(re.findall(
        r"\b(le|la|les|de|des|du|et|est|en|un|une|pour|que|qui|dans|pas|sur|"
        r"au|aux|je|tu|il|elle|nous|vous|ils|elles|mon|ton|son|ma|ta|sa|mais|"
        r"ou|donc|ni|car|par|avec|cette|tout|plus|très|bien|même|aussi|comme)\b", s
    ))
    en = len(re.findall(
        r"\b(the|is|are|was|were|been|have|has|had|do|does|did|will|would|could|"
        r"should|may|might|a|an|and|or|but|in|on|at|to|for|of|with|by|from|this|"
        r"that|these|those|it|its|not|all|also|just|more|can|about|up|out|one|"
        r"they|their)\b", s
    ))
    return "fr" if fr > en else "en"


def _build_batches(items: list[tuple[int, str]], max_len: int) -> list[tuple[list[int], list[str]]]:
    batches: list[tuple[list[int], list[str]]] = []
    cur_idx: list[int] = []
    cur_txt: list[str] = []
    cur_len = 0

    for idx, text in items:
        add_len = (len(SEP) if cur_len else 0) + len(text)
        if cur_len + add_len > max_len and cur_idx:
            batches.append((cur_idx, cur_txt))
            cur_idx, cur_txt, cur_len = [idx], [text], len(text)
        else:
            cur_idx.append(idx)
            cur_txt.append(text)
            cur_len += add_len

    if cur_idx:
        batches.append((cur_idx, cur_txt))
    return batches


def _unpack(translated: str, orig_texts: list[str]) -> list[str]:
    parts = re.split(r"\n\s*\n", translated)
    return [(parts[i].strip() if i < len(parts) else "") or orig_texts[i] for i in range(len(orig_texts))]


def translate_texts(texts: list[str], from_lang: str, to_lang: str) -> list[str]:
    """Translate a list of texts: DeepL → Apertium → MyMemory fallback."""
    if not texts:
        return []

    to_translate = [(i, t) for i, t in enumerate(texts) if should_translate(t)]
    results = list(texts)

    if not to_translate:
        return results

    deepl_key = os.getenv("DEEPL_API_KEY", "").strip()
    mymemory_email = os.getenv("MYMEMORY_EMAIL", "").strip()

    # ── 1. DeepL ────────────────────────────────────────────────────────────
    if deepl_key and DEEPL_AVAILABLE:
        try:
            translator = deepl_sdk.Translator(deepl_key)
            target_code = "en-US" if to_lang == "en" else "fr"
            batch_texts = [t for _, t in to_translate]
            res = translator.translate_text(batch_texts, source_lang=from_lang.upper(), target_lang=target_code)
            translated_list = [r.text for r in res] if isinstance(res, list) else [res.text]
            for k, (idx, _) in enumerate(to_translate):
                results[idx] = translated_list[k] if k < len(translated_list) else texts[idx]
            return results
        except Exception:
            pass  # fall through

    # ── 2. Apertium ─────────────────────────────────────────────────────────
    apertium_pair = "eng|fra" if from_lang == "en" else "fra|eng"
    apertium_batches = _build_batches(to_translate, 4800)
    apertium_failed: list[tuple[int, str]] = []

    with httpx.Client(timeout=20.0) as client:
        for bi, (indices, batch_texts) in enumerate(apertium_batches):
            batch = SEP.join(batch_texts)
            try:
                res = client.get(
                    "https://www.apertium.org/apy/translate",
                    params={"q": batch, "langpair": apertium_pair},
                )
                if res.status_code == 200:
                    data = res.json()
                    if str(data.get("responseStatus")) == "200":
                        translated_text = str(data.get("responseData", {}).get("translatedText", ""))
                        parts = _unpack(translated_text, batch_texts)
                        for k, idx in enumerate(indices):
                            results[idx] = parts[k]
                        if bi < len(apertium_batches) - 1:
                            time.sleep(0.3)
                        continue
            except Exception:
                pass

            for k, idx in enumerate(indices):
                apertium_failed.append((idx, batch_texts[k]))
            if bi < len(apertium_batches) - 1:
                time.sleep(0.3)

    if not apertium_failed:
        return results

    # ── 3. MyMemory ──────────────────────────────────────────────────────────
    mm_limit = (4500 if mymemory_email else 450) - 20
    mm_batches = _build_batches(apertium_failed, mm_limit)

    with httpx.Client(timeout=25.0) as client:
        for bi, (indices, batch_texts) in enumerate(mm_batches):
            batch = SEP.join(batch_texts)
            delay = 3.0
            for attempt in range(4):
                try:
                    params: dict = {"q": batch, "langpair": f"{from_lang}|{to_lang}"}
                    if mymemory_email:
                        params["de"] = mymemory_email
                    res = client.get("https://api.mymemory.translated.net/get", params=params)
                    if res.status_code in (429, 500, 502, 503):
                        if attempt < 3:
                            time.sleep(delay)
                            delay *= 2
                            continue
                        break
                    if res.status_code == 200:
                        data = res.json()
                        if str(data.get("responseStatus")) == "200":
                            translated_text = data["responseData"]["translatedText"]
                            parts = _unpack(translated_text, batch_texts)
                            for k, idx in enumerate(indices):
                                results[idx] = parts[k]
                        break
                except Exception:
                    if attempt < 3:
                        time.sleep(delay)
                        delay *= 2

            if bi < len(mm_batches) - 1:
                time.sleep(0.7)

    return results
