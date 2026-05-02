"""Upload chain-determinism-bench-v1 to HuggingFace Hub.

Reads token from `.env_hf.txt` (key may be `HF_TOKEN` or `HF-TOKEN`,
optional whitespace and quotes around value, matching .env_pypi.txt
parser). Token is never printed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = ROOT / "chain_determinism_bench"
DATA_DIR = BENCH_DIR / "data"
REPO_ID = "cruxia/chain-determinism-bench-v1"


def load_hf_token() -> str:
    """Parse `.env_hf.txt`. Format: `HF_TOKEN = <token>` or `HF-TOKEN = <token>`,
    optionally quoted. Whitespace tolerant."""
    env_path = ROOT / ".env_hf.txt"
    if not env_path.exists():
        raise SystemExit(f"FATAL: {env_path} not found")
    text = env_path.read_text()
    # Match HF_TOKEN, HF-TOKEN, or HFTOKEN (any case) followed by '='
    m = re.search(
        r"^\s*HF[_\-]?TOKEN\s*=\s*['\"]?([^'\"\n\r]+?)['\"]?\s*$",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    if not m:
        raise SystemExit("FATAL: could not parse HF_TOKEN from .env_hf.txt")
    return m.group(1).strip()


def main():
    token = load_hf_token()
    # NEVER print the token. Set env var so child loaders can pick it up safely.
    os.environ["HF_TOKEN"] = token

    from huggingface_hub import HfApi, create_repo, upload_file

    api = HfApi(token=token)

    # 1. Create the repo (idempotent: exist_ok=True).
    print(f"Creating repo {REPO_ID} (type=dataset, public)...", flush=True)
    create_repo(
        repo_id=REPO_ID,
        repo_type="dataset",
        private=False,
        exist_ok=True,
        token=token,
    )

    # 2. Upload files.
    files_to_upload = [
        ("README.md", BENCH_DIR / "README.md"),
        ("croissant.json", BENCH_DIR / "croissant.json"),
        ("data/phase_1a.jsonl", DATA_DIR / "phase_1a.jsonl"),
        ("data/phase_1b.jsonl", DATA_DIR / "phase_1b.jsonl"),
        ("data/phase_2_v2.jsonl", DATA_DIR / "phase_2_v2.jsonl"),
        ("data/phase_3_5_swebench.jsonl", DATA_DIR / "phase_3_5_swebench.jsonl"),
    ]
    for repo_path, local_path in files_to_upload:
        if not local_path.exists():
            print(f"  WARN: missing {local_path}, skipping", flush=True)
            continue
        size_mb = local_path.stat().st_size / 1024 / 1024
        print(f"  uploading {repo_path}  ({size_mb:.1f} MB) ...", flush=True)
        upload_file(
            path_or_fileobj=str(local_path),
            path_in_repo=repo_path,
            repo_id=REPO_ID,
            repo_type="dataset",
            token=token,
            commit_message=f"upload {repo_path}",
        )

    # 3. Verify the repo exists and is accessible.
    print("\nVerifying via dataset_info...", flush=True)
    info = api.dataset_info(REPO_ID, token=token)
    print(f"  repo: {info.id}")
    print(f"  sha:  {info.sha}")
    print(f"  files: {len(info.siblings)} siblings")
    for s in info.siblings:
        print(f"    - {s.rfilename}")

    print(f"\nDataset live at: https://huggingface.co/datasets/{REPO_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
