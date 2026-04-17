import urllib.request
import urllib.error
import json
import os

# 找一张测试图（用uploads里现有的图）
upload_dir = "D:/pet_recognition_system/uploads"
test_image = None
if os.path.exists(upload_dir):
    imgs = [f for f in os.listdir(upload_dir) if f.lower().endswith(('.jpg','.jpeg','.png'))]
    if imgs:
        test_image = os.path.join(upload_dir, imgs[0])
        print("找到测试图:", test_image)
    else:
        print("uploads目录没有图片")
else:
    print("uploads目录不存在")

if test_image:
    import urllib.request as req
    # 手动构造 multipart POST
    boundary = "----testboundary12345"
    with open(test_image, 'rb') as f:
        img_data = f.read()
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"test.jpg\"\r\n"
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + img_data + f"\r\n--{boundary}--\r\n".encode()
    
    request = urllib.request.Request(
        "http://localhost:5000/api/recognize",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(request, timeout=30)
        result = json.loads(resp.read().decode())
        print("识别成功！结果:", json.dumps(result, ensure_ascii=False, indent=2)[:500])
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print("HTTP错误:", e.code, err[:500])
    except Exception as e:
        print("请求失败:", e)
else:
    print("无法测试，没有测试图片")

# 检查 web_app.py 启动时的模型状态
print("\n--- 检查模型文件 ---")
model_dirs = [
    "D:/pet_recognition_system",
    "D:/pet_recognition_system/models",
]
for d in model_dirs:
    if os.path.exists(d):
        files = os.listdir(d)
        model_files = [f for f in files if f.endswith(('.pth','.pt','.pkl','.h5','.onnx'))]
        if model_files:
            print(f"{d}: {model_files}")
