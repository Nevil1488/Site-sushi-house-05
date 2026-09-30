"""
Telegram-бот для управления меню (products.json) и категориями.
Работает на aiogram 3+

УСТАНОВКА:
    pip install aiogram

НАСТРОЙКА:
    1. Вставьте токен бота в BOT_TOKEN (получить у @BotFather)
    2. Вставьте свой Telegram ID в ADMIN_IDS (узнать у @userinfobot)
    3. Запустите: python bot.py
"""

import asyncio
import json
import re
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8885443774:AAEW2bLG3JQY-bcXZGjXkyqws-hSRUHElDg"
ADMIN_IDS = [5312985947]  # ← ваш Telegram ID

BASE_DIR = Path(__file__).parent
PRODUCTS_FILE = BASE_DIR / "products.json"
IMAGES_THUMB = BASE_DIR / "images" / "thumb"

IMAGES_THUMB.mkdir(parents=True, exist_ok=True)

# ===================== ФАЙЛ =====================

import subprocess

def git_push():
    try:
        subprocess.run(["git", "add", "products.json"], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "commit", "-m", "Auto-update menu"], cwd=BASE_DIR, check=True)
        subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
    except Exception as e:
        print("⚠️ Git push failed:", e)

def load_data() -> dict:
    if not PRODUCTS_FILE.exists():
        return {"categories": []}
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"categories": []}

def save_data(data: dict) -> None:
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    git_push()

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-zа-яё0-9]+", "_", text, flags=re.IGNORECASE)
    return text.strip("_") or "item"

# ===================== КЛАВИАТУРЫ =====================
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Просмотр меню",     callback_data="view:cats")],
        [InlineKeyboardButton(text="🍽 Управление блюдами", callback_data="items:menu")],
        [InlineKeyboardButton(text="📁 Управление категориями", callback_data="cats:menu")],
    ])

def items_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить блюдо",  callback_data="add:start")],
        [InlineKeyboardButton(text="✏️ Изменить блюдо",  callback_data="edit:cats")],
        [InlineKeyboardButton(text="🗑 Удалить блюдо",   callback_data="del:cats")],
        [InlineKeyboardButton(text="⬅️ Назад",           callback_data="menu:main")],
    ])

def cats_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить категорию",  callback_data="cats:add")],
        [InlineKeyboardButton(text="✏️ Изменить категорию",  callback_data="cats:edit")],
        [InlineKeyboardButton(text="🗑 Удалить категорию",   callback_data="cats:del")],
        [InlineKeyboardButton(text="⬅️ Назад",                callback_data="menu:main")],
    ])

def categories_kb(action: str) -> InlineKeyboardMarkup:
    data = load_data()
    cats = data.get("categories", [])
    kb = []
    for i, c in enumerate(cats):
        icon = c.get("icon", "🍽")
        name = c.get("name", "Без названия")
        count = len(c.get("items", []))
        kb.append([InlineKeyboardButton(
            text=f"{icon} {name} ({count})",
            callback_data=f"{action}:cat:{i}"
        )])

    # Куда возвращаться в зависимости от действия
    back_targets = {
        "add":       "items:menu",   # добавление блюда → в меню блюд
        "edit":      "items:menu",   # изменение блюда → в меню блюд
        "del":       "items:menu",   # удаление блюда → в меню блюд
        "catsedit":  "cats:menu",    # изменение категории → в меню категорий
        "catsdel":   "cats:menu",    # удаление категории → в меню категорий
    }
    back = back_targets.get(action, "menu:main")

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def items_kb(action: str, cat_idx: int) -> InlineKeyboardMarkup:
    data = load_data()
    try:
        items = data["categories"][cat_idx]["items"]
    except (IndexError, KeyError):
        items = []
    kb = []
    for i, it in enumerate(items):
        name = it.get("name", "Без названия")
        price = it.get("price", 0)
        kb.append([InlineKeyboardButton(
            text=f"{name} — {price} ₽",
            callback_data=f"{action}:item:{cat_idx}:{i}"
        )])
    kb.append([InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data=f"{action}:cats")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def cat_fields_kb(cat_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Название",  callback_data=f"cats:field:name:{cat_idx}")],
        [InlineKeyboardButton(text="😀 Эмодзи",     callback_data=f"cats:field:icon:{cat_idx}")],
        [InlineKeyboardButton(text="⬅️ Назад",      callback_data="cats:edit")],
    ])

