#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phota3A (AI Video Maker 3A Phota Lite v1.0.42) 2api demo server
上游: sci.videomate.cc  /algo/v1/faceFusion/aigc/*
鉴权: sign = md5("gmdh1Z" + timeStamp秒), 头 userid/timeStamp/cp/version/platform/sign
用法: python demo_server.py  (端口 8902, 需 PYTHONPATH 无特殊依赖, 仅 requests+flask)
"""
import hashlib
import json
import time
import uuid

import requests
from flask import Flask, Response, jsonify, request, send_file

UPSTREAM = "https://sci.videomate.cc"
SIGN_KEY = "gmdh1Z"          # DES 解密结果 (key=IM41OUCa, IV=1234567890ABCDEF)
PACKAGE = "com.mivii.mvlite.editor"
VERSION = "42"
PLATFORM = "1"

app = Flask(__name__, static_folder=".")
TASKS = {}  # 本地任务台账: job_id -> {endpoint, created}

session = requests.Session()
session.proxies = {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}  # 本地代理, 可按需改


def build_headers(userid=None):
    ts = str(int(time.time()))
    sign = hashlib.md5((SIGN_KEY + ts).encode()).hexdigest()
    return {
        "Content-Type": "application/json",
        "userid": userid or ("u" + uuid.uuid4().hex[:12]),
        "timeStamp": ts,
        "cp": PACKAGE,
        "version": VERSION,
        "platform": PLATFORM,
        "sign": sign,
        "User-Agent": "okhttp/4.9.3",
    }


def upstream_post(path, body, userid=None):
    return session.post(UPSTREAM + path, headers=build_headers(userid), data=json.dumps(body), timeout=60)


# ---------- 健康检查 ----------
@app.get("/health")
def health():
    return jsonify({"status": "ok", "upstream": UPSTREAM, "sign_key": SIGN_KEY})


# ---------- 原生透传: 任意 /algo 路径 ----------
@app.route("/algo/<path:p>", methods=["POST", "GET"])
def algo_proxy(p):
    body = request.get_json(silent=True) or {}
    r = upstream_post("/algo/" + p, body, request.headers.get("X-Upstream-Userid"))
    return Response(r.content, status=r.status_code, mimetype="application/json")


# ---------- OpenAI 风格: 图片转视频 ----------
@app.post("/v1/images2video")
def images2video():
    """body: {image_urls:[...], prompt?, template_id?, model_id?, p2_type?}"""
    b = request.get_json(force=True)
    userid = "u" + uuid.uuid4().hex[:12]
    body = {
        "style": "aiGenerate",
        "imageUrls": b.get("image_urls", []),
        "params": json.dumps(b.get("params", {})),
    }
    if b.get("template_id"):
        body["templateId"] = b["template_id"]
    if b.get("model_id"):
        body["modelId"] = b["model_id"]
    r = upstream_post("/algo/v1/faceFusion/aigc/image2VideoCreateV2", body, userid)
    TASKS[userid] = {"endpoint": "/algo/v1/faceFusion/aigc/image2VideoQuery", "created": time.time()}
    return _relay(r, userid)


# ---------- 已实测链路封装 ----------
@app.post("/v1/upload")
def upload():
    """multipart 上传文件(files=...), 返回 algo.videomate.cc URL"""
    ts = str(int(time.time()))
    sign = hashlib.md5((SIGN_KEY + ts).encode()).hexdigest()
    files = request.files.getlist("files")
    payload = [("files", (f.filename, f.stream, f.mimetype or "image/jpg")) for f in files]
    r = session.post(
        UPSTREAM + "/algo/v1/aiGenerate-aigc/multipleUpload",
        headers={"userid": "u" + uuid.uuid4().hex[:12], "timeStamp": ts, "cp": PACKAGE,
                 "version": VERSION, "platform": PLATFORM, "sign": sign, "User-Agent": "okhttp/4.9.3"},
        files=payload, data={"ifHttps": "true"}, timeout=120)
    return Response(r.content, status=r.status_code, mimetype="application/json")


@app.post("/v1/stitch")
def stitch():
    """双图拼接 (AI情侣照), body {imageUrls:[url1,url2]}; 异步任务"""
    b = request.get_json(force=True)
    ts = str(int(time.time()))
    sign = hashlib.md5((SIGN_KEY + ts).encode()).hexdigest()
    uid = "u" + uuid.uuid4().hex[:12]
    r = session.post(UPSTREAM + "/algo/v1/faceFusion/aigc/stitchImage/createTask",
                     headers={"Content-Type": "application/json", "version": VERSION, "cp": PACKAGE,
                              "platform": PLATFORM, "userId": uid, "sign": sign, "timestamp": ts},
                     data=json.dumps({"imageUrls": b["imageUrls"]}), timeout=120)
    data = r.json()
    job = (data.get("d") or {}).get("taskId") if isinstance(data.get("d"), dict) else None
    if job:
        TASKS[job] = {"endpoint": "/algo/v1/faceFusion/aigc/stitchImage/queryTask", "field": "taskId"}
    return Response(r.content, status=r.status_code, mimetype="application/json")


@app.post("/v1/facekey")
def facekey():
    """人脸特征提取, body {images:[url]}; 异步"""
    b = request.get_json(force=True)
    r = upstream_post("/algo/v1/faceFusion/aigc/createFaceKeyTask", {"images": b["images"]})
    data = r.json()
    if isinstance(data.get("d"), str) and data["d"]:
        TASKS[data["d"]] = {"endpoint": "/algo/v1/faceFusion/aigc/queryFaceKeyTaskV2", "field": "taskId"}
    return Response(r.content, status=r.status_code, mimetype="application/json")


@app.post("/v1/picture-detect")
def picture_detect():
    """人脸检测(脸框), body {imageUrls:[url], ratio?}; 异步"""
    b = request.get_json(force=True)
    r = upstream_post("/algo/v1/faceFusion/aigc/createPictureDetectTask",
                      {"imageUrls": b["imageUrls"], "ratio": b.get("ratio", "9:16")})
    data = r.json()
    if isinstance(data.get("d"), str) and data["d"]:
        TASKS[data["d"]] = {"endpoint": "/algo/v1/faceFusion/aigc/queryPictureDetectTask", "field": "taskId"}
    return Response(r.content, status=r.status_code, mimetype="application/json")


@app.post("/v1/face-info")
def face_info():
    """人脸信息(性别/年龄/框), 同步"""
    b = request.get_json(force=True)
    r = upstream_post("/algo/v1/faceFusion/aigc/getFaceInfo", {"imageUrls": b["imageUrls"]})
    return Response(r.content, status=r.status_code, mimetype="application/json")


# ---------- 查询任务 ----------
@app.post("/v1/tasks/<job_id>")
def query_task(job_id):
    """查询任务结果(自动重放对应 query 端点)"""
    info = TASKS.get(job_id)
    if info:
        r = upstream_post(info["endpoint"], {info["field"]: job_id})
    else:
        r = upstream_post("/algo/v1/faceFusion/aigc/stitchImage/queryTask", {"taskId": job_id})
    return _relay(r, job_id)


def _relay(r, userid):
    try:
        data = r.json()
    except Exception:
        return jsonify({"raw": r.text[:2000], "status": r.status_code}), r.status_code
    data.setdefault("_job_ref", userid)
    return jsonify(data), (200 if data.get("c") == 200 else 502)


# ---------- demo 页 ----------
@app.get("/")
def demo():
    return send_file("demo.html")


if __name__ == "__main__":
    print("Phota3A 2api demo -> http://127.0.0.1:8913  (upstream %s, signKey=%s)" % (UPSTREAM, SIGN_KEY))
    app.run(host="127.0.0.1", port=8913, debug=False)
