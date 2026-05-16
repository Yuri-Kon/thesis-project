#!/usr/bin/env python3
"""
Foldseek Webserver API 完整调用示例

API 文档: https://github.com/soedinglab/MMseqs2-App/blob/master/docs/api.html
在线服务: https://search.foldseek.com
"""

import json
import time
import sys
import requests  # pip install requests

# ─────────────────────── 配置 ───────────────────────
API_BASE = "https://search.foldseek.com/api"
POLL_INTERVAL = 2   # 轮询间隔（秒）
MAX_POLLS = 60      # 最大轮询次数（2分钟超时）

# 示例: 用 foldseek example 中的 d1asha_ 结构作为查询
# 或者你也可以传 PDB 文件路径: QUERY_PDB_PATH = "/path/to/structure.pdb"
QUERY_PDB_PATH = None  # None 表示用内置示例 PDB

# 数据库选择 (可用列表见下方)
DATABASES = [
    "afdb-swissprot",   # AlphaFold/Swiss-Prot (小, 适合快速测试)
    # "afdb50",         # AlphaFold/UniProt50 (大, 54M结构)
    # "pdb100",         # PDB 实验结构
    # "cath50",         # CATH 结构域分类
]

# ─────────────────────── 内置示例 PDB ───────────────────────
SAMPLE_PDB = """\
ATOM    866  N   PHE A 111      11.187 -12.768  -6.000  1.00  0.00           N
ATOM    867  CA  PHE A 111      11.895 -11.516  -5.804  1.00  0.00           C
ATOM    868  C   PHE A 111      13.203 -11.457  -6.592  1.00  0.00           C
ATOM    870  CB  PHE A 111      12.169 -11.360  -4.310  1.00  0.00           C
ATOM    877  N   GLY A 112      13.543 -10.277  -7.094  1.00  0.00           N
ATOM    878  CA  GLY A 112      14.800 -10.107  -7.788  1.00  0.00           C
ATOM    879  C   GLY A 112      14.816  -9.982  -9.286  1.00  0.00           C
ATOM    881  N   TYR A 113      13.670 -10.112  -9.938  1.00  0.00           N
ATOM    882  CA  TYR A 113      13.648 -10.024 -11.397  1.00  0.00           C
ATOM    883  C   TYR A 113      12.764  -8.904 -11.929  1.00  0.00           C
ATOM    885  CB  TYR A 113      13.182 -11.355 -11.997  1.00  0.00           C
ATOM    893  N   CYS A 114      13.052  -8.468 -13.148  1.00  0.00           N
ATOM    894  CA  CYS A 114      12.288  -7.406 -13.778  1.00  0.00           C
ATOM    895  C   CYS A 114      10.881  -7.902 -14.054  1.00  0.00           C
ATOM    897  CB  CYS A 114      12.938  -6.973 -15.096  1.00  0.00           C
ATOM    899  N   GLU A 115       9.884  -7.083 -13.740  1.00  0.00           N
ATOM    900  CA  GLU A 115       8.508  -7.493 -13.963  1.00  0.00           C
ATOM    901  C   GLU A 115       8.078  -7.419 -15.428  1.00  0.00           C
ATOM    903  CB  GLU A 115       7.564  -6.649 -13.087  1.00  0.00           C
ATOM    908  N   SER A 116       8.751  -6.604 -16.236  1.00  0.00           N
ATOM    909  CA  SER A 116       8.399  -6.475 -17.651  1.00  0.00           C
ATOM    910  C   SER A 116       9.022  -7.604 -18.460  1.00  0.00           C
END
"""


def list_databases():
    """列出 foldseek 服务器上所有可用数据库。"""
    resp = requests.get(f"{API_BASE}/databases")
    resp.raise_for_status()
    return resp.json()


def submit_search(pdb_content: str, databases: list[str]) -> dict:
    """提交结构搜索任务, 返回 ticket。"""
    # foldseek API 要求:
    #   - 用 multipart/form-data 上传 PDB/mmCIF 文件
    #   - mode='3diaa' (3Di+AA alignment mode)
    resp = requests.post(
        f"{API_BASE}/ticket",
        files={"q": ("query.pdb", pdb_content, "text/plain")},
        data={
            "mode": "3diaa",
            "database[]": databases,
        },
    )
    resp.raise_for_status()
    return resp.json()


