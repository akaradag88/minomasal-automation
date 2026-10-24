
"""MinoMasal: Güvenli masalsı anlatım önerisi üretimi."""

import json
import re

import requests


def create_masalsi_candidate(story, api_key, model="openai"):
    """Orijinal hikâyeyi değiştirmeden masalsı öneri üretir."""

    scenes = story.get("scenes", [])

    if len(scenes) != 10:
        raise ValueError("Tam 10 sahne gerekli.")

    original = [s["narration"] for s in scenes]

    prompt = (
        "Sen deneyimli bir Türkçe çocuk masalı editörüsün. "
        "Aşağıdaki 10 sahnenin anlatımını doğal "
        "-miş'li geçmiş zamana dönüştür. "

        "Hikâyeyi yeniden yazma. "
        "Yalnızca anlatım kipini değiştir. "

        "Tamamlanmış olaylarda -miş kullan: "
        "'sevindi' -> 'sevinmiş', "
        "'gülümsedi' -> 'gülümsemiş', "
        "'gördü' -> 'görmüş', "
        "'yardım etti' -> 'yardım etmiş'. "

        "Geçmişte devam eden olaylarda gerektiğinde "
        "-yormuş kullan: 'arıyordu' -> 'arıyormuş'. "

        "Etken cümleleri edilgen hâle getirme. "
        "'Gördü' fiilini 'görülmüş' yapma. "
        "Özneyi, karakterleri, duyguları ve olay sırasını koru. "

        "Yeni olay, karakter veya duygu ekleme. "
        "Karakterlerin doğrudan konuşmalarını değiştirme. "
        "Çocuklara yöneltilen soruları aynen koru. "
        "Doğal, sıcak ve anlaşılır Türkçe kullan. "

        "Tam 10 sahne üret. "
        "Toplam anlatım 100-130 kelime arasında olsun. "

        'Yalnız geçerli JSON döndür: '
        '{"scenes":["sahne1","sahne2",'
        '"...","sahne10"]}\n'
        + json.dumps(original, ensure_ascii=False)
    )

    response = requests.post(
        "https://gen.pollinations.ai/v1/chat/completions",
        headers={"Authorization": "Bearer " + api_key},
        json={
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
        },
        timeout=150,
    )

    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]

    content = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        content.strip(),
    )

    converted = json.loads(content)["scenes"]

    if (
        not isinstance(converted, list)
        or len(converted) != 10
        or not all(isinstance(x, str) and x.strip() for x in converted)
    ):
        raise ValueError("Masalsı sahne yapısı geçersiz.")

    # Son düşünme sorusunu orijinal hâliyle koru.
    question_pattern = r"[^.!?]*\?\s*$"

    old_question = re.search(question_pattern, original[-1])
    new_question = re.search(question_pattern, converted[-1])

    if not old_question or not new_question:
        raise ValueError("Son düşünme sorusu bulunamadı.")

    converted[-1] = (
        converted[-1][:new_question.start()]
        + old_question.group(0)
    )

    word_count = sum(len(x.split()) for x in converted)

    if not 100 <= word_count <= 130:
        raise ValueError(
            f"Masalsı anlatım uzunluğu uygun değil: {word_count}"
        )

    # Yalnızca öneri döndür; hikâyeye otomatik uygulama.
    return converted
