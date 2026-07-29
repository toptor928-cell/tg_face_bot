import os
import io
import json
import base64
import asyncio
import requests
from PIL import Image
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from datetime import datetime

TELEGRAM_TOKEN = "8658818301:AAH0ZyTItNkGMOXkgEf6RJLuviThkZxDhAI"

os.makedirs("faces", exist_ok=True)
os.makedirs("limits", exist_ok=True)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

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

def get_prompt_from_image(image_bytes):
    url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
    try:
        resp = requests.post(url, data=image_bytes, timeout=60)
        if resp.status_code == 200:
            return resp.json()[0]["generated_text"]
        return "a person"
    except:
        return "a person"

def generate_with_face(prompt, user_id):
    face_path = f"faces/user_{user_id}.jpg"
    if not os.path.exists(face_path):
        return None
    with open(face_path, "rb") as f:
        face_b64 = base64.b64encode(f.read()).decode("utf-8")
    
    url = "https://instant-id.hf.space/run/predict"
    payload = {"data": [face_b64, prompt, 0.8, 30, 768, 768]}
    try:
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code == 200:
            img_data = base64.b64decode(resp.json()["data"][0])
            return io.BytesIO(img_data)
    except:
        return None
    return None

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.reply("📸 Отправь фото с лицом. Я запомню его и сгенерирую новое изображение.\nЛимит: 50/день.\nКоманды: /status, /reset_face, /generate <промпт>")

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
    result = generate_with_face(prompt, user_id)
    if not result:
        await message.reply("❌ Ошибка генерации. Попробуй позже.")
        return
    increment_user_requests(user_id)
    await message.reply_photo(InputFile(result), caption=f"✅ Готово!\nПромпт: {prompt}")

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo = message.photo[-1]
    file = await bot.download(photo.file_id)
    img_bytes = file.read()
    
    face_path = f"faces/user_{user_id}.jpg"
    with open(face_path, "wb") as f:
        f.write(img_bytes)
    
    prompt = get_prompt_from_image(img_bytes)
    await message.reply(f"🔍 Промпт: *{prompt}*", parse_mode="Markdown")
    
    if get_user_requests(user_id) >= 50:
        await message.reply("⛔ Лимит 50/день.")
        return
    
    await message.reply("🎨 Генерация...")
    result = generate_with_face(prompt, user_id)
    if not result:
        await message.reply("❌ Ошибка генерации.")
        return
    increment_user_requests(user_id)
    await message.reply_photo(InputFile(result), caption=f"✅ Готово!\nПромпт: {prompt}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
