
"""MinoMasal: Onaylı masalsı anlatım entegrasyonu."""

from copy import deepcopy
from minomasal_masalsi_uygula import apply_masalsi


def prepare_story_for_render(
    story,
    supplied_story=False,
    approved_candidate=None,
):
    """Güvenli şekilde video üretimine uygun hikâye seç."""

    original = deepcopy(story)

    # Önceden onaylanmış JSON hikâyelerine dokunma.
    if supplied_story:
        return original

    # Onaylı masalsı metin yoksa orijinali kullan.
    if approved_candidate is None:
        return original

    # Yalnızca açıkça verilmiş onaylı adayı uygula.
    return apply_masalsi(
        original,
        approved_candidate,
        approved=True,
    )