def fields_kb(cat_idx: int, item_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Название",  callback_data=f"edit:field:name:{cat_idx}:{item_idx}")],
        [InlineKeyboardButton(text="📄 Описание",  callback_data=f"edit:field:desc:{cat_idx}:{item_idx}")],
        [InlineKeyboardButton(text="💰 Цена",      callback_data=f"edit:field:price:{cat_idx}:{item_idx}")],
        [InlineKeyboardButton(text="🖼 Фото",       callback_data=f"edit:field:img:{cat_idx}:{item_idx}")],
        [InlineKeyboardButton(text="⬅️ Назад",      callback_data=f"edit:cat:{cat_idx}")],
    ])

def confirm_del_kb(cat_idx: int, item_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"del:confirm:{cat_idx}:{item_idx}"),
            InlineKeyboardButton(text="❌ Отмена",      callback_data="items:menu"),
        ],
    ])

def confirm_del_cat_kb(cat_idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"cats:del:confirm:{cat_idx}"),
            InlineKeyboardButton(text="❌ Отмена",      callback_data="cats:menu"),
        ],
    ])

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="menu:main")]
    ])

def skip_or_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data="cats:add:skip_icon")],
        [InlineKeyboardButton(text="❌ Отмена",       callback_data="menu:main")],
    ])

# ===================== СОСТОЯНИЯ =====================
class AddItem(StatesGroup):
    name = State()
    desc = State()
    price = State()
    photo = State()

class EditText(StatesGroup):
    value = State()

class EditPhoto(StatesGroup):
    waiting = State()

class AddCategory(StatesGroup):
    name = State()
    icon = State()

class EditCategory(StatesGroup):
    value = State()

# ===================== РОУТЕР =====================
router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# ---------------- СТАРТ / ОТМЕНА ----------------
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return
    await state.clear()
    await message.answer(
        "👋 <b>Панель управления меню</b>\n\n"
        "Здесь можно управлять блюдами и категориями.",
        reply_markup=main_menu_kb(),
    )

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=main_menu_kb())

@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "👋 <b>Панель управления меню</b>"
    try:
        await call.message.edit_text(text, reply_markup=main_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=main_menu_kb())
    await call.answer()

@router.callback_query(F.data == "items:menu")
async def cb_items_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "🍽 <b>Управление блюдами</b>"
    try:
        await call.message.edit_text(text, reply_markup=items_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=items_menu_kb())
    await call.answer()

@router.callback_query(F.data == "cats:menu")
async def cb_cats_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "📁 <b>Управление категориями</b>"
    try:
        await call.message.edit_text(text, reply_markup=cats_menu_kb())
    except Exception:
        await call.message.answer(text, reply_markup=cats_menu_kb())
    await call.answer()

# ---------------- ПРОСМОТР ----------------
@router.callback_query(F.data == "view:cats")
async def cb_view_cats(call: CallbackQuery):
    data = load_data()
    cats = data.get("categories", [])
    if not cats:
        text = "📭 Категорий пока нет."
    else:
        lines = ["📋 <b>Список категорий:</b>\n"]
        for i, c in enumerate(cats):
            icon = c.get("icon", "🍽")
            name = c.get("name", "Без названия")
            count = len(c.get("items", []))
            lines.append(f"{i+1}. {icon} <b>{name}</b> — {count} поз.")
        text = "\n".join(lines)

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")]
        ]),
    )
    await call.answer()

