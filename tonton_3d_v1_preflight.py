import json
from pathlib import Path

from minomasal_cloudflare_quality_test import run_check

PLAN_PATH = Path("visual_assets/tonton_3d_v1/visual-plan.json")

def main():
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8-sig"))

    if len(plan["scenes"]) != 1:
        raise SystemExit("Exactly one scene required")

    # Reuse existing free-plan, quota and inference safeguards.
    # The existing runner requires two scenes, so use the same
    # scene twice for a preflight-only check without inference.
    check_plan = {
        "profile": plan["profile"],
        "scenes": plan["scenes"] * 2,
    }

    report = run_check(
        "tonton_3d_v1_preflight",
        generate=False,
        plan=check_plan,
    )

    print(json.dumps({
        "status": report["status"],
        "free_plan_verified": report["free_plan_verified"],
        "quota_verified": report["quota_verified"],
        "paid_usage_allowed": report["paid_usage_allowed"],
    }, indent=2))

if __name__ == "__main__":
    main()
