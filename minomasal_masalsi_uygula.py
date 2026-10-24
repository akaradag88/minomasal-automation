
"""Masalsı anlatımı orijinal hikâyeyi değiştirmeden uygula."""

from copy import deepcopy
from minomasal_masalsi_kontrol import select_narrations


def apply_masalsi(story, converted, approved=False):
    result = deepcopy(story)

    original = [
        scene["narration"]
        for scene in result["scenes"]
    ]

    selected = select_narrations(
        original,
        converted,
        approved=approved
    )

    for scene, narration in zip(result["scenes"], selected):
        scene["narration"] = narration

    return result