# ============================================================
# УПРАВЛЕНИЕ КАТЕГОРИЯМИ
# ============================================================

# --- ДОБАВИТЬ КАТЕГОРИЮ ---
@router.callback_query(F.data == "cats:add")
async def cb_cat_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddCategory.name)
    await call.message.edit_text(
        "📁 <b>Новая категория</b>\n\n"
        "Введите <b>название</b> категории:\n"
        "<i>(например: Пицца, Суши, Напитки)</i>",
        reply_markup=cancel_kb(),
    )
    await call.answer()

@router.message(AddCategory.name)
async def cat_add_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Название не может быть пустым:")
        return
    await state.update_data(cat_name=name)
    await state.set_state(AddCategory.icon)
    await message.answer(
        "😀 Отправьте <b>эмодзи</b> для категории\n"
        "<i>(например: 🍕 🍣 🥤 🍔)</i>\n\n"
        "Или нажмите «Пропустить» — будет использоваться 🍽",
        reply_markup=skip_or_cancel_kb(),
    )

@router.callback_query(F.data == "cats:add:skip_icon", AddCategory.icon)
async def cat_add_skip(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await finish_cat_add(call.message, state, data["cat_name"], "🍽")
    await call.answer()

@router.message(AddCategory.icon)
async def cat_add_icon(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    icon = text if text else "🍽"
    data = await state.get_data()
    await finish_cat_add(message, state, data["cat_name"], icon)

async def finish_cat_add(message: Message, state: FSMContext, name: str, icon: str):
    await state.clear()
    products = load_data()
    if "categories" not in products:
        products["categories"] = []
    products["categories"].append({
        "id": slugify(name),
        "name": name,
        "icon": icon,
        "items": []
    })
    save_data(products)
    await message.answer(
        f"✅ Категория <b>{icon} {name}</b> создана!",
        reply_markup=cats_menu_kb(),
    )

# --- ИЗМЕНИТЬ КАТЕГОРИЮ ---
@router.callback_query(F.data == "cats:edit")
async def cb_cat_edit(call: CallbackQuery):
    await call.message.edit_text(
        "📁 Выберите категорию для изменения:",
        reply_markup=categories_kb("catsedit"),
    )
    await call.answer()

@router.callback_query(F.data.regexp(r"^catsedit:cat:\d+$"))
async def cb_cat_edit_pick(call: CallbackQuery):
    cat_idx = int(call.data.split(":")[2])
    data = load_data()
    try:
        cat = data["categories"][cat_idx]
    except (IndexError, KeyError):
        await call.answer("Категория не найдена", show_alert=True)
        return

    text = (
        f"📁 <b>{cat.get('icon','🍽')} {cat.get('name','')}</b>\n"
        f"Блюд в категории: {len(cat.get('items', []))}\n\n"
        f"Что изменить?"
    )
    await call.message.edit_text(text, reply_markup=cat_fields_kb(cat_idx))
    await call.answer()

@router.callback_query(F.data.regexp(r"^cats:field:(name|icon):\d+$"))
async def cb_cat_edit_field(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    field, cat_idx = parts[2], int(parts[3])

    label = "новое <b>название</b>" if field == "name" else "новый <b>эмодзи</b>"
    await state.update_data(field=field, cat_idx=cat_idx)
    await state.set_state(EditCategory.value)
    await call.message.edit_text(
        f"✏️ Введите {label}:",
        reply_markup=cancel_kb(),
    )
    await call.answer()

@router.message(EditCategory.value)
async def cat_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    field = data["field"]
    cat_idx = data["cat_idx"]
    value = (message.text or "").strip()

    if not value:
        await message.answer("❌ Значение не может быть пустым.")
        return

    products = load_data()
    try:
        products["categories"][cat_idx][field] = value
        # Если поменяли название — обновляем и id
        if field == "name":
            products["categories"][cat_idx]["id"] = slugify(value)
        save_data(products)
    except (IndexError, KeyError) as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return

    cat = products["categories"][cat_idx]
    await message.answer(
        f"✅ Категория обновлена: <b>{cat.get('icon','🍽')} {cat.get('name','')}</b>",
        reply_markup=cats_menu_kb(),
    )

# --- УДАЛИТЬ КАТЕГОРИЮ ---
@router.callback_query(F.data == "cats:del")
async def cb_cat_del(call: CallbackQuery):
    await call.message.edit_text(
        "🗑 Выберите категорию для удаления:",
        reply_markup=categories_kb("catsdel"),
    )
    await call.answer()

@router.callback_query(F.data.regexp(r"^catsdel:cat:\d+$"))
async def cb_cat_del_pick(call: CallbackQuery):
    cat_idx = int(call.data.split(":")[2])
    data = load_data()
    try:
        cat = data["categories"][cat_idx]
    except (IndexError, KeyError):
        await call.answer("Категория не найдена", show_alert=True)
        return

    count = len(cat.get("items", []))
    warn = ""
    if count > 0:
        warn = f"\n\n⚠️ В категории <b>{count}</b> блюд — они тоже будут удалены!"

    await call.message.edit_text(
        f"❓ Удалить категорию <b>{cat.get('icon','🍽')} {cat.get('name','')}</b>?{warn}",
        reply_markup=confirm_del_cat_kb(cat_idx),
    )
    await call.answer()

@router.callback_query(F.data.regexp(r"^cats:del:confirm:\d+$"))
async def cb_cat_del_confirm(call: CallbackQuery):
    cat_idx = int(call.data.split(":")[3])
    products = load_data()
    try:
        removed = products["categories"].pop(cat_idx)
        save_data(products)
    except (IndexError, KeyError) as e:
        await call.message.edit_text(f"❌ Ошибка удаления: {e}")
        await call.answer()
        return

    await call.message.edit_text(
        f"✅ Категория <b>{removed.get('icon','🍽')} {removed.get('name','')}</b> удалена.",
        reply_markup=cats_menu_kb(),
    )
    await call.answer("Удалено")

# ============================================================
# УПРАВЛЕНИЕ БЛЮДАМИ
# ============================================================

# --- ДОБАВЛЕНИЕ БЛЮДА ---
@router.callback_query(F.data == "add:start")
async def cb_add_start(call: CallbackQuery):
    data = load_data()
    cats = data.get("categories", [])
    if not cats:
        await call.message.edit_text(
            "⚠️ Нет ни одной категории.\nСначала создайте категорию.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📁 Создать категорию", callback_data="cats:add")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="items:menu")],
            ]),
        )
        await call.answer()
        return
    await call.message.edit_text(
        "📁 Выберите категорию, куда добавить блюдо:",
        reply_markup=categories_kb("add"),
    )
    await call.answer()

