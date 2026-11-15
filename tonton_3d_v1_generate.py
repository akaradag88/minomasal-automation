"""Manual, single-image Cloudflare test. No publishing."""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from minomasal_images import (
    Cloudflare, ProviderFailure, http, json_response,
    load_config, verify_cloudflare_free_plan,
)
from minomasal_cloudflare_usage import query_quota
from minomasal_visual_profile import build_prompt, validate_profile

ROOT = "https://api.cloudflare.com/client/v4"
BRANCH = "refs/heads/feat/tonton-3d-v1-test"
PLAN_PATH = Path("visual_assets/tonton_3d_v1/visual-plan.json")
OUTPUT = Path("tonton_3d_v1_output")

def main():
    if not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
        and os.environ.get("GITHUB_REPOSITORY") == "akaradag88/minomasal-automation"
        and os.environ.get("GITHUB_REF") == BRANCH
    ):
        raise SystemExit("Manual GitHub Actions test only.")

    report = {
        "status": "blocked_no_publish",
        "paid_usage_allowed": False,
        "max_image_requests": 1,
        "generated_images": 0,
    }

    try:
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8-sig"))
        validate_profile(plan["profile"])
        if len(plan["scenes"]) != 1:
            raise ValueError("one_scene_required")
        prompt = build_prompt(plan["profile"], plan["scenes"][0])

        account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
        usage_token = os.environ.get("CLOUDFLARE_USAGE_TOKEN", "").strip()

        if not re.fullmatch(r"[a-fA-F0-9]{32}", account):
            raise ValueError("invalid_account")
        if not token or not usage_token or token == usage_token:
            raise ValueError("invalid_credentials")

        models = json_response(
            http("cloudflare", "GET",
                 f"{ROOT}/accounts/{account}/ai/models/search",
                 headers={"Authorization": "Bearer " + token},
                 params={"search": "@cf/black-forest-labs/flux-1-schnell"}),
            "cloudflare",
        )
        if models.get("success") is not True or not any(
            isinstance(m, dict) and m.get("name") == "@cf/black-forest-labs/flux-1-schnell"
            for m in models.get("result", [])
        ):
            raise ValueError("model_not_verified")

        subscriptions = json_response(
            http("cloudflare", "GET",
                 f"{ROOT}/accounts/{account}/subscriptions",
                 headers={"Authorization": "Bearer " + usage_token}),
            "cloudflare",
        )
        verify_cloudflare_free_plan(subscriptions)

        quota = query_quota(account, usage_token)
        if quota["remaining_neurons_reported"] < 1000:
            raise ValueError("insufficient_free_quota")

        fresh = query_quota(account, usage_token)
        if (
            fresh["utc_day"] != quota["utc_day"]
            or fresh["remaining_neurons_reported"] < 1000
        ):
            raise ValueError("quota_changed")

        config = load_config()
        config["http_attempts"] = 1
        provider = Cloudflare(config)
        provider.account = account
        provider.token = token
        provider.model = "@cf/black-forest-labs/flux-1-schnell"

        data = provider.generate(prompt, 1)

        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "tonton-3d-v1.png").write_bytes(data)
        report["generated_images"] = 1
        report["status"] = "image_generated_review_required"

    except (ProviderFailure, ValueError, OSError, KeyError):
        report["status"] = "blocked_no_publish"
    except Exception:
        report["status"] = "blocked_no_publish"

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["generated_images"] == 1 else 1

if __name__ == "__main__":
    sys.exit(main())
