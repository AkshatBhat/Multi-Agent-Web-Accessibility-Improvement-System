#!/usr/bin/env python3
import argparse
import os
import sys
import json
import pickle

EXAMPLE_WEBUI7K_ROOT = "/Users/akshat/Data/UIUC/Spring 2025/Courses/CS 568 User-Centered Machine Learning/Project/WebUI-7k"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 3+4: merge Axe results and keep pages/viewports with violations."
    )
    parser.add_argument(
        "--base-dir",
        default=os.getenv("WEBUI7K_ROOT"),
        help="WebUI7k root path (contains train_split_web7k, intermediate, etc.).",
    )
    parser.add_argument(
        "--train-dir",
        default=os.getenv("WEBUI7K_TRAIN_DIR"),
        help="Override train split dir. Defaults to <base-dir>/train_split_web7k.",
    )
    parser.add_argument(
        "--pkl-path",
        default=os.getenv("WEBUI7K_PKL_PATH"),
        help="Override phase1 pickle path. Defaults to <base-dir>/intermediate/per_page.pkl.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("WEBUI7K_OUTPUT_DIR"),
        help="Override output dir. Defaults to <base-dir>/json_dataset_for_agents.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.base_dir:
        train_dir = args.train_dir or os.path.join(args.base_dir, "train_split_web7k")
        pkl_path = args.pkl_path or os.path.join(args.base_dir, "intermediate", "per_page.pkl")
        output_dir = args.output_dir or os.path.join(args.base_dir, "json_dataset_for_agents")
    else:
        if not (args.train_dir and args.pkl_path and args.output_dir):
            print(
                "❌ Missing paths. Provide --base-dir, or provide all of --train-dir --pkl-path --output-dir.",
                file=sys.stderr,
            )
            print(f"   Example base dir: {EXAMPLE_WEBUI7K_ROOT}", file=sys.stderr)
            sys.exit(1)
        train_dir = args.train_dir
        pkl_path = args.pkl_path
        output_dir = args.output_dir

    if not os.path.isdir(train_dir):
        print(f"❌ train_dir does not exist: {train_dir}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # ─── LOAD PHASE 1 METADATA ──────────────────────────────────────────────────
    try:
        with open(pkl_path, "rb") as f:
            per_page = pickle.load(f)
    except Exception as e:
        print(f"❌ Fatal: could not load phase 1 pickle at {pkl_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # ─── PHASE 3+4: FILTER & MERGE ─────────────────────────────────────────────
    for page_id, page_data in per_page.items():
        vps = page_data.get("viewports", [])
        out_viewports = []

        for vp_entry in vps:
            vp = vp_entry.get("viewport")
            if vp in ("iPad-Pro", "iPhone-13 Pro"):
                prefix = vp
            else:
                prefix = f"default_{vp}"

            axe_path = os.path.join(train_dir, page_id, f"{prefix}-axe.json")
            if not os.path.isfile(axe_path):
                print(f"⚠️  Missing axe file, skipping: {axe_path}", file=sys.stderr)
                continue

            try:
                with open(axe_path, "r", encoding="utf-8") as axf:
                    axe_data = json.load(axf)
            except Exception as e:
                print(f"⚠️  Could not parse JSON {axe_path}: {e}", file=sys.stderr)
                continue

            violations = axe_data.get("violations")
            if isinstance(violations, list) and len(violations) > 0:
                new_vp = vp_entry.copy()
                new_vp["axe"] = axe_data
                out_viewports.append(new_vp)

        if out_viewports:
            out_payload = {
                "page_id": page_id,
                "viewports": out_viewports
            }
            out_file = os.path.join(output_dir, f"{page_id}.json")
            try:
                with open(out_file, "w", encoding="utf-8") as outf:
                    json.dump(out_payload, outf, indent=2)
                print(f"✅ Wrote {len(out_viewports)} violations → {out_file}")
            except Exception as e:
                print(f"❌ Failed to write {out_file}: {e}", file=sys.stderr)

    print("🏁 Phase 3+4 complete. Check", output_dir)


if __name__ == "__main__":
    main()