@router.callback_query(F.data.startswith("add:cat:"))
async def cb_add_cat(call: CallbackQuery, state: FSMContext):
    cat_idx = int(call.data.split(":")[2])
    data = load_data()
    try:
        cat_name = data["categories"][cat_idx]["name"]
    except (IndexError, KeyError):
        await call.answer("Категория не найдена", show_alert=True)
        return

    await state.update_data(cat_idx=cat_idx)
    await state.set_state(AddItem.name)
    await call.message.edit_text(
        f"📁 Категория: <b>{cat_name}</b>\n\n"
        "Введите <b>название блюда</b>:\n<i>(или /cancel)</i>",
        reply_markup=cancel_kb(),
    )
    await call.answer()

@router.message(AddItem.name)
async def add_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ Название не может быть пустым:")
        return
    await state.update_data(name=name)
    await state.set_state(AddItem.desc)
    await message.answer(
        "📄 Введите <b>описание</b>\n<i>(или <code>-</code> чтобы пропустить):</i>",
        reply_markup=cancel_kb(),
    )

@router.message(AddItem.desc)
async def add_desc(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    desc = "" if text == "-" else text
    await state.update_data(desc=desc)
    await state.set_state(AddItem.price)
    await message.answer(
        "💰 Введите <b>цену</b> (только число):",
        reply_markup=cancel_kb(),
    )

@router.message(AddItem.price)
async def add_price(message: Message, state: FSMContext):
    try:
        price = int((message.text or "").strip())
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Цена должна быть положительным числом:")
        return
    await state.update_data(price=price)
    await state.set_state(AddItem.photo)
    await message.answer(
        "🖼 <b>Отправьте фото блюда</b> как картинку 📷\n\n"
        "<i>Или напишите <code>-</code> чтобы добавить без фото.</i>",
        reply_markup=cancel_kb(),
    )

@router.message(AddItem.photo, F.photo)
async def add_photo_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    item_name = data["name"]

    photo = message.photo[-1]
    slug = slugify(item_name)
    filename = f"{slug}.jpg"
    save_path = IMAGES_THUMB / filename

    try:
        await bot.download(photo, destination=save_path)
    except Exception as e:
        await message.answer(f"❌ Не удалось сохранить фото: {e}")
        return

    img_path = f"images/thumb/{filename}"

    new_item = {
        "name": item_name,
        "desc": data["desc"],
        "price": data["price"],
        "img": img_path,
    }

    products = load_data()
    try:
        products["categories"][data["cat_idx"]]["items"].append(new_item)
        save_data(products)
    except (IndexError, KeyError) as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return

    await state.clear()
    cat_name = products["categories"][data["cat_idx"]]["name"]
    await message.answer(
        f"✅ Блюдо <b>{item_name}</b> добавлено в <b>{cat_name}</b>!\n"
        f"🖼 Фото сохранено как <code>{img_path}</code>",
        reply_markup=items_menu_kb(),
    )

@router.message(AddItem.photo, F.text == "-")
async def add_photo_skip(message: Message, state: FSMContext):
    data = await state.get_data()
    new_item = {
        "name": data["name"],
        "desc": data["desc"],
        "price": data["price"],
        "img": "",
    }

    products = load_data()
    try:
        products["categories"][data["cat_idx"]]["items"].append(new_item)
        save_data(products)
    except (IndexError, KeyError) as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return

    await state.clear()
    cat_name = products["categories"][data["cat_idx"]]["name"]
    await message.answer(
        f"✅ Блюдо <b>{data['name']}</b> добавлено в <b>{cat_name}</b> без фото.",
        reply_markup=items_menu_kb(),
    )

@router.message(AddItem.photo)
async def add_photo_invalid(message: Message):
    await message.answer(
        "❌ Пожалуйста, отправьте <b>фотографию</b> 📷 или напишите <code>-</code> чтобы пропустить."
    )

# --- РЕДАКТИРОВАНИЕ БЛЮДА ---
@router.callback_query(F.data == "edit:cats")
async def cb_edit_cats(call: CallbackQuery):
    await call.message.edit_text(
        "📁 Выберите категорию:",
        reply_markup=categories_kb("edit"),
    )
    await call.answer()

@router.callback_query(F.data.regexp(r"^edit:cat:\d+$"))
async def cb_edit_cat(call: CallbackQuery):
    cat_idx = int(call.data.split(":")[2])
    data = load_data()
    try:
        cat_name = data["categories"][cat_idx]["name"]
        items = data["categories"][cat_idx]["items"]
    except (IndexError, KeyError):
        await call.answer("Категория не найдена", show_alert=True)
        return

    if not items:
        await call.message.edit_text(
            f"📭 В категории <b>{cat_name}</b> нет блюд.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К категориям", callback_data="edit:cats")]
            ]),
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"📁 Категория: <b>{cat_name}</b>\n\nВыберите блюдо:",
        reply_markup=items_kb("edit", cat_idx),
    )
    await call.answer()

