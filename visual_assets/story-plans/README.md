# Production input contract

No production scene plan or approval is supplied by this PR. `catalog.json`
remains empty. The original RGB Tonton reference is not a complete RGBA sprite.

For #47 provide exactly ten composition scenes in `47.json` (the compositor
schema in `visual_assets/README.md`). Each scene contains one `tonton` layer.
Its approved asset has hash-bound `cargo_state`: `loaded` for scenes 1–8,
`unloading` for 9, `empty` for 10. The Tonton profile's reference hash must match
`tonton_referans.png`; do not substitute the fox or any rejected trial truck.
Sand already contained in the approved truck asset is not a second truck or
mandatory separate layer. Separate props need their own approved assets.

`red_bridge` is absent in scenes 1–7 and present once in 8–10. Use approved toy
construction-site backgrounds, never the forest trial. Keep the three-path
junction in scene 3 and correct sand unloading action in scene 9. Structural
metadata cannot establish these pixel semantics: an actual human must review
all ten composed frames.

After visual review put the compositor's documented `manual_scene_review`
object in `47.review.json`, including reviewer, date, identity/count/text/action
checks and the exact ten rendered JPEG hashes. Missing or altered approval
blocks TTS/rendering. The engine neither invents the approval nor generates a
replacement character when an input is missing.
