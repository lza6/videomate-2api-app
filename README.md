# videomate-2api-app

**目标应用**: AI Video Maker 3A Phota Lite v1.0.42 PRØ (`com.mivii.mvlite.editor`, Mivi/ufotosoft 系)
**上游**: `https://sci.videomate.cc`

> ⚠️ 仅供安全研究与协议学习用途

## 鉴权（已破解并实测）

```
sign      = MD5(signKey + timeStamp秒)
signKey   = "gmdh1Z"   # DES/CBC 解密 "72UcMnmGjNw=", key=IM41OUCa, IV=1234567890ABCDEF
```

请求头: `userid`(任意) / `timeStamp`(秒) / `cp: com.mivii.mvlite.editor` / `version: 42` / `platform: 1` / `sign`

## 已验证链路（图片）

| 端点 | 说明 | 状态 |
|---|---|---|
| `POST /algo/v1/aiGenerate-aigc/multipleUpload` | multipart 上传图片/音频 | ✅ |
| `POST /algo/v1/faceFusion/aigc/stitchImage/createTask` | 双图拼接(AI情侣照) `{imageUrls:[a,b]}` | ✅ 真实出图 |
| `POST /algo/v1/faceFusion/aigc/stitchImage/queryTask` | `{taskId}` → responseUrl | ✅ |
| `POST /algo/v1/faceFusion/aigc/createFaceKeyTask` | 人脸特征 `{images:[url]}` | ✅（质检严，拒合成图） |
| `POST /algo/v1/faceFusion/aigc/createPictureDetectTask` | 人脸检测 `{imageUrls,ratio}` | ✅ |
| `POST /algo/v1/faceFusion/aigc/getFaceInfo` | 人脸信息(同步) | ✅ |

## 视频生成（未打通 — 三道墙）

1. `image2video/unifiedTaskCreate` 的 `example` 参数服务端白名单校验
2. AiHug 需 `poseSequenceId`，目录接口 `getAllPoseSequenceId` 已 404 下线
3. `createAiCustomizeTask` 参数凑齐后 → `ERROR_CREDIT_DEDUCTION_SERVICE`（credit 计费墙，免费 3 次/天在服务端记账）

## 使用

```bash
pip install flask requests
python demo_server.py        # http://127.0.0.1:8913

# 上传
curl -F "files=@face.jpg" http://127.0.0.1:8913/v1/upload

# 拼接(异步)
curl -X POST http://127.0.0.1:8913/v1/stitch \
  -H "Content-Type: application/json" \
  -d '{"imageUrls":["https://...a.jpg","https://...b.jpg"]}'
curl -X POST http://127.0.0.1:8913/v1/tasks/<taskId>
```

打开 `http://127.0.0.1:8913/` 有网页 demo。`/algo/*` 为原生任意端点透传。

## 压测

```bash
python stress_test.py [并发] [总数]   # 基线/边界值/并发三场景
```
4 并发无 429；时间戳窗口宽松(±1天)；风险在 credit 层而非频率层。

## 文档

- [逆向报告.md](逆向报告.md) — 完整 API 面谱(50+ 端点)、P2Type 任务类型、鉴权还原链、errCode 观测

## 下一步

- 真机/模拟器抓包拿有效 `example` 与 `poseSequenceId`
- 弄清 credit 发放机制（新设备首日额度?）
- LoRA 链: faceKey 过检 → roopImage → createAiPhotoModelV2
