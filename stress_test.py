#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phota3A 上游压测 (参考 notrack-stress 模式)
场景: 签名正确性批量验证 / 边界值(时间戳偏移/包名错) / 轮询探测 / 并发节流探测
用法: python stress_test.py [并发数] [总请求数]
"""
import concurrent.futures
import hashlib
import json
import random
import sys
import time
import uuid

import requests

UPSTREAM = "https://sci.videomate.cc"
SIGN_KEY = "gmdh1Z"
PACKAGE = "com.mivii.mvlite.editor"
PROXY = {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}
ENDPOINT = "/algo/v1/faceFusion/aigc/queryAiCustomizeTask"  # 轻量只读端点
session = requests.Session()
session.proxies = PROXY


def call(ts_offset=0, sign_key=SIGN_KEY, cp=PACKAGE, userid=None):
    ts = str(int(time.time()) + ts_offset)
    sign = hashlib.md5((sign_key + ts).encode()).hexdigest()
    r = session.post(UPSTREAM + ENDPOINT, headers={
        "Content-Type": "application/json", "userid": userid or ("u" + uuid.uuid4().hex[:10]),
        "timeStamp": ts, "cp": cp, "version": "42", "platform": "1", "sign": sign,
        "User-Agent": "okhttp/4.9.3",
    }, data=json.dumps({"jobId": "stress-" + uuid.uuid4().hex[:8]}), timeout=30)
    try:
        return r.status_code, r.json().get("c"), r.json().get("m", "")[:60]
    except Exception:
        return r.status_code, None, r.text[:60]


def scenario(name, fn, n):
    results = {}
    t0 = time.time()
    for _ in range(n):
        key = fn()
        results[key] = results.get(key, 0) + 1
    dt = time.time() - t0
    print(f"\n[{name}] {n} 次 / {dt:.1f}s = {n/dt:.1f} rps")
    for k, v in sorted(results.items(), key=lambda x: -x[1]):
        print(f"  {v:4d}x  {k}")


if __name__ == "__main__":
    conc = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 12

    print("=== 场景1: 基线(正确签名, 顺序) ===")
    scenario("baseline", lambda: str(call()), 3)

    print("\n=== 场景2: 边界值 ===")
    for off, label in [(0, "ts正确"), (-3600, "ts-1h"), (-86400, "ts-1d"), (60, "ts+1m")]:
        c, code, m = call(ts_offset=off)
        print(f"  {label:8s} -> http={c} biz={code} {m}")
    c, code, m = call(sign_key="wrongkey")
    print(f"  错误key   -> http={c} biz={code} {m}")
    c, code, m = call(cp="com.other.app")
    print(f"  错误包名  -> http={c} biz={code} {m}")

    print(f"\n=== 场景3: 并发节流探测 ({conc} 并发 x {total}) ===")
    with concurrent.futures.ThreadPoolExecutor(max_workers=conc) as ex:
        futs = [ex.submit(lambda: str(call())) for _ in range(total)]
        agg = {}
        for f in concurrent.futures.as_completed(futs):
            k = f.result()
            agg[k] = agg.get(k, 0) + 1
    for k, v in sorted(agg.items(), key=lambda x: -x[1]):
        print(f"  {v:4d}x  {k}")
    print("\n=== 完成 ===")