def poll_ticket(ticket_id: str) -> dict:
    """轮询 ticket 状态, 直到 COMPLETE / ERROR 或超时。"""
    for i in range(1, MAX_POLLS + 1):
        resp = requests.get(f"{API_BASE}/ticket/{ticket_id}")
        resp.raise_for_status()
        status = resp.json()
        state = status["status"]
        print(f"  [{i:2d}] status={state}")
        if state in ("COMPLETE", "ERROR"):
            return status
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Job {ticket_id} did not complete within {MAX_POLLS * POLL_INTERVAL}s")


def get_result(ticket_id: str, entry: int = 0) -> dict:
    """获取第 entry 个 query 的搜索结果。"""
    resp = requests.get(f"{API_BASE}/result/{ticket_id}/{entry}")
    resp.raise_for_status()
    return resp.json()


def download_result(ticket_id: str, output_path: str = "/tmp/foldseek_result.tar.gz"):
    """下载 BLAST-tab 格式的完整结果归档。"""
    resp = requests.get(f"{API_BASE}/result/download/{ticket_id}", stream=True)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"  Downloaded to {output_path} ({resp.headers.get('Content-Length', '?')} bytes)")


# ─────────────────────── main ───────────────────────
def main():
    # 1. 列出可用数据库
    print("=" * 60)
    print("Step 1: 列出可用数据库")
    print("=" * 60)
    db_info = list_databases()
    for db in db_info["databases"]:
        print(f"  {db['name']:30s}  path={db['path']:25s}  default={db.get('default','?')}")
    print()

    # 2. 准备查询结构
    if QUERY_PDB_PATH:
        with open(QUERY_PDB_PATH) as f:
            pdb_content = f.read()
        print(f"Using PDB file: {QUERY_PDB_PATH}")
    else:
        pdb_content = SAMPLE_PDB
        print("Using built-in sample PDB (d1asha fragment)")

    # 3. 提交搜索
    print()
    print("=" * 60)
    print("Step 2: 提交搜索任务")
    print("=" * 60)
    print(f"  Databases: {DATABASES}")
    ticket = submit_search(pdb_content, DATABASES)
    ticket_id = ticket["id"]
    print(f"  Ticket ID: {ticket_id}")
    print(f"  Initial status: {ticket['status']}")

    # 4. 轮询
    print()
    print("=" * 60)
    print("Step 3: 轮询等待完成")
    print("=" * 60)
    final_status = poll_ticket(ticket_id)

    if final_status["status"] == "ERROR":
        print(f"ERROR: {json.dumps(final_status, indent=2)}")
        sys.exit(1)

    # 5. 获取结果
    print()
    print("=" * 60)
    print("Step 4: 获取搜索结果")
    print("=" * 60)
    result = get_result(ticket_id, entry=0)

    # 显示 query 信息
    query_info = result.get("query", {})
    print(f"  Query: {query_info.get('header', '?')}")
    print(f"  Sequence length: {len(query_info.get('sequence', ''))}")

    # 显示 top hits
    for db_result in result.get("results", []):
        db_name = db_result.get("db", "?")
        alignments = db_result.get("alignments", [])
        print(f"\n  Database: {db_name}")
        print(f"  Total hits: {len(alignments)}")
        print(f"\n  {'#':<3} {'Target':<20} {'SeqId':>6} {'E-value':>12} {'Score':>8} {'AlnLen':>7}")
        print(f"  {'-'*3} {'-'*20} {'-'*6} {'-'*12} {'-'*8} {'-'*7}")
        for i, aln in enumerate(alignments[:10], 1):
            print(
                f"  {i:<3} "
                f"{str(aln.get('target', '?'))[:20]:<20} "
                f"{aln.get('seqId', 0):>6.3f} "
                f"{str(aln.get('eval', '?')):>12} "
                f"{aln.get('score', 0):>8} "
                f"{aln.get('alnLength', 0):>7}"
            )

    # 6. 下载完整结果 (可选)
    print()
    print("=" * 60)
    print("Step 5: 下载完整结果归档")
    print("=" * 60)
    download_result(ticket_id)
    print()
    print("Done!")


if __name__ == "__main__":
    main()