@router.callback_query(F.data.startswith("edit:item:"))
async def cb_edit_item(call: CallbackQuery):
    parts = call.data.split(":")
    cat_idx, item_idx = int(parts[2]), int(parts[3])
    data = load_data()
    try:
        item = data["categories"][cat_idx]["items"][item_idx]
    except (IndexError, KeyError):
        await call.answer("Блюдо не найдено", show_alert=True)
        return

    img_show = item.get("img", "") or "— не указано —"
    text = (
        f"🍽 <b>{item.get('name','')}</b>\n"
        f"📄 {item.get('desc','') or '—'}\n"
        f"💰 {item.get('price',0)} ₽\n"
        f"🖼 {img_show}\n\n"
        f"Что изменить?"
    )
    await call.message.edit_text(text, reply_markup=fields_kb(cat_idx, item_idx))
    await call.answer()

@router.callback_query(F.data.regexp(r"^edit:field:(name|desc|price):\d+:\d+$"))
async def cb_edit_text_field(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    field, cat_idx, item_idx = parts[2], int(parts[3]), int(parts[4])

    labels = {
        "name": "новое <b>название</b>",
        "desc": "новое <b>описание</b> (или <code>-</code> чтобы очистить)",
        "price": "новую <b>цену</b> (только число)",
    }

    await state.update_data(field=field, cat_idx=cat_idx, item_idx=item_idx)
    await state.set_state(EditText.value)
    await call.message.edit_text(
        f"✏️ Введите {labels[field]}:",
        reply_markup=cancel_kb(),
    )
    await call.answer()

@router.message(EditText.value)
async def edit_text_value(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    field = data["field"]
    cat_idx = data["cat_idx"]
    item_idx = data["item_idx"]
    value = (message.text or "").strip()

    if field == "price":
        try:
            value = int(value)
            if value < 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Цена должна быть положительным числом.")
            return
    elif field == "desc" and value == "-":
        value = ""

    products = load_data()
    try:
        products["categories"][cat_idx]["items"][item_idx][field] = value
        save_data(products)
    except (IndexError, KeyError) as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")
        return

    item_name = products["categories"][cat_idx]["items"][item_idx].get("name", "")
    await message.answer(
        f"✅ Поле <b>{field}</b> у блюда <b>{item_name}</b> обновлено!",
        reply_markup=items_menu_kb(),
    )

@router.callback_query(F.data.regexp(r"^edit:field:img:\d+:\d+$"))
async def cb_edit_photo(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    cat_idx, item_idx = int(parts[3]), int(parts[4])
    await state.update_data(cat_idx=cat_idx, item_idx=item_idx)
    await state.set_state(EditPhoto.waiting)
    await call.message.edit_text(
        "🖼 <b>Отправьте новое фото блюда</b> (как картинку 📷)\n\n"
        "<i>Или напишите <code>-</code> чтобы удалить фото.</i>",
        reply_markup=cancel_kb(),
    )
    await call.answer()

@router.message(EditPhoto.waiting, F.photo)
async def edit_photo_receive(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()

    cat_idx = data["cat_idx"]
    item_idx = data["item_idx"]

    products = load_data()
    try:
        item = products["categories"][cat_idx]["items"][item_idx]
    except (IndexError, KeyError) as e:
        await message.answer(f"❌ Ошибка: {e}")
        return

    photo = message.photo[-1]
    slug = slugify(item.get("name", "item"))
    filename = f"{slug}.jpg"
    save_path = IMAGES_THUMB / filename

    try:
        await bot.download(photo, destination=save_path)
    except Exception as e:
        await message.answer(f"❌ Не удалось сохранить фото: {e}")
        return

    item["img"] = f"images/thumb/{filename}"
    save_data(products)

    await message.answer(
        f"✅ Фото блюда <b>{item.get('name','')}</b> обновлено!",
        reply_markup=items_menu_kb(),
    )

@router.message(EditPhoto.waiting, F.text == "-")
async def edit_photo_remove(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    cat_idx = data["cat_idx"]
    item_idx = data["item_idx"]

    products = load_data()
    try:
        products["categories"][cat_idx]["items"][item_idx]["img"] = ""
        save_data(products)
        item_name = products["categories"][cat_idx]["items"][item_idx].get("name", "")
    except (IndexError, KeyError) as e:
        await message.answer(f"❌ Ошибка: {e}")
        return

    await message.answer(
        f"✅ Фото блюда <b>{item_name}</b> удалено.",
        reply_markup=items_menu_kb(),
    )

@router.message(EditPhoto.waiting)
async def edit_photo_invalid(message: Message):
    await message.answer(
        "❌ Отправьте <b>фотографию</b> 📷 или напишите <code>-</code> чтобы удалить фото."
    )

# --- УДАЛЕНИЕ БЛЮДА ---
@router.callback_query(F.data == "del:cats")
async def cb_del_cats(call: CallbackQuery):
    await call.message.edit_text(
        "🗑 Выберите категорию:",
        reply_markup=categories_kb("del"),
    )
    await call.answer()

@router.callback_query(F.data.regexp(r"^del:cat:\d+$"))
async def cb_del_cat(call: CallbackQuery):
    cat_idx = int(call.data.split(":")[2])
    data = load_data()
    try:
        cat_name = data["categories"][cat_idx]["name"]
        items = data["categories"][cat_idx]["items"]
    except (IndexError, KeyError):
        await call.answer("Категория не найдена", show_alert=True)
        return

    if not items:
        await call.message.edit_text(
            f"📭 В категории <b>{cat_name}</b> нет блюд.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К категориям", callback_data="del:cats")]
            ]),
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"🗑 Категория: <b>{cat_name}</b>\n\nВыберите блюдо:",
        reply_markup=items_kb("del", cat_idx),
    )
    await call.answer()

@router.callback_query(F.data.startswith("del:item:"))
async def cb_del_item(call: CallbackQuery):
    parts = call.data.split(":")
    cat_idx, item_idx = int(parts[2]), int(parts[3])
    data = load_data()
    try:
        item = data["categories"][cat_idx]["items"][item_idx]
    except (IndexError, KeyError):
        await call.answer("Блюдо не найдено", show_alert=True)
        return

    await call.message.edit_text(
        f"❓ Удалить блюдо <b>{item.get('name','')}</b>?",
        reply_markup=confirm_del_kb(cat_idx, item_idx),
    )
    await call.answer()

@router.callback_query(F.data.startswith("del:confirm:"))
async def cb_del_confirm(call: CallbackQuery):
    parts = call.data.split(":")
    cat_idx, item_idx = int(parts[2]), int(parts[3])

    products = load_data()
    try:
        removed = products["categories"][cat_idx]["items"].pop(item_idx)
        save_data(products)
    except (IndexError, KeyError) as e:
        await call.message.edit_text(f"❌ Ошибка удаления: {e}")
        await call.answer()
        return

    await call.message.edit_text(
        f"✅ Блюдо <b>{removed.get('name','')}</b> удалено.",
        reply_markup=items_menu_kb(),
    )
    await call.answer("Удалено")

# ===================== ЗАПУСК =====================
async def main():
    if BOT_TOKEN.startswith("ВСТАВЬТЕ"):
        print("⚠️  Укажите BOT_TOKEN в файле bot.py!")
        return
    if not ADMIN_IDS or ADMIN_IDS == [123456789]:
        print("⚠️  Укажите свой Telegram ID в ADMIN_IDS!")
        return

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    print("🤖 Бот запущен. Ctrl+C для остановки.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен.")