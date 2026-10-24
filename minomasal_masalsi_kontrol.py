
"""Masalsı anlatım için güvenli seçim kontrolü."""


def select_narrations(original, converted, approved=False):
    # Onay yoksa orijinal hikâyeyi koru.
    if not approved:
        return original

    if not isinstance(converted, list):
        return original

    if len(converted) != len(original) or len(original) != 10:
        return original

    if not all(
        isinstance(text, str) and text.strip()
        for text in converted
    ):
        return original

    words = sum(len(text.split()) for text in converted)

    if not 100 <= words <= 130:
        return original

    # Son düşünme sorusu değiştirilmemeli.
    import re

    def last_question(text):
        match = re.search(r"[^.!?]*\?\s*$", text)
        return match.group(0).strip() if match else None

    if last_question(original[-1]) != last_question(converted[-1]):
        return original

    return converted
