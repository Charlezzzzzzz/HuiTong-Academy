#!/usr/bin/env python3
"""Create a sanitized Huitong source delivery archive.

The package deliberately excludes local identity, authentication, model-key,
database and generated research-output files. It is intended for handoff and
reproduction, not for migrating a live local session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent

EXACT_EXCLUDES = {
    ".env",
    "data/config.json",
    "data/model_config.json",
    "data/users.json",
    "data/auth_sessions.json",
    "data/participant_tokens.json",
    "research/outputs.jsonl",
    "research/manual_scores.jsonl",
    "research/runs/aggregate.csv",
    "research/runs/case_deltas.csv",
    "research/runs/run_records.jsonl",
    "research/runs/scores.jsonl",
    "research/runs/summary.json",
    "research/runs/validation.json",
}


def is_excluded(relative: Path) -> bool:
    rel = relative.as_posix()
    if rel in EXACT_EXCLUDES:
        return True
    if relative.name == ".DS_Store":
        return True
    if "__pycache__" in relative.parts:
        return True
    if relative.suffix in {".pyc", ".pyo"}:
        return True
    if relative.parts and relative.parts[0] == "data":
        if relative.name.startswith("huitong.sqlite3"):
            return True
    if rel.startswith("research/processed/") or rel.startswith("research/raw_exports/"):
        return True
    return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_package(output: Path) -> tuple[int, str]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="huitong-delivery-") as temp_name:
        stage = Path(temp_name) / "huitong-web"
        stage.mkdir(parents=True)

        copied: list[Path] = []
        for source in sorted(ROOT.rglob("*")):
            if not source.is_file():
                continue
            relative = source.relative_to(ROOT)
            if is_excluded(relative):
                continue
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(relative)

        exclusions = """# 交付包排除项\n\n本压缩包用于安全交接和复现，不迁移本机运行态。以下内容被有意排除：\n\n- SQLite 数据库、登录账号、登录会话、participant token 和模型配置；\n- `.env`、API Key、Cookie、会话 token、密码摘要；\n- `__pycache__`、`*.pyc`、`.DS_Store`；\n- 研究运行输出、人工评分、原始导出和脱敏前的用户文本；\n- 可由脚本重新生成的聚合结果和验证结果。\n\n首次启动会在本机重新创建运行态文件。研究材料 `cases.jsonl`、`conditions.json` 和计划运行清单保留在包内；`annotation_only.jsonl` 只能用于人工编码，不能进入生成提示词。\n"""
        (stage / "PACKAGE_EXCLUSIONS.md").write_text(exclusions, encoding="utf-8")
        copied.append(Path("PACKAGE_EXCLUSIONS.md"))

        manifest = []
        for relative in sorted(copied):
            path = stage / relative
            manifest.append(
                {
                    "path": relative.as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
        (stage / "PACKAGE_MANIFEST.json").write_text(
            json.dumps(
                {
                    "package": output.stem,
                    "source_root": str(ROOT),
                    "file_count": len(manifest),
                    "files": manifest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        sums = "\n".join(f"{item['sha256']}  {item['path']}" for item in manifest) + "\n"
        (stage / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")

        if output.exists():
            output.unlink()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, Path("huitong-web") / path.relative_to(stage))

    return len(copied), sha256(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT.parent / "huitong-web-delivery-20261031.zip",
        help="output zip path (default: sibling of project directory)",
    )
    args = parser.parse_args()
    count, digest = build_package(args.output)
    print(f"created: {args.output.resolve()}")
    print(f"files: {count}")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
