# -*- coding: utf-8 -*-
"""v0.0.2 发布：更新全部文件到 main + 打 tag + 创建 release。
注意：沙箱 git 出网受限 → 用 api.github.com Contents API。"""
import base64
import json
import os
import sys
import urllib.request

OWNER = "ht182400-creator"
REPO = "deepthink-single"
BRANCH = "main"
TAG = "v0.0.2"
ROOT = r"E:\AI_Studio\deepthinkSingle"
EXCLUDE_DIRS = {"data", "node_modules", "__pycache__", ".git", "venv", ".venv", "logs"}
EXCLUDE_SUFFIXES = (".pyc", ".log", ".tmp", ".db")


def get_token():
    """字符串查找 token（环境会吞正则反斜杠，不用 re）。"""
    with open(os.path.expanduser("~/.config/gh/hosts.yml"), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("oauth_token:"):
                return line.split(":", 1)[1].strip()
    raise RuntimeError("token 未找到")


def api(method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "wb-release")
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
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
            out.append(rel)
    return sorted(out)


def upload_all():
    """Contents API 逐文件更新（已存在文件带 sha 覆盖），各自成 commit。"""
    files = collect_files()
    print(f"上传 {len(files)} 个文件…")
    ok = fail = 0
    for rel in files:
        with open(os.path.join(ROOT, rel), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        body = {"message": f"v0.0.2: {rel}", "content": b64, "branch": BRANCH}
        gs, gj = api("GET", f"/repos/{OWNER}/{REPO}/contents/{rel}")
        if gs == 200 and gj.get("sha"):
            body["sha"] = gj["sha"]
        status, resp = api("PUT", f"/repos/{OWNER}/{REPO}/contents/{rel}", body)
        if status == 409:
            import time
            time.sleep(2)
            status, resp = api("PUT", f"/repos/{OWNER}/{REPO}/contents/{rel}", body)
        if status in (200, 201):
            ok += 1
        else:
            fail += 1
            print(f"  FAIL {rel}: {status} {resp.get('message')}")
    print(f"上传完成: {ok} ok, {fail} fail")
    return fail == 0


def get_head_sha():
    status, body = api("GET", f"/repos/{OWNER}/{REPO}/branches/{BRANCH}")
    if status != 200:
        raise RuntimeError(f"获取分支失败 {status}")
    return body["commit"]["sha"]


def create_tag(sha):
    """轻量 tag（refs/tags/v0.0.2）。"""
    status, resp = api("POST", f"/repos/{OWNER}/{REPO}/git/refs",
                       {"ref": f"refs/tags/{TAG}", "sha": sha})
    if status == 201:
        print(f"tag {TAG} 创建成功 → {sha[:8]}")
        return True
    # 已存在 → 更新
    if status == 422 and resp.get("message", "").startswith("Reference already exists"):
        s2, r2 = api("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/tags/{TAG}",
                     {"sha": sha, "force": True})
        print(f"tag 已存在，更新 → {s2}")
        return True
    print(f"tag 创建失败: {status} {resp}")
    return False


def create_release(sha):
    status, resp = api("POST", f"/repos/{OWNER}/{REPO}/releases",
                       {"tag_name": TAG, "name": f"V{TAG[1:]}", "target_commitish": sha,
                        "body": "自选批量表格 / 资金流明细 / 5日主力对比 / 异动告警 / CSV导出 / 右键副图配置 / 全A股拼音搜索",
                        "draft": False, "prerelease": False})
    if status in (201, 200):
        print(f"release V{TAG[1:]} 创建成功: {resp.get('html_url')}")
        return True
    print(f"release 创建失败: {status} {resp.get('message')}")
    return False


if __name__ == "__main__":
    globals()["TAG"] = sys.argv[1] if len(sys.argv) > 1 else "v0.0.2"
    TOKEN = get_token()
    print(f"发布 {TAG} · token 前缀: {TOKEN[:8]}")
    if not upload_all():
        print("有文件上传失败，中止打 tag")
        sys.exit(1)
    sha = get_head_sha()
    print(f"main HEAD: {sha}")
    create_tag(sha)
    create_release(sha)
    print(f"\n完成。查看: https://github.com/{OWNER}/{REPO}/releases/tag/{TAG}")