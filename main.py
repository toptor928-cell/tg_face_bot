import os
import io
import json
import base64
import asyncio
import requests
from PIL import Image
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
import numpy as np
import mediapipe as mp
import cv2
from datetime import datetime

TELEGRAM_TOKEN = "8658818301:AAH0ZyTItNkGMOXkgEf6RJLuviThkZxDhAI"

os.makedirs("faces", exist_ok=True)
os.makedirs("generated", exist_ok=True)
os.makedirs("limits", exist_ok=True)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)

HF_API_KEY = ""  # можно оставить пустым, работает без ключа для BLIP

def get_user_requests(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    path = f"limits/{user_id}_{today}.json"
    if not os.path.exists(path):
        return 0
    with open(path, "r") as f:
        return json.load(f).get("count", 0)

def increment_user_requests(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    path = f"limits/{user_id}_{today}.json"
    count = get_user_requests(user_id)
    with open(path, "w") as f:
        json.dump({"count": count + 1}, f)

def extract_face(image_bytes, user_id):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    results = face_detection.process(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
    if not results.detections:
        return None
    detection = results.detections[0]
    bbox = detection.location_data.relative_bounding_box
    h, w, _ = img_cv.shape
    x = int(bbox.xmin * w)
    y = int(bbox.ymin * h)
    x2 = int((bbox.xmin + bbox.width) * w)
    y2 = int((bbox.ymin + bbox.height) * h)
    face = img.crop((x, y, x2, y2))
    path = f"faces/user_{user_id}.jpg"
    face.save(path)
    return path

def describe_photo_online(image_bytes):
    # Используем бесплатный HuggingFace API для BLIP
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_base64 = base64.b64encode(io.BytesIO(image_bytes).getvalue()).decode("utf-8")
    url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"} if HF_API_KEY else {}
    try:
        response = requests.post(url, headers=headers, data=image_bytes, timeout=30)
        if response.status_code == 200:
            return response.json()[0]["generated_text"]
        else:
            return "a person"
    except:
        return "a person"

def generate_free_with_face(prompt, user_id):
    face_path = f"faces/user_{user_id}.jpg"
    if not os.path.exists(face_path):
        return None
    with open(face_path, "rb") as f:
        face_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    API_URL = "https://instant-id.hf.space/run/predict"
    payload = {"data": [face_b64, prompt, 0.8, 30, 768, 768]}
    try:
        resp = requests.post(API_URL, json=payload, timeout=120)
        if resp.status_code == 200:
            img_data = base64.b64decode(resp.json()["data"][0])
            return io.BytesIO(img_data)
    except:
        return None
    return None

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.reply("📸 Отправь фото с лицом. Лимит 50/день. Команды: /status, /reset_face, /generate <промпт>")

@dp.message_handler(commands=['status'])
async def status_cmd(message: types.Message):
    used = get_user_requests(message.from_user.id)
    await message.reply(f"📊 Сегодня: {used}/50, осталось: {50-used}")

@dp.message_handler(commands=['reset_face'])
async def reset_face(message: types.Message):
    path = f"faces/user_{message.from_user.id}.jpg"
    if os.path.exists(path):
        os.remove(path)
    await message.reply("🗑 Лицо удалено.")

@dp.message_handler(commands=['generate'])
async def generate_cmd(message: types.Message):
    user_id = message.from_user.id
    prompt = message.get_args()
    if not prompt:
        await message.reply("Пример: /generate киберпанк девушка")
        return
    if get_user_requests(user_id) >= 50:
        await message.reply("⛔ Лимит 50/день.")
        return
    await message.reply("🎨 Генерация...")
    result = generate_free_with_face(prompt, user_id)
    if not result:
        await message.reply("❌ Ошибка генерации.")
        return
    increment_user_requests(user_id)
    await message.reply_photo(InputFile(result), caption=f"✅ Готово!\nПромпт: {prompt}")

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo = message.photo[-1]
    file = await bot.download(photo.file_id)
    img_bytes = file.read()
    
    if not extract_face(img_bytes, user_id):
        await message.reply("❌ Лицо не найдено.")
        return
    
    prompt = describe_photo_online(img_bytes)
    await message.reply(f"🔍 Промпт: *{prompt}*", parse_mode="Markdown")
    
    if get_user_requests(user_id) >= 50:
        await message.reply("⛔ Лимит 50/день.")
        return
    
    await message.reply("🎨 Генерация...")
    result = generate_free_with_face(prompt, user_id)
    if not result:
        await message.reply("❌ Ошибка генерации.")
        return
    increment_user_requests(user_id)
    await message.reply_photo(InputFile(result), caption=f"✅ Готово!\nПромпт: {prompt}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
