import os
import re
import time

try:
    import deepl as deepl_sdk
    DEEPL_AVAILABLE = True
except ImportError:
    DEEPL_AVAILABLE = False

try:
    from deep_translator import GoogleTranslator
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


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


def _google_translate_batch(texts: list, from_lang: str, to_lang: str) -> list:
    """Translate a list of texts using Google Translate, in chunks of 50."""
    if not GOOGLE_AVAILABLE:
        return texts

    target = "fr" if to_lang == "fr" else "en"
    source = from_lang  # e.g. "en" or "fr"

    results = list(texts)
    chunk_size = 50

    for start in range(0, len(texts), chunk_size):
        chunk = texts[start:start + chunk_size]
        try:
            translator = GoogleTranslator(source=source, target=target)
            translated = translator.translate_batch(chunk)
            for j, t in enumerate(translated):
                if t:
                    results[start + j] = t
        except Exception:
            # Translate one by one as fallback if batch fails
            for j, text in enumerate(chunk):
                try:
                    t = GoogleTranslator(source=source, target=target).translate(text)
                    if t:
                        results[start + j] = t
                    time.sleep(0.1)
                except Exception:
                    pass
        if start + chunk_size < len(texts):
            time.sleep(0.3)

    return results


def translate_texts(texts: list, from_lang: str, to_lang: str) -> list:
    """Translate a list of texts: DeepL → Google Translate fallback."""
    if not texts:
        return []

    to_translate = [(i, t) for i, t in enumerate(texts) if should_translate(t)]
    results = list(texts)

    if not to_translate:
        return results

    deepl_key = os.getenv("DEEPL_API_KEY", "").strip()

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
            pass

    # ── 2. Google Translate ──────────────────────────────────────────────────
    if GOOGLE_AVAILABLE:
        try:
            batch_texts = [t for _, t in to_translate]
            translated_batch = _google_translate_batch(batch_texts, from_lang, to_lang)
            for k, (idx, _) in enumerate(to_translate):
                results[idx] = translated_batch[k] if k < len(translated_batch) else texts[idx]
            return results
        except Exception:
            pass

    return results
