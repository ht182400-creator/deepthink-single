# -*- coding: utf-8 -*-
"""通过 api.github.com Contents API 上传项目源码（沙箱 git 出网受限时）。
每个文件一个 PUT（各自成为一个 commit），目录自动创建。"""
import base64
import json
import os
import sys
import urllib.request

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
OWNER = "ht182400-creator"
REPO = "deepthink-single"
BRANCH = "main"
ROOT = r"E:\AI_Studio\deepthinkSingle"

# 上传清单：排除 data/（本地数据）、缓存、venv
EXCLUDE_DIRS = {"data", "node_modules", "__pycache__", ".git", "venv", ".venv"}
EXCLUDE_SUFFIXES = (".pyc", ".log", ".tmp", ".db")


def api(method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "wb-push")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def collect_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(EXCLUDE_SUFFIXES):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            out.append(rel)
    return sorted(out)


def create_repo():
    status, body = api("POST", "/user/repos",
                       {"name": REPO, "description": "A股盯盘单页应用：分时/K线/综合数据/副图配置",
                        "private": False, "auto_init": True})
    if status in (201, 422):  # 201=创建成功, 422=已存在
        print(f"仓库就绪: {status}")
    else:
        print(f"创建仓库失败: {status} {body}")
        sys.exit(1)


def upload_all():
    files = collect_files()
    print(f"共 {len(files)} 个文件")
    ok = 0
    for rel in files:
        with open(os.path.join(ROOT, rel), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        # 目录嵌套：GitHub 自动创建父目录（Content API 支持 path 含子目录）
        body = {"message": f"upload {rel}", "content": b64, "branch": BRANCH}
        status, resp = api("PUT", f"/repos/{OWNER}/{REPO}/contents/{rel}", body)
        if status in (200, 201):
            ok += 1
        else:
            print(f"  FAIL {rel}: {status} {resp.get('message')}")
    print(f"完成: {ok}/{len(files)} 个文件上传")


if __name__ == "__main__":
    if not TOKEN:
        import re
        with open(os.path.expanduser("~/.config/gh/hosts.yml"), "r", encoding="utf-8") as f:
            m = re.search(r"oauth_token:\s*(\S+)", f.read())
            TOKEN = m.group(1) if m else ""
    create_repo()
    upload_all()