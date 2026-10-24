
"""MinoMasal masalsı anlatım için güvenli hazırlık."""

from copy import deepcopy

from minomasal_masalsi_oneri import create_masalsi_candidate


def prepare_masalsi_safely(story, api_key, model="openai"):
    """
    Masalsı anlatım adayı hazırlar.

    Hata olursa orijinal hikâyeyi korur.
    Aday metni otomatik olarak uygulamaz.
    """

    original = deepcopy(story)

    try:
        candidate = create_masalsi_candidate(
            story,
            api_key,
            model=model,
        )

        print("MASALSI ADAY HAZIR - MANUEL ONAY BEKLENIYOR")

        return original, candidate

    except Exception as exc:
        
        # Yalnizca bilinen dogrulama hatalarini acikla.
        detail = str(exc)

        known_errors = (
            "Masalsı anlatım uzunluğu uygun değil",
            "Masalsı sahne yapısı geçersiz",
            "Son düşünme sorusu bulunamadı",
            "Tam 10 sahne gerekli",
        )

        if isinstance(exc, ValueError) and detail.startswith(known_errors):
            print("MASALSI HATA NEDENI:", detail)
        else:
            print("MASALSI HATA NEDENI: Ayrinti gizlendi.")

        print(
            "MASALSI DONUSUM BASARISIZ:",
            type(exc).__name__,
        )

        print("ORIJINAL HIKAYE KORUNDU")

        return original, None
