"""Move cover images to immediately after each post h1 in Feishu doc."""
import json
import subprocess
import shutil

DOC = "VrSsdDs7uodjDZxK8zlcqUYBnec"
LARK = shutil.which("lark-cli.cmd")

# h1 block_id -> cover img block_id (09 -> 01 order for safe moves)
MOVES = [
    ("doxcnI8aK5ULGq2LWu2qdjk1tjc", "doxcnSAmL0PimchquR9BPfPplZg"),  # 09
    ("doxcniYjIr9LJelHrkLJhjevE8e", "doxcn0N81jVByb9AkqiM2d9IXTf"),  # 08
    ("doxcnBZQIhWIuVNjbJqCEdwgIhd", "doxcn6rPoK3z4kHJtewQIHcWLug"),  # 07
    ("doxcn48n3Qi67rJI3ERrsjLG9id", "doxcnwnjOpqG4jWeZ8ZImWx028e"),  # 06
    ("doxcnkefZC2qhqAiC4pFystkyee", "doxcnReBrRlHm01sPZfcJwgCA3k"),  # 05
    ("doxcn6DGt9j34GdDVzF7wCI8Nhd", "doxcnR0gp7h30wm9dNSx3QhX6Jb"),  # 04
    ("doxcn0qk4MieFfdniuPKVE98kwd", "doxcnl18fWE6adtLRJsRGC9xS7L"),  # 03
    ("doxcn67neIXiEoUNWWnKSVXOUYe", "doxcniip3pHqHbNy8GWReQAmHdg"),  # 02
    # 01 already moved in test; skip duplicate delete separately
]

DELETE_DUP = "doxcnDuw4R8LiNBNZtsxugAVJaf"  # duplicate post-01 cover at end


def run(args):
    r = subprocess.run(
        [LARK, "docs", "+update", "--api-version", "v2", "--as", "user", "--doc", DOC, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    print(r.stdout or r.stderr)
    return r.returncode == 0


def main():
    for h1, img in MOVES:
        ok = run(
            [
                "--command",
                "block_move_after",
                "--block-id",
                h1,
                "--src-block-ids",
                img,
            ]
        )
        if not ok:
            print(f"FAILED move {img} after {h1}")
            return 1
    # delete duplicate cover at end
    run(["--command", "block_delete", "--block-id", DELETE_DUP])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
